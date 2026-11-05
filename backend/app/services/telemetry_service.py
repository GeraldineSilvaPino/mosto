"""
Servicio de Telemetría y Calibración Física (MOSTO)
Equivalente a la capa @Service en Spring Boot.

Contiene la lógica de negocio pura:
- Fórmulas de conversión física para sensores (pH, Inclinación -> Brix, Batería, Wi-Fi).
- Orquestación con la base de datos (Entidades LECTURA_TELEMETRIA, DISPOSITIVO, ESTADO_NODO, CUBA, PROCESO_FERMENTACION).
- Cumple al 100% las restricciones NOT NULL y Triggers de integridad de Supabase.
"""
import math
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    EmpresaCliente,
    Bodega,
    TipoMaterialCuba,
    Cepa,
    Cuba,
    PerfilFermentacion,
    ModeloDispositivo,
    Dispositivo,
    AsignacionDispositivo,
    ProcesoFermentacion,
    LecturaTelemetria,
    TelemetriaEstadoNodo
)
from app.schemas import (
    TelemetriaESP32In,
    TelemetriaESP8266In,
    TelemetriaRespuestaOut,
    TelemetriaProcesadaOut
)
from app.services.rules_engine import rules_engine


class TelemetryService:
    """
    Servicio encargado de calibrar tramas de hardware y persistirlas.
    """

    TILT_ANGULO_AGUA_CERO_BRIX = 25.0
    FACTOR_TILT_A_BRIX = 0.60
    VOLTAJE_NEUTRO_PH7 = 2.50
    FACTOR_SENSIBILIDAD_PH = 0.18

    @staticmethod
    def calibrar_ph(voltaje_ph: Optional[float], ph_directo: Optional[float]) -> Optional[float]:
        """Calcula el pH a partir del voltaje analógico de la sonda PH-4502C."""
        if ph_directo is not None:
            return round(max(0.0, min(14.0, float(ph_directo))), 2)

        if voltaje_ph is not None:
            ph_calculado = 7.0 - ((voltaje_ph - TelemetryService.VOLTAJE_NEUTRO_PH7) / TelemetryService.FACTOR_SENSIBILIDAD_PH)
            return round(max(1.0, min(14.0, ph_calculado)), 2)

        return None

    @staticmethod
    def calcular_brix_y_densidad(
        angulo_tilt: Optional[float],
        ax: Optional[float] = None,
        ay: Optional[float] = None,
        az: Optional[float] = None,
        brix_directo: Optional[float] = None,
        sg_directo: Optional[float] = None
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calcula inclinación, °Brix y Gravedad Específica (SG) desde el MPU-6050."""
        tilt = angulo_tilt
        if tilt is None and ax is not None and ay is not None and az is not None:
            if az != 0:
                magnitud_plano = math.sqrt(ax * ax + ay * ay)
                tilt = round(math.atan2(magnitud_plano, az) * 180.0 / math.pi, 2)

        if brix_directo is not None:
            brix = round(float(brix_directo), 2)
            sg = sg_directo or round(1.0000 + (brix * 0.00385), 4)
            return tilt, brix, sg

        if tilt is not None:
            delta_angulo = max(0.0, tilt - TelemetryService.TILT_ANGULO_AGUA_CERO_BRIX)
            brix_estimado = round(delta_angulo * TelemetryService.FACTOR_TILT_A_BRIX, 2)
            brix_estimado = min(35.0, brix_estimado)
            sg_estimado = round(1.0000 + (brix_estimado * 0.0039), 4)
            return tilt, brix_estimado, sg_estimado

        return None, None, None

    @staticmethod
    def calcular_bateria(voltaje: Optional[float]) -> Tuple[Optional[int], Optional[float]]:
        """Convierte voltaje Li-Po (3.3V a 4.2V) a porcentaje (0 a 100%)."""
        if voltaje is None:
            return None, None
        volt = round(float(voltaje), 2)
        pct = int(max(0, min(100, (volt - 3.30) / (4.20 - 3.30) * 100)))
        return pct, volt

    @staticmethod
    def clasificar_wifi(rssi: Optional[int]) -> Optional[str]:
        """Clasifica la cobertura de señal en dBm."""
        if rssi is None:
            return None
        if rssi >= -60:
            return "Excelente"
        if rssi >= -75:
            return "Buena"
        if rssi >= -85:
            return "Regular"
        return "Débil"

    def _obtener_o_crear_empresa_y_bodega(self, db: Session) -> Tuple[EmpresaCliente, Bodega]:
        empresa = db.query(EmpresaCliente).first()
        if not empresa:
            empresa = EmpresaCliente(
                nomb_emp="Viña MOSTO Chile",
                email_emp="contacto@mosto.cl",
                direccion_emp="Valle del Maipo, Chile",
                activo=True
            )
            db.add(empresa)
            db.commit()
            db.refresh(empresa)

        bodega = db.query(Bodega).first()
        if not bodega:
            bodega = Bodega(
                nombre="Bodega Principal",
                direccion="Sector Las Cubas s/n",
                empresa_id=empresa.id,
                valle_vitivinicola="Valle del Maipo",
                comuna="Buin",
                region="Metropolitana"
            )
            db.add(bodega)
            db.commit()
            db.refresh(bodega)

        return empresa, bodega

    def _obtener_o_crear_modelo_dispositivo(self, db: Session, tipo: str) -> ModeloDispositivo:
        nombre_modelo = "ESP32-WROOM-32" if "ESP32" in tipo else "ESP8266-12F"
        modelo = db.query(ModeloDispositivo).filter(ModeloDispositivo.modelo == nombre_modelo).first()
        if not modelo:
            modelo = ModeloDispositivo(
                marca="Espressif Systems",
                modelo=nombre_modelo,
                arquitectura="Xtensa" if "ESP32" in tipo else "Tensilica L106",
                version_hardware="v1.0"
            )
            db.add(modelo)
            db.commit()
            db.refresh(modelo)
        return modelo

    def _obtener_o_crear_material_cuba(self, db: Session) -> TipoMaterialCuba:
        mat = db.query(TipoMaterialCuba).first()
        if not mat:
            mat = TipoMaterialCuba(nombre="Acero Inoxidable AISI 304")
            db.add(mat)
            db.commit()
            db.refresh(mat)
        return mat

    def _obtener_o_crear_cepa(self, db: Session) -> Cepa:
        cepa = db.query(Cepa).first()
        if not cepa:
            cepa = Cepa(
                tipo_uva="Tinto",
                nombre_variedad="Cabernet Sauvignon"
            )
            db.add(cepa)
            db.commit()
            db.refresh(cepa)
        return cepa

    def _obtener_o_crear_perfil(self, db: Session, bodega_id: int) -> PerfilFermentacion:
        perfil = db.query(PerfilFermentacion).filter(PerfilFermentacion.bodega_id == bodega_id).first()
        if not perfil:
            cepa = self._obtener_o_crear_cepa(db)
            perfil = PerfilFermentacion(
                nomb_perfil="Cabernet Sauvignon Tradicional",
                temp_min=16.0,
                temp_max=26.0,
                brix_caida_min_dia=1.5,
                ph_min=3.10,
                ph_max=3.80,
                activo=True,
                bodega_id=bodega_id,
                cepa_id=cepa.id
            )
            db.add(perfil)
            db.commit()
            db.refresh(perfil)
        return perfil

    def _obtener_o_crear_dispositivo(self, db: Session, mac_address: str, tipo_sugerido: str) -> Dispositivo:
        dispositivo = db.query(Dispositivo).filter(Dispositivo.mac_address == mac_address).first()
        if not dispositivo:
            empresa, _ = self._obtener_o_crear_empresa_y_bodega(db)
            modelo = self._obtener_o_crear_modelo_dispositivo(db, tipo_sugerido)
            dispositivo = Dispositivo(
                mac_address=mac_address,
                tipo_dispositivo=tipo_sugerido,
                firmware_version="1.0.0-ino",
                estado="activo",
                empresa_id=empresa.id,
                modelo_id=modelo.id
            )
            db.add(dispositivo)
            db.commit()
            db.refresh(dispositivo)
        return dispositivo

    def _resolver_cuba_y_proceso(self, db: Session, dispositivo_id: int, cuba_id_payload: Optional[int]) -> Tuple[int, int]:
        """Resuelve a qué Cuba y Proceso de Fermentación activo corresponde la telemetría."""
        cuba_id = cuba_id_payload

        if not cuba_id:
            asignacion = db.query(AsignacionDispositivo).filter(
                AsignacionDispositivo.dispositivo_id == dispositivo_id,
                AsignacionDispositivo.activo == True
            ).first()
            if asignacion:
                cuba_id = asignacion.cuba_id
            else:
                cuba_id = 1

        _, bodega = self._obtener_o_crear_empresa_y_bodega(db)
        cuba = db.query(Cuba).filter(Cuba.id == cuba_id).first()
        if not cuba:
            material = self._obtener_o_crear_material_cuba(db)
            cuba = Cuba(
                id=cuba_id,
                codigo=f"CB-{cuba_id:02d}",
                cap_litros=10000.0,
                sector_cuba="Nave A",
                estado_operativo="en_uso",
                fecha_cuba=datetime.utcnow(),
                bodega_id=bodega.id,
                material_id=material.id
            )
            db.add(cuba)
            db.commit()
            db.refresh(cuba)

        # Verificar asignación activa (desasignado_en MUST BE NULL)
        asignacion = db.query(AsignacionDispositivo).filter(
            AsignacionDispositivo.dispositivo_id == dispositivo_id,
            AsignacionDispositivo.cuba_id == cuba.id,
            AsignacionDispositivo.activo == True
        ).first()
        if not asignacion:
            asignacion = AsignacionDispositivo(
                dispositivo_id=dispositivo_id,
                cuba_id=cuba.id,
                activo=True,
                desasignado_en=None
            )
            db.add(asignacion)
            db.commit()

        # Resolver o crear proceso activo
        proceso = db.query(ProcesoFermentacion).filter(
            ProcesoFermentacion.cuba_id == cuba.id,
            ProcesoFermentacion.estado == "en_proceso"
        ).order_by(ProcesoFermentacion.id.desc()).first()

        if not proceso:
            perfil = self._obtener_o_crear_perfil(db, bodega_id=cuba.bodega_id)
            ahora = datetime.utcnow()
            proceso = ProcesoFermentacion(
                cuba_id=cuba.id,
                perfil_id=perfil.id,
                volumen_litros=8500.0,
                brix_inicial=24.0,
                brix_objetivo=2.0,
                densidad_inicial_sg=1.0960,
                estado="en_proceso",
                fecha_inicio=ahora,
                fecha_estimada_fin=ahora + timedelta(days=14),
                creado_en=ahora
            )
            db.add(proceso)
            db.commit()
            db.refresh(proceso)

        return cuba.id, proceso.id

    def procesar_telemetria_esp32(self, db: Session, payload: TelemetriaESP32In) -> TelemetriaRespuestaOut:
        """Procesa tramas de tempsensmosto.ino (ESP32 Nodo Cuba)."""
        dispositivo = self._obtener_o_crear_dispositivo(
            db=db,
            mac_address=payload.mac_address,
            tipo_sugerido="ESP32_NODO_CUBA"
        )

        cuba_id, proceso_id = self._resolver_cuba_y_proceso(
            db=db,
            dispositivo_id=dispositivo.id,
            cuba_id_payload=payload.cuba_id
        )

        # Obtener última lectura del proceso para complementar valores no nulos
        ultima_lectura = (
            db.query(LecturaTelemetria)
            .filter(LecturaTelemetria.fermentacion_id == proceso_id)
            .order_by(desc(LecturaTelemetria.id))
            .first()
        )

        ph_final = self.calibrar_ph(payload.voltaje_ph, payload.ph)
        if ph_final is None:
            ph_final = float(ultima_lectura.ph) if ultima_lectura and ultima_lectura.ph else 3.45

        temp_amb_final = (
            round(payload.temperatura_ambiente, 2)
            if payload.temperatura_ambiente is not None
            else (float(ultima_lectura.temp_ambiente) if ultima_lectura and ultima_lectura.temp_ambiente else 20.5)
        )

        brix_final = float(ultima_lectura.brix) if ultima_lectura and ultima_lectura.brix else 23.5
        densidad_final = float(ultima_lectura.densidad_sg) if ultima_lectura and ultima_lectura.densidad_sg else 1.0920

        bateria_pct, bateria_volt = self.calcular_bateria(payload.bateria_voltaje)
        if bateria_pct is None:
            bateria_pct = 95
            bateria_volt = 4.10

        rssi_final = payload.rssi if payload.rssi is not None else -65
        calidad_wifi = self.clasificar_wifi(rssi_final)
        ahora = datetime.utcnow()

        lectura = LecturaTelemetria(
            dispositivo_id=dispositivo.id,
            fermentacion_id=proceso_id,
            timestamp=ahora,
            temp_mosto=round(payload.temperatura_vino, 2),
            temp_ambiente=temp_amb_final,
            densidad_sg=densidad_final,
            brix=brix_final,
            ph=ph_final,
            origen_dato="sensor_iot",
            lectura_valida=True
        )
        db.add(lectura)

        estado_nodo = TelemetriaEstadoNodo(
            dispositivo_id=dispositivo.id,
            timestamp=ahora,
            bateria_pct=bateria_pct,
            bateria_volt=bateria_volt,
            rssi_dbm=rssi_final,
            estado_red="conectado"
        )
        db.add(estado_nodo)

        db.commit()
        db.refresh(lectura)

        # TASK-BE-03B: Evaluación de reglas enológicas y despacho de alertas con control anti-spam
        rules_engine.procesar_alertas_lectura(
            db=db,
            lectura=lectura,
            cuba_id=cuba_id,
            dispositivo_id=dispositivo.id
        )

        return TelemetriaRespuestaOut(
            status="ok",
            mensaje="Telemetría ESP32 (Nodo Cuba) persistida y calibrada correctamente",
            lectura_id=lectura.id,
            cuba_id=cuba_id,
            proceso_id=proceso_id,
            timestamp=ahora,
            valores_procesados=TelemetriaProcesadaOut(
                temperatura_vino=round(payload.temperatura_vino, 2),
                temperatura_ambiente=temp_amb_final,
                humedad_ambiente=round(payload.humedad_ambiente, 2) if payload.humedad_ambiente is not None else None,
                ph=ph_final,
                brix=brix_final,
                densidad_sg=densidad_final,
                bateria_pct=bateria_pct,
                calidad_wifi=calidad_wifi
            )
        )

    def procesar_telemetria_esp8266(self, db: Session, payload: TelemetriaESP8266In) -> TelemetriaRespuestaOut:
        """Procesa tramas de esp86xyz.ino (ESP8266 Flotador Densímetro)."""
        dispositivo = self._obtener_o_crear_dispositivo(
            db=db,
            mac_address=payload.mac_address,
            tipo_sugerido="ESP8266_FLOTADOR"
        )

        cuba_id, proceso_id = self._resolver_cuba_y_proceso(
            db=db,
            dispositivo_id=dispositivo.id,
            cuba_id_payload=payload.cuba_id
        )

        tilt_calc, brix_calc, sg_calc = self.calcular_brix_y_densidad(
            angulo_tilt=payload.angulo_tilt,
            ax=payload.ax,
            ay=payload.ay,
            az=payload.az,
            brix_directo=payload.brix,
            sg_directo=payload.densidad_sg
        )

        # Obtener última lectura para complementar valores no nulos
        ultima_lectura = (
            db.query(LecturaTelemetria)
            .filter(LecturaTelemetria.fermentacion_id == proceso_id)
            .order_by(desc(LecturaTelemetria.id))
            .first()
        )

        temp_mosto_final = (
            round(payload.temp_vino, 2)
            if payload.temp_vino is not None
            else (float(ultima_lectura.temp_mosto) if ultima_lectura and ultima_lectura.temp_mosto else 18.5)
        )
        temp_amb_final = float(ultima_lectura.temp_ambiente) if ultima_lectura and ultima_lectura.temp_ambiente else 20.5
        ph_final = float(ultima_lectura.ph) if ultima_lectura and ultima_lectura.ph else 3.45

        brix_final = brix_calc if brix_calc is not None else 22.0
        densidad_final = sg_calc if sg_calc is not None else 1.0880

        bateria_pct, bateria_volt = self.calcular_bateria(payload.bateria_voltaje)
        if bateria_pct is None:
            bateria_pct = 90
            bateria_volt = 4.05

        rssi_final = payload.rssi if payload.rssi is not None else -70
        calidad_wifi = self.clasificar_wifi(rssi_final)
        ahora = datetime.utcnow()

        lectura = LecturaTelemetria(
            dispositivo_id=dispositivo.id,
            fermentacion_id=proceso_id,
            timestamp=ahora,
            temp_mosto=temp_mosto_final,
            temp_ambiente=temp_amb_final,
            densidad_sg=densidad_final,
            brix=brix_final,
            ph=ph_final,
            origen_dato="sensor_iot",
            lectura_valida=True
        )
        db.add(lectura)

        estado_nodo = TelemetriaEstadoNodo(
            dispositivo_id=dispositivo.id,
            timestamp=ahora,
            bateria_pct=bateria_pct,
            bateria_volt=bateria_volt,
            rssi_dbm=rssi_final,
            estado_red="conectado"
        )
        db.add(estado_nodo)

        db.commit()
        db.refresh(lectura)

        # TASK-BE-03B: Evaluación de reglas enológicas y despacho de alertas con control anti-spam
        rules_engine.procesar_alertas_lectura(
            db=db,
            lectura=lectura,
            cuba_id=cuba_id,
            dispositivo_id=dispositivo.id
        )

        return TelemetriaRespuestaOut(
            status="ok",
            mensaje="Telemetría ESP8266 (Flotador Hidrómetro) persistida y calibrada correctamente",
            lectura_id=lectura.id,
            cuba_id=cuba_id,
            proceso_id=proceso_id,
            timestamp=ahora,
            valores_procesados=TelemetriaProcesadaOut(
                temperatura_vino=temp_mosto_final,
                temperatura_ambiente=temp_amb_final,
                angulo_tilt=tilt_calc,
                brix=brix_final,
                densidad_sg=densidad_final,
                ph=ph_final,
                bateria_pct=bateria_pct,
                calidad_wifi=calidad_wifi
            )
        )


telemetry_service = TelemetryService()
