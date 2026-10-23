"""Conjunto ficticio SOLO para DEMO_MODE. Nunca mezclar con la base real."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import math

UTC = timezone.utc
BASE = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)

def iso(d):
    return d.isoformat()

def create_seed():
    db = {
        "empresas": [{"id": 1, "nomb_emp": "Viña Los Aromos", "email_emp":"contacto@ejemplo.invalid","activo":True}],
        "bodegas": [
            {"id": 1,"empresa_id":1,"nombre":"Bodega Principal","direccion":"Valle del Maipo","valle_vitivinicola":"Maipo","comuna":"Paine","region":"Metropolitana","creado_en":iso(BASE)},
            {"id": 2,"empresa_id":1,"nombre":"Bodega Cordillera","direccion":"Valle de Casablanca","valle_vitivinicola":"Casablanca","comuna":"Casablanca","region":"Valparaíso","creado_en":iso(BASE)},
        ],
        "cepas": [{"id":1,"tipo_uva":"tinta","nombre_variedad":"Cabernet Sauvignon"},{"id":2,"tipo_uva":"tinta","nombre_variedad":"Carménère"},{"id":3,"tipo_uva":"blanca","nombre_variedad":"Sauvignon Blanc"}],
        "materiales": [{"id":1,"nombre":"Acero inoxidable"},{"id":2,"nombre":"Hormigón"},{"id":3,"nombre":"Roble"}],
        "modelos": [{"id":1,"marca":"Mosto","modelo":"Nodo M1","arquitectura":"ESP32","version_hardware":"1.0"}],
        "roles": [{"id":1,"codigo":"ADMIN","descripcion":"Administrador"},{"id":2,"codigo":"ENOLOGO","descripcion":"Enólogo"},{"id":3,"codigo":"OPERADOR","descripcion":"Operador"}],
        "usuarios": [{"id":1,"nomb_comp":"Camila Torres","correo_elec":"camila@ejemplo.invalid","telefono":"","activo":True,"empresa_id":1},{"id":2,"nomb_comp":"Diego Rojas","correo_elec":"diego@ejemplo.invalid","telefono":"","activo":True,"empresa_id":1},{"id":3,"nomb_comp":"Sofía Pérez","correo_elec":"sofia@ejemplo.invalid","telefono":"","activo":True,"empresa_id":1}],
        "usuarios_bodega": [{"id":1,"usuario_id":1,"bodega_id":1,"rol_id":1,"asignado_en":iso(BASE)},{"id":2,"usuario_id":2,"bodega_id":1,"rol_id":2,"asignado_en":iso(BASE)},{"id":3,"usuario_id":3,"bodega_id":1,"rol_id":3,"asignado_en":iso(BASE)},{"id":4,"usuario_id":2,"bodega_id":2,"rol_id":2,"asignado_en":iso(BASE)}],
        "cubas": [
            {"id":1,"codigo":"CU-001","cap_litros":12000,"sector_cuba":"Nave Norte","estado_operativo":"en uso","fecha_cuba":"2024-02-10","bodega_id":1,"material_id":1},
            {"id":2,"codigo":"CU-002","cap_litros":8500,"sector_cuba":"Nave Norte","estado_operativo":"en uso","fecha_cuba":"2023-08-10","bodega_id":1,"material_id":1},
            {"id":3,"codigo":"CU-003","cap_litros":6000,"sector_cuba":"Nave Sur","estado_operativo":"disponible","fecha_cuba":"2024-01-20","bodega_id":1,"material_id":2},
            {"id":4,"codigo":"CU-004","cap_litros":9500,"sector_cuba":"Sala A","estado_operativo":"en uso","fecha_cuba":"2024-02-12","bodega_id":2,"material_id":1},
            {"id":5,"codigo":"CU-005","cap_litros":5000,"sector_cuba":"Sala A","estado_operativo":"mantención","fecha_cuba":"2022-11-12","bodega_id":2,"material_id":3},
            {"id":6,"codigo":"CU-006","cap_litros":7500,"sector_cuba":"Sala B","estado_operativo":"disponible","fecha_cuba":"2024-04-12","bodega_id":2,"material_id":1},
        ],
        "dispositivos": [
            {"id":1,"mac_address":"A4:CF:12:2A:91:01","tipo_dispositivo":"multisensor","firmware_version":"1.2.1","estado":"activo","empresa_id":1,"modelo_id":1,"creado_en":iso(BASE)},
            {"id":2,"mac_address":"A4:CF:12:2A:91:02","tipo_dispositivo":"multisensor","firmware_version":"1.2.1","estado":"activo","empresa_id":1,"modelo_id":1,"creado_en":iso(BASE)},
            {"id":3,"mac_address":"A4:CF:12:2A:91:03","tipo_dispositivo":"multisensor","firmware_version":"1.1.8","estado":"activo","empresa_id":1,"modelo_id":1,"creado_en":iso(BASE)},
            {"id":4,"mac_address":"A4:CF:12:2A:91:04","tipo_dispositivo":"multisensor","firmware_version":"1.1.8","estado":"inactivo","empresa_id":1,"modelo_id":1,"creado_en":iso(BASE)},
        ],
        "asignaciones": [{"id":1,"dispositivo_id":1,"cuba_id":1,"activo":True,"asignado_en":iso(BASE-timedelta(days=12)),"desasignado_en":None},{"id":2,"dispositivo_id":2,"cuba_id":2,"activo":True,"asignado_en":iso(BASE-timedelta(days=8)),"desasignado_en":None},{"id":3,"dispositivo_id":3,"cuba_id":4,"activo":True,"asignado_en":iso(BASE-timedelta(days=5)),"desasignado_en":None}],
        "perfiles": [
            {"id":1,"nomb_perfil":"Cabernet · Control clásico","temp_min":20,"temp_max":27,"brix_caida_min_dia":0.8,"ph_min":3.2,"ph_max":3.9,"activo":True,"bodega_id":1,"cepa_id":1},
            {"id":2,"nomb_perfil":"Carménère · Fermentación lenta","temp_min":19,"temp_max":25,"brix_caida_min_dia":0.6,"ph_min":3.1,"ph_max":3.8,"activo":True,"bodega_id":1,"cepa_id":2},
            {"id":3,"nomb_perfil":"Sauvignon · Baja temperatura","temp_min":12,"temp_max":19,"brix_caida_min_dia":0.5,"ph_min":3.0,"ph_max":3.7,"activo":True,"bodega_id":2,"cepa_id":3},
        ],
        "fermentaciones": [
            {"id":1,"cuba_id":1,"perfil_id":1,"volumen_litros":10400,"brix_inicial":24.8,"brix_objetivo":2.0,"densidad_inicial_sg":1.100,"estado":"en curso","fecha_inicio":iso(BASE-timedelta(days=8)),"fecha_estimada_fin":iso(BASE+timedelta(days=6)),"fecha_real_fin":None,"creado_en":iso(BASE)},
            {"id":2,"cuba_id":2,"perfil_id":2,"volumen_litros":7500,"brix_inicial":23.5,"brix_objetivo":2.5,"densidad_inicial_sg":1.094,"estado":"en curso","fecha_inicio":iso(BASE-timedelta(days=5)),"fecha_estimada_fin":iso(BASE+timedelta(days=8)),"fecha_real_fin":None,"creado_en":iso(BASE)},
            {"id":3,"cuba_id":4,"perfil_id":3,"volumen_litros":8200,"brix_inicial":20.4,"brix_objetivo":1.8,"densidad_inicial_sg":1.085,"estado":"en curso","fecha_inicio":iso(BASE-timedelta(days=4)),"fecha_estimada_fin":iso(BASE+timedelta(days=7)),"fecha_real_fin":None,"creado_en":iso(BASE)},
        ],
        "umbrales": [{"id":1,"fermentacion_id":1,"establecido_por":2,"temp_min":20,"temp_max":26,"brix_caida_min_dia":None,"ph_min":None,"ph_max":None,"actualizado_en":iso(BASE-timedelta(days=1))}],
        "alertas": [
            {"id":1,"dispositivo_id":2,"fermentacion_id":2,"atendida_por":None,"timestamp":iso(BASE-timedelta(minutes=16)),"tipo_alerta":"temperatura_alta","severidad":"alta","met_dispar":"temp_mosto","valor_registrado":26.4,"valor_limite":25.0,"mensaje":"Temperatura por encima del umbral definido para Carménère.","estado":"pendiente","fecha_atencion":None,"resolucion_nota":None},
            {"id":2,"dispositivo_id":3,"fermentacion_id":3,"atendida_por":None,"timestamp":iso(BASE-timedelta(minutes=52)),"tipo_alerta":"caida_brix","severidad":"media","met_dispar":"brix_caida_min_dia","valor_registrado":0.3,"valor_limite":0.5,"mensaje":"La caída diaria de °Brix es inferior al mínimo esperado.","estado":"pendiente","fecha_atencion":None,"resolucion_nota":None},
            {"id":3,"dispositivo_id":1,"fermentacion_id":1,"atendida_por":2,"timestamp":iso(BASE-timedelta(days=2)),"tipo_alerta":"temperatura_alta","severidad":"media","met_dispar":"temp_mosto","valor_registrado":27.8,"valor_limite":27.0,"mensaje":"Se registró una desviación de temperatura, corregida.","estado":"resuelta","fecha_atencion":iso(BASE-timedelta(days=2,hours=-1)),"resolucion_nota":"Se ajustó el circuito de refrigeración."},
        ],
        "intervenciones": [
            {"id":1,"fermentacion_id":1,"usuario_id":3,"fecha_registro":iso(BASE-timedelta(days=3)),"tipo_intervencion":"Control de temperatura","descripcion":"Se ajustó el sistema de enfriamiento de la cuba.","dosis_aplicada":"N/A"},
            {"id":2,"fermentacion_id":2,"usuario_id":2,"fecha_registro":iso(BASE-timedelta(days=1)),"tipo_intervencion":"Adición de nutrientes","descripcion":"Se agregaron nutrientes según el protocolo de la bodega.","dosis_aplicada":"2 kg"},
        ],
        "estados_nodo": [],"lecturas": [],
    }
    for d, battery, signal in [(1,91,-60),(2,78,-66),(3,64,-73),(4,12,-96)]:
        db["estados_nodo"].append({"id":d,"dispositivo_id":d,"timestamp":iso(BASE-timedelta(minutes=8 if d!=4 else 320)),"bateria_pct":battery,"bateria_volt":round(3.2+battery/110,2),"rssi_dbm":signal,"estado_red":"conectado" if d!=4 else "desconectado"})
    for idx,(fid,did,start,base,brix_start) in enumerate([(1,1,24,23.5,14.7),(2,2,26,25.1,18.1),(3,3,20,16.3,17.1)]):
        for i in range(25):
            t = BASE-timedelta(hours=24-i)
            temp = round(base + 0.9*math.sin(i/3.5) + (0.7 if fid==2 and i>17 else 0),2)
            brix = round(max(0,brix_start - i*(0.052 if fid==1 else 0.026)),2)
            ph = round((3.45 if fid!=3 else 3.26)+0.04*math.sin(i/6),2)
            db["lecturas"].append({"id":len(db["lecturas"])+1,"dispositivo_id":did,"fermentacion_id":fid,"timestamp":iso(t),"temp_mosto":temp,"temp_ambiente":round(temp-2.4,2),"densidad_sg":round(1.01+brix*0.003,4),"brix":brix,"ph":ph,"origen_dato":"dispositivo","lectura_valida":True})
    return db
