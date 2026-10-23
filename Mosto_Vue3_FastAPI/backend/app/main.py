"""Mosto API: prototipo de interfaz + adaptador seguro a Supabase PostgREST.

DEMO_MODE=true solo utiliza datos ficticios en RAM. Modo real exige JWT de
Supabase y políticas RLS comprobadas por bodega/empresa (HU-37).
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import csv
import os
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from .seed import create_seed

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in {"true", "1", "yes"}
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app = FastAPI(title="Mosto · API", version="0.1.0", description="MVP APT: telemetría, bodegas y alertas. El modo demo usa exclusivamente datos simulados.")
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN], allow_credentials=True, allow_methods=["GET","POST","PATCH","OPTIONS"], allow_headers=["Authorization","Content-Type"])
DEMO_DB = create_seed() if DEMO_MODE else {}

# Relación de entidades documentadas: diagram ER -> nombres PostgreSQL habituales.
TABLE_MAP = {
    "empresas": "empresa_cliente", "bodegas":"bodega","cubas":"cuba", "cepas":"cepa",
    "materiales":"tipo_material_cuba","modelos":"modelo_dispositivo","roles":"rol",
    "usuarios":"usuario","usuarios_bodega":"usuario_bodega","dispositivos":"dispositivo",
    "asignaciones":"asignacion_dispositivo","perfiles":"perfil_fermentacion",
    "fermentaciones":"proceso_fermentacion","umbrales":"umbral_fermentacion",
    "alertas":"evento_alerta","intervenciones":"bitacora_intervencion",
    "estados_nodo":"telemetria_estado_nodo","lecturas":"lectura_telemetria"
}
# No se expone escritura arbitraria: solo acciones previstas por historias de usuario.
WRITABLE = {"empresas", "bodegas", "cubas", "dispositivos", "asignaciones", "perfiles", "fermentaciones", "intervenciones", "usuarios_bodega"}

class LoginInput(BaseModel):
    email: str
    password: str

class PatchAlert(BaseModel):
    nota: str | None = None

class NewEntity(BaseModel):
    data: dict[str, Any]

class CloseFermentation(BaseModel):
    estado: str


def now():
    return datetime.now(timezone.utc).isoformat()

def demo_new_id(kind):
    return max((row.get("id",0) for row in DEMO_DB[kind]), default=0)+1

async def supabase_request(method: str, path: str, authorization: str | None, *, params: dict | None = None, json_data: Any = None, prefer: str | None = None):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(503, "Configura SUPABASE_URL y SUPABASE_ANON_KEY en el backend.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Se requiere una sesión de Supabase válida.")
    # Verificar token usando el servicio de Auth. No basta con decodificar el JWT sin verificar.
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": authorization}
    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            verified = await client.get(f"{SUPABASE_URL}/auth/v1/user", headers=headers)
            if verified.status_code != 200:
                raise HTTPException(401, "Sesión inválida o caducada.")
            api_headers = {**headers, "Content-Type":"application/json"}
            if prefer:
                api_headers["Prefer"] = prefer
            response = await client.request(method, f"{SUPABASE_URL}/rest/v1/{path}", headers=api_headers, params=params, json=json_data)
        except httpx.RequestError:
            raise HTTPException(502, "No se pudo establecer conexión con Supabase.")
    if response.status_code >= 400:
        if response.status_code in {401, 403}:
            raise HTTPException(403, "Acceso denegado por la configuración de seguridad o RLS.")
        raise HTTPException(422, "La operación no se pudo completar. Revisa datos, relaciones y permisos de la base.")
    if not response.content:
        return []
    return response.json()

@app.get("/api/health")
def health():
    return {"status":"ok", "mode":"demo" if DEMO_MODE else "live", "storage":"memory" if DEMO_MODE else "supabase"}

@app.get("/api/config")
def config():
    return {"mode":"demo" if DEMO_MODE else "live", "label":"DEMO · DATOS SIMULADOS" if DEMO_MODE else "DATOS REALES · SUPABASE"}

@app.post("/api/auth/login")
async def login(body: LoginInput):
    if DEMO_MODE:
        raise HTTPException(400, "El modo demo no necesita credenciales.")
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(503, "Supabase no está configurado.")
    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            resp = await client.post(f"{SUPABASE_URL}/auth/v1/token", params={"grant_type":"password"}, headers={"apikey": SUPABASE_ANON_KEY,"Content-Type":"application/json"}, json=body.model_dump())
        except httpx.RequestError:
            raise HTTPException(502, "Supabase Auth no está disponible.")
    if resp.status_code != 200:
        raise HTTPException(401, "No fue posible iniciar sesión. Comprueba tus credenciales.")
    payload = resp.json()
    return {"access_token":payload.get("access_token"),"expires_in":payload.get("expires_in"),"token_type":"bearer"}

@app.get("/api/{resource}")
async def list_records(resource: str, authorization: str | None = Header(None), fermentacion_id: int | None = Query(None), limit: int = Query(500, ge=1, le=5000)):
    if resource not in TABLE_MAP:
        raise HTTPException(404, "Recurso no encontrado.")
    if DEMO_MODE:
        records = deepcopy(DEMO_DB[resource])
        if fermentacion_id is not None:
            if resource not in {"alertas", "lecturas", "intervenciones", "umbrales"}:
                raise HTTPException(400, "Filtro no disponible para este recurso.")
            records = [r for r in records if r.get("fermentacion_id") == fermentacion_id]
        if resource=="lecturas":
            records.sort(key=lambda x:x["timestamp"])
        return records[-limit:]
    params: dict[str,str] = {"select":"*", "limit":str(limit)}
    if fermentacion_id is not None:
        if resource not in {"alertas", "lecturas", "intervenciones", "umbrales"}:
            raise HTTPException(400, "Filtro no disponible.")
        params["fermentacion_id"] = f"eq.{fermentacion_id}"
    if resource == "lecturas":
        params["order"]="timestamp.desc"
    elif resource == "alertas":
        params["order"]="timestamp.desc"
    data = await supabase_request("GET", TABLE_MAP[resource], authorization, params=params)
    if resource == "lecturas": data.reverse()
    return data

# Demo-only business rules enforce the important cross-table requirements.
def validate_demo(resource: str, data: dict[str, Any]):
    if resource=="empresas":
        if not data.get("nomb_emp") or any(e["nomb_emp"]==data["nomb_emp"] for e in DEMO_DB["empresas"]):raise HTTPException(409,"Nombre de empresa faltante o duplicado.")
    elif resource=="usuarios_bodega":
        user=next((u for u in DEMO_DB["usuarios"] if u["id"]==data.get("usuario_id")),None)
        bodega=next((b for b in DEMO_DB["bodegas"] if b["id"]==data.get("bodega_id")),None)
        if not user or not bodega or user["empresa_id"]!=bodega["empresa_id"]:raise HTTPException(422,"El usuario y la bodega deben pertenecer a la misma empresa.")
    elif resource=="cubas":
        if float(data.get("cap_litros",0))<=0: raise HTTPException(422,"La capacidad debe ser mayor a cero.")
        if not any(b["id"]==int(data.get("bodega_id",0)) for b in DEMO_DB["bodegas"]): raise HTTPException(422,"La bodega no existe.")
        if any(c["codigo"]==data.get("codigo") and c["bodega_id"]==data.get("bodega_id") for c in DEMO_DB["cubas"]): raise HTTPException(409,"Código de cuba duplicado en la bodega.")
    elif resource=="fermentaciones":
        cuba = next((c for c in DEMO_DB["cubas"] if c["id"]==data.get("cuba_id")),None)
        perfil = next((p for p in DEMO_DB["perfiles"] if p["id"]==data.get("perfil_id")),None)
        if not cuba or not perfil or cuba["bodega_id"]!=perfil["bodega_id"] or not perfil.get("activo"):
            raise HTTPException(422,"La cuba y el perfil deben ser válidos y pertenecer a la misma bodega.")
        if cuba["estado_operativo"]!="disponible":raise HTTPException(409,"La cuba no está disponible.")
        volume=float(data.get("volumen_litros",0))
        if volume<=0 or volume>float(cuba["cap_litros"]):raise HTTPException(422,"Volumen inválido para la capacidad de la cuba.")
        if any(f["cuba_id"]==cuba["id"] and f["estado"]=="en curso" for f in DEMO_DB["fermentaciones"]):raise HTTPException(409,"La cuba ya tiene una fermentación activa.")
        if data.get("fecha_estimada_fin","")<=data.get("fecha_inicio",""): raise HTTPException(422,"La fecha estimada debe ser posterior al inicio.")
        cuba["estado_operativo"]="en uso"
    elif resource=="asignaciones":
        device = next((d for d in DEMO_DB["dispositivos"] if d["id"]==data.get("dispositivo_id")),None)
        cuba = next((c for c in DEMO_DB["cubas"] if c["id"]==data.get("cuba_id")),None)
        bodega = next((b for b in DEMO_DB["bodegas"] if cuba and b["id"]==cuba["bodega_id"]),None)
        if not device or not bodega or device["empresa_id"]!=bodega["empresa_id"]:raise HTTPException(422,"Dispositivo y cuba de empresas distintas o inexistentes.")
        if any(a["dispositivo_id"]==device["id"] and a["activo"] for a in DEMO_DB["asignaciones"]):raise HTTPException(409,"Dispositivo ya asignado.")
    elif resource=="perfiles":
        mn,mx=float(data.get("temp_min",0)),float(data.get("temp_max",0))
        phmn,phmx=float(data.get("ph_min",0)),float(data.get("ph_max",0))
        if mn>mx or phmn>phmx or phmn<0 or phmx>14: raise HTTPException(422,"Umbrales de temperatura o pH inconsistentes.")
    elif resource=="intervenciones":
        if not data.get("tipo_intervencion") or not data.get("descripcion") or not data.get("dosis_aplicada"):
            raise HTTPException(422,"Tipo, descripción y dosis son obligatorios.")
        if not any(f["id"]==data.get("fermentacion_id") for f in DEMO_DB["fermentaciones"]):raise HTTPException(422,"Fermentación inexistente.")
    elif resource=="dispositivos":
        if any(d["mac_address"]==data.get("mac_address") for d in DEMO_DB["dispositivos"]):raise HTTPException(409,"MAC ya registrada.")

@app.post("/api/{resource}", status_code=201)
async def create_record(resource: str, body: NewEntity, authorization: str | None = Header(None)):
    if resource not in WRITABLE:
        raise HTTPException(405, "No está permitido crear registros de este tipo.")
    data = dict(body.data)
    allowed_fields = {
        "empresas":{"nomb_emp","email_emp","direccion_emp","activo"},
        "bodegas":{"empresa_id","nombre","direccion","valle_vitivinicola","comuna","region"},
        "cubas":{"codigo","cap_litros","sector_cuba","estado_operativo","fecha_cuba","bodega_id","material_id"},
        "dispositivos":{"mac_address","tipo_dispositivo","firmware_version","estado","empresa_id","modelo_id"},
        "asignaciones":{"dispositivo_id","cuba_id","activo","asignado_en"},
        "perfiles":{"nomb_perfil","temp_min","temp_max","brix_caida_min_dia","ph_min","ph_max","activo","bodega_id","cepa_id"},
        "fermentaciones":{"cuba_id","perfil_id","volumen_litros","brix_inicial","brix_objetivo","densidad_inicial_sg","estado","fecha_inicio","fecha_estimada_fin"},
        "intervenciones":{"fermentacion_id","usuario_id","tipo_intervencion","descripcion","dosis_aplicada"},
        "usuarios_bodega":{"usuario_id","bodega_id","rol_id"}
    }
    if set(data)-allowed_fields[resource]:raise HTTPException(422,"El formulario contiene campos no permitidos.")
    if DEMO_MODE:
        validate_demo(resource,data)
        data["id"] = demo_new_id(resource)
        if resource=="intervenciones":data["fecha_registro"]=now()
        if resource=="fermentaciones":
            data["estado"]="en curso"; data["fecha_real_fin"]=None; data["creado_en"]=now()
        if resource=="asignaciones":data.update({"activo":True,"asignado_en":now(),"desasignado_en":None})
        if resource=="usuarios_bodega":data["asignado_en"]=now()
        if resource=="bodegas":data["creado_en"]=now()
        if resource=="usuarios_bodega":
            DEMO_DB[resource]=[r for r in DEMO_DB[resource] if not (r["usuario_id"]==data["usuario_id"] and r["bodega_id"]==data["bodega_id"])]
        DEMO_DB[resource].append(data)
        return {"record":data, "demo":True}
    # Nunca se confía en un client company-id: RLS y CHECK en Supabase deben validar pertenencia.
    if resource=="intervenciones":
        # Nunca aceptar usuario_id proporcionado por el navegador en modo real.
        data.pop("usuario_id",None)
        return {"record":await supabase_request("POST","rpc/mosto_registrar_intervencion",authorization,json_data={"p_fermentacion_id":data.get("fermentacion_id"),"p_tipo":data.get("tipo_intervencion"),"p_descripcion":data.get("descripcion"),"p_dosis":data.get("dosis_aplicada")}),"demo":False}
    records = await supabase_request("POST", TABLE_MAP[resource], authorization, json_data=data, prefer="return=representation")
    return {"record":records[0] if records else {},"demo":False}

@app.post("/api/alertas/{alert_id}/atender")
async def attend_alert(alert_id: int, authorization: str | None = Header(None)):
    if DEMO_MODE:
        a = next((r for r in DEMO_DB["alertas"] if r["id"]==alert_id),None)
        if not a:raise HTTPException(404,"Alerta inexistente.")
        if a["estado"]!="pendiente":raise HTTPException(409,"Solo las alertas pendientes se pueden atender.")
        a.update({"estado":"atendida","atendida_por":2,"fecha_atencion":now()})
        return a
    # RLS + función RPC atómica del lado DB. Requiere ejecutar backend/sql/mosto_rpc.sql.
    return await supabase_request("POST", "rpc/mosto_atender_alerta", authorization, json_data={"p_alerta_id":alert_id})

@app.post("/api/alertas/{alert_id}/resolver")
async def resolve_alert(alert_id: int, body: PatchAlert, authorization: str | None = Header(None)):
    if not body.nota or not body.nota.strip():raise HTTPException(422,"La resolución requiere una nota.")
    if DEMO_MODE:
        a = next((r for r in DEMO_DB["alertas"] if r["id"]==alert_id),None)
        if not a:raise HTTPException(404,"Alerta inexistente.")
        if a["estado"]!="atendida":raise HTTPException(409,"Primero debes atender la alerta.")
        a.update({"estado":"resuelta","resolucion_nota":body.nota.strip()})
        return a
    return await supabase_request("POST", "rpc/mosto_resolver_alerta", authorization, json_data={"p_alerta_id":alert_id,"p_nota":body.nota.strip()})

@app.post("/api/fermentaciones/{fermentation_id}/cerrar")
async def close_fermentation(fermentation_id: int, body: CloseFermentation, authorization: str | None = Header(None)):
    if body.estado not in {"finalizada","detenida","cancelada"}:raise HTTPException(422,"Estado de cierre inválido.")
    if DEMO_MODE:
        f = next((r for r in DEMO_DB["fermentaciones"] if r["id"]==fermentation_id),None)
        if not f:raise HTTPException(404,"Fermentación inexistente.")
        if f["estado"]!="en curso":raise HTTPException(409,"La fermentación ya está cerrada.")
        f.update({"estado":body.estado,"fecha_real_fin":now()})
        cuba = next(c for c in DEMO_DB["cubas"] if c["id"]==f["cuba_id"])
        cuba["estado_operativo"]="disponible"
        return f
    return await supabase_request("POST","rpc/mosto_cerrar_fermentacion",authorization,json_data={"p_fermentacion_id":fermentation_id,"p_estado":body.estado})

@app.get("/api/exportaciones/lecturas.csv")
async def export_readings(fermentacion_id: int, authorization: str | None = Header(None)):
    if DEMO_MODE:
        data=[r for r in DEMO_DB["lecturas"] if r["fermentacion_id"]==fermentacion_id and r["lectura_valida"]]
    else:
        data=await supabase_request("GET", TABLE_MAP["lecturas"], authorization, params={"select":"*","fermentacion_id":f"eq.{fermentacion_id}","lectura_valida":"eq.true", "order":"timestamp.asc","limit":"5000"})
    cols=["timestamp","dispositivo_id","temp_mosto","temp_ambiente","densidad_sg","brix","ph","origen_dato"]
    buf=StringIO(); writer=csv.DictWriter(buf,fieldnames=cols,extrasaction="ignore");writer.writeheader();writer.writerows(data)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f"attachment; filename=mosto-fermentacion-{fermentacion_id}.csv"})


class UpdateStatus(BaseModel):
    estado: str

@app.patch("/api/cubas/{cuba_id}/estado")
async def update_cuba_status(cuba_id:int, body:UpdateStatus, authorization:str|None=Header(None)):
    valid={"disponible","en uso","mantención","fuera de servicio"}
    if body.estado not in valid:raise HTTPException(422,"Estado de cuba inválido.")
    if DEMO_MODE:
        cuba=next((c for c in DEMO_DB["cubas"] if c["id"]==cuba_id),None)
        if not cuba:raise HTTPException(404,"Cuba no encontrada.")
        if any(f["cuba_id"]==cuba_id and f["estado"]=="en curso" for f in DEMO_DB["fermentaciones"]):raise HTTPException(409,"No puedes cambiar el estado de una cuba con fermentación en curso.")
        cuba["estado_operativo"]=body.estado
        return cuba
    return await supabase_request("PATCH",TABLE_MAP["cubas"],authorization,params={"id":f"eq.{cuba_id}"},json_data={"estado_operativo":body.estado},prefer="return=representation")

@app.post("/api/asignaciones/{assignment_id}/desasignar")
async def unassign_device(assignment_id:int, authorization:str|None=Header(None)):
    if DEMO_MODE:
        entry=next((a for a in DEMO_DB["asignaciones"] if a["id"]==assignment_id),None)
        if not entry:raise HTTPException(404,"Asignación no encontrada.")
        if not entry["activo"]:raise HTTPException(409,"Asignación ya inactiva.")
        entry.update({"activo":False,"desasignado_en":now()})
        return entry
    return await supabase_request("POST","rpc/mosto_desasignar_dispositivo",authorization,json_data={"p_asignacion_id":assignment_id})

# Integración del prototipo IoT (HU-23, HU-24, HU-27).
# DEMO: clave sintética para pruebas aisladas; NO es credencial de producción.
# LIVE: la ingesta se bloquea hasta desplegar autenticación individual revocable (HU-39).
import hmac
from datetime import datetime as DateTime, timedelta

class NewTelemetry(BaseModel):
    dispositivo_id: int = Field(gt=0)
    timestamp: DateTime
    temp_mosto: float | None = None
    temp_ambiente: float | None = None
    densidad_sg: float | None = Field(default=None, ge=0)
    brix: float | None = Field(default=None, ge=0)
    ph: float | None = Field(default=None, ge=0, le=14)

class NewNodeState(BaseModel):
    dispositivo_id: int = Field(gt=0)
    timestamp: DateTime
    bateria_pct: int = Field(ge=0, le=100)
    bateria_volt: float = Field(ge=0)
    rssi_dbm: int = Field(le=0)
    estado_red: str


def check_demo_device(device_id:int, secret:str|None):
    expected=f"mosto-demo-dispositivo-{device_id}"
    if not secret or not hmac.compare_digest(expected,secret):
        raise HTTPException(401,"Credencial de demostración inválida para el dispositivo.")
    device=next((d for d in DEMO_DB["dispositivos"] if d["id"]==device_id),None)
    if not device or device["estado"]!="activo":
        raise HTTPException(403,"Dispositivo no registrado o inactivo.")
    return device


def block_real_ingestion():
    if not DEMO_MODE:
        raise HTTPException(501,"Ingesta IoT real deshabilitada hasta implementar credenciales individuales revocables, validación de pertenencia y transacción de alertas en el servidor (HU-39).")

@app.post("/api/iot/lecturas",status_code=201)
def ingest_reading(payload:NewTelemetry, x_device_key:str|None=Header(None)):
    block_real_ingestion()
    check_demo_device(payload.dispositivo_id,x_device_key)
    a=next((x for x in DEMO_DB["asignaciones"] if x["dispositivo_id"]==payload.dispositivo_id and x["activo"]),None)
    if not a:raise HTTPException(422,"El dispositivo no está asignado a ninguna cuba.")
    f=next((f for f in DEMO_DB["fermentaciones"] if f["cuba_id"]==a["cuba_id"] and f["estado"]=="en curso"),None)
    if not f:raise HTTPException(422,"No existe una fermentación en curso asociada a la cuba.")
    if payload.timestamp.tzinfo is None:raise HTTPException(422,"timestamp debe incluir zona horaria.")
    stamp=payload.timestamp.isoformat()
    if any(r["dispositivo_id"]==payload.dispositivo_id and DateTime.fromisoformat(r["timestamp"])==payload.timestamp for r in DEMO_DB["lecturas"]):
        raise HTTPException(409,"Lectura duplicada para ese dispositivo e instante.")
    if all(v is None for v in (payload.temp_mosto,payload.temp_ambiente,payload.densidad_sg,payload.brix,payload.ph)):
        raise HTTPException(422,"Se requiere al menos una variable medida.")
    reading={"id":demo_new_id("lecturas"),"dispositivo_id":payload.dispositivo_id,"fermentacion_id":f["id"],"timestamp":stamp,"temp_mosto":payload.temp_mosto,"temp_ambiente":payload.temp_ambiente,"densidad_sg":payload.densidad_sg,"brix":payload.brix,"ph":payload.ph,"origen_dato":"dispositivo","lectura_valida":True}
    DEMO_DB["lecturas"].append(reading)
    profile=next(p for p in DEMO_DB["perfiles"] if p["id"]==f["perfil_id"])
    thresholds=next((u for u in DEMO_DB["umbrales"] if u["fermentacion_id"]==f["id"]),{})
    new_alerts=[]
    for field, low, high in (("temp_mosto","temp_min","temp_max"),("ph","ph_min","ph_max")):
        value=getattr(payload,field)
        if value is None:continue
        lower=thresholds.get(low) if thresholds.get(low) is not None else profile[low]
        upper=thresholds.get(high) if thresholds.get(high) is not None else profile[high]
        if lower<=value<=upper:continue
        issue=f"{field}_{'alta' if value>upper else 'baja'}"
        if any(x["fermentacion_id"]==f["id"] and x["tipo_alerta"]==issue and x["estado"]=='pendiente' for x in DEMO_DB["alertas"]):continue
        boundary=upper if value>upper else lower
        severity="alta" if abs(value-boundary)>1 else "media"
        alert={"id":demo_new_id("alertas"),"dispositivo_id":payload.dispositivo_id,"fermentacion_id":f["id"],"atendida_por":None,"timestamp":stamp,"tipo_alerta":issue,"severidad":severity,"met_dispar":field,"valor_registrado":value,"valor_limite":boundary,"mensaje":f"{field} fuera del rango permitido ({lower}–{upper}).","estado":"pendiente","fecha_atencion":None,"resolucion_nota":None}
        DEMO_DB["alertas"].append(alert);new_alerts.append(alert)
    # HU-27: comprobar la caída diaria de °Brix si existe una medición comparable
    # 18-30 horas antes; sin suficiente historia no se inventa la tasa.
    if payload.brix is not None:
        prior = [r for r in DEMO_DB["lecturas"] if r["fermentacion_id"]==f["id"]
                 and r["id"]!=reading["id"] and r["brix"] is not None
                 and 18 <= (payload.timestamp - DateTime.fromisoformat(r["timestamp"])).total_seconds()/3600 <= 30]
        if prior:
            reference=min(prior,key=lambda r:abs((payload.timestamp-DateTime.fromisoformat(r["timestamp"])).total_seconds()-86400))
            days=(payload.timestamp-DateTime.fromisoformat(reference["timestamp"])).total_seconds()/86400
            daily_drop=(reference["brix"]-payload.brix)/days
            minimum=thresholds.get("brix_caida_min_dia") if thresholds.get("brix_caida_min_dia") is not None else profile["brix_caida_min_dia"]
            if daily_drop < minimum and not any(a["fermentacion_id"]==f["id"] and a["tipo_alerta"]=="caida_brix" and a["estado"]=="pendiente" for a in DEMO_DB["alertas"]):
                alert={"id":demo_new_id("alertas"),"dispositivo_id":payload.dispositivo_id,"fermentacion_id":f["id"],"atendida_por":None,"timestamp":stamp,"tipo_alerta":"caida_brix","severidad":"media","met_dispar":"brix_caida_min_dia","valor_registrado":round(daily_drop,3),"valor_limite":minimum,"mensaje":"La caída diaria de °Brix es inferior al mínimo del perfil.","estado":"pendiente","fecha_atencion":None,"resolucion_nota":None}
                DEMO_DB["alertas"].append(alert);new_alerts.append(alert)
    return {"lectura":reading,"alertas_generadas":new_alerts,"modo":"demostracion"}

@app.post("/api/iot/estado",status_code=201)
def ingest_node_state(payload:NewNodeState,x_device_key:str|None=Header(None)):
    block_real_ingestion()
    check_demo_device(payload.dispositivo_id,x_device_key)
    if payload.timestamp.tzinfo is None:raise HTTPException(422,"timestamp debe incluir zona horaria.")
    if any(x["dispositivo_id"]==payload.dispositivo_id and DateTime.fromisoformat(x["timestamp"])==payload.timestamp for x in DEMO_DB["estados_nodo"]):raise HTTPException(409,"Estado de nodo duplicado.")
    row={"id":demo_new_id("estados_nodo"),**payload.model_dump(),"timestamp":payload.timestamp.isoformat()}
    DEMO_DB["estados_nodo"].append(row)
    return {"estado":row,"modo":"demostracion"}
