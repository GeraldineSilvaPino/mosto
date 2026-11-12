#!/usr/bin/env python3
"""
Simulador de nodos IoT de MOSTO — TASK-BE-02A / TASK-BE-02B
=============================================================

Emula los dos microcontroladores fisicos del proyecto (ver
`backend/docs/HARDWARE_Y_TELEMETRIA.md` seccion 5) enviando telemetria
periodica por HTTP POST al backend FastAPI:

  * Nodo 1 (ESP32)  -> POST /api/telemetria/nodo-cuba   (tempsensmosto.ino)
  * Nodo 2 (ESP8266)-> POST /api/telemetria/flotador     (esp86xyz.ino)

Simula una fermentacion realista:
  * °Brix descendiendo linealmente de 24° a 2° en `--duracion-dias` dias.
  * Temperatura del mosto oscilando en torno a 18.5 °C (ciclo diario + ruido).
  * pH cayendo de 3.60 a 3.30, transmitido como voltaje de la sonda PH-4502C
    para que el backend ejecute su formula de calibracion real.
  * Inclinacion del flotador derivada del °Brix para que el backend ejecute
    su conversion tilt -> Brix -> SG real (no se envian °Bx ni SG directos).
  * Descarga de bateria Li-Po y variacion de RSSI.

TASK-BE-02B — Inyector de anomalias (pruebas de estres):
  * `--spike-temp 33.0`    Sobrecalentamiento subito para probar el disparador
                           de alertas termicas (temperatura_alta / critica).
  * `--drain-battery 3.2`  Descarga de bateria para probar alertas de hardware.
  * `--drop-ph 2.8`        Desviacion de acidez para probar alertas de pH.

Uso:
    python backend/scripts/simulate_esp.py --cuba 1 --interval 5

No requiere dependencias externas: usa unicamente la biblioteca estandar de
Python 3.8+.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib import error as url_error
from urllib import request as url_request


# ---------------------------------------------------------------------------
# Constantes fisicas (deben mantenerse sincronizadas con el backend)
# ---------------------------------------------------------------------------

# backend/app/services/telemetry_service.py -> calibrar_ph()
VOLTAJE_NEUTRO_PH7 = 2.50
FACTOR_SENSIBILIDAD_PH = 0.18

# backend/app/services/telemetry_service.py -> calcular_brix_y_densidad()
TILT_AGUA_CERO_BRIX = 25.0
FACTOR_TILT_A_BRIX = 0.60

# backend/app/services/telemetry_service.py -> calcular_bateria()
BATERIA_V_MIN = 3.30
BATERIA_V_MAX = 4.20

PATH_ESP32 = "/api/telemetria/nodo-cuba"
PATH_ESP8266 = "/api/telemetria/flotador"

# Codigos HTTP que el backend usa para una ingesta exitosa
CODIGOS_OK = (200, 201)


# ---------------------------------------------------------------------------
# Modelo de simulacion de la fermentacion
# ---------------------------------------------------------------------------

class SimuladorFermentacion:
    """
    Evoluciona el estado fisico de una cuba a lo largo del tiempo simulado.

    Cada ciclo avanza `horas_por_ciclo` horas de fermentacion. El tiempo
    simulado sigue avanzando aunque el backend no responda, porque el
    proceso fisico es independiente de la conectividad de la red.

    TASK-BE-02B: puede forzarse una o varias anomalias (fallos inyectados)
    que sobrescriben los valores fisicos calculados y saltan los clamps de
    seguridad, para probar el disparador de alertas de RulesEngine.
    """

    # Rango fisico aceptado por la sonda DS18B20 sin clampamientos
    TEMP_MIN_FISICO = 10.0
    TEMP_MAX_FISICO = 40.0

    def __init__(self, args: argparse.Namespace, cuba_id: Optional[int] = None) -> None:
        self.cuba_id: int = int(cuba_id) if cuba_id is not None else int(str(args.cuba).split(",")[0])
        self.dias_totales: float = max(float(args.duracion_dias), 0.01)
        self.horas_por_ciclo: float = max(float(args.horas_por_ciclo), 0.001)
        self.brix_inicial: float = float(args.brix_inicial)
        self.brix_final: float = float(args.brix_final)
        self.temp_base: float = float(args.temp_base)
        self.temp_amplitud: float = float(args.temp_amplitud)

        # Estado dinámico de degradación de azúcares y temperatura
        self.current_brix: float = float(args.brix_inicial)
        self.stuck_fermentation: bool = getattr(args, "stuck_fermentation", False)
        self.stuck_cuba: Optional[int] = getattr(args, "stuck_cuba", None)
        self.stuck_after: int = getattr(args, "stuck_after", 4)
        self.stuck_temp: float = 29.5

        # --- TASK-BE-02B: fallos inyectados (None = desactivado) ----------
        self.spike_temp: Optional[float] = getattr(args, "spike_temp", None)
        self.drain_battery: Optional[float] = getattr(args, "drain_battery", None)
        self.drop_ph: Optional[float] = getattr(args, "drop_ph", None)

        self.horas_simuladas: float = 0.0
        self.ciclo: int = 0

    @property
    def is_in_stuck_mode(self) -> bool:
        """Determina si esta cuba entró en fase de parada de fermentación (Brix plano y alta temp)."""
        es_cuba = self.stuck_fermentation or (self.stuck_cuba is not None and self.cuba_id == self.stuck_cuba)
        return es_cuba and (self.ciclo >= self.stuck_after)

    @property
    def fallas_activas(self) -> List[str]:
        """Lista legible de anomalias inyectadas con `--spike-temp` etc."""
        activas = []
        if self.is_in_stuck_mode:
            activas.append("PARADA-FERMENTACION (IA ML)")
        if self.spike_temp is not None:
            activas.append("SPIKE-TEMP {0:.1f}°C".format(self.spike_temp))
        if self.drain_battery is not None:
            activas.append("DRAIN-BATTERY {0:.1f}V".format(self.drain_battery))
        if self.drop_ph is not None:
            activas.append("DROP-PH {0:.1f}".format(self.drop_ph))
        return activas

    # -- Tiempo -----------------------------------------------------------
    @property
    def horas_totales(self) -> float:
        return self.dias_totales * 24.0

    @property
    def dia(self) -> float:
        return self.horas_simuladas / 24.0

    @property
    def progreso(self) -> float:
        """0.0 al inicio de la vendimia, 1.0 cuando termina."""
        if self.horas_totales <= 0:
            return 1.0
        return min(1.0, self.horas_simuladas / self.horas_totales)

    def avanzar(self) -> None:
        self.ciclo += 1
        self.horas_simuladas += self.horas_por_ciclo

        if self.is_in_stuck_mode:
            # Estancamiento: Brix congelado alrededor de ~14.5 °Bx
            self.current_brix = 14.50
            # Temperatura sube progresivamente hacia 31.0°C - 33.0°C
            if self.stuck_temp < 32.2:
                self.stuck_temp += random.uniform(0.3, 0.7)
        else:
            # Caída saludable de Brix (-0.03 a -0.06 por tick de 5s en demo)
            caida = random.uniform(0.03, 0.06)
            self.current_brix = max(self.brix_final, self.current_brix - caida)

    # -- Sensores ---------------------------------------------------------
    @property
    def brix(self) -> float:
        if self.is_in_stuck_mode:
            # Parada de fermentación: Brix plano en ~14.5 con ruido mínimo N(0, 0.02)
            valor = 14.50 + random.gauss(0.0, 0.02)
            return round(valor, 2)

        # Caída saludable con suave ruido gaussiano N(0, 0.05)
        valor = self.current_brix + random.gauss(0.0, 0.05)
        return round(max(self.brix_final, min(self.brix_inicial, valor)), 2)

    @property
    def densidad_sg(self) -> float:
        """Gravedad especifica esperada a partir del °Brix (para referencias)."""
        return round(1.0 + self.brix * 0.0039, 4)

    @property
    def temperatura_vino(self) -> float:
        # TASK-BE-02B: sobrecalentamiento forzado sin clamp ni ruido
        if self.spike_temp is not None:
            return round(self.spike_temp, 2)
        if self.is_in_stuck_mode:
            # Parada de fermentación: temperatura elevada hacia 30°C - 33°C
            return round(self.stuck_temp + random.gauss(0.0, 0.15), 2)

        # Fermentación saludable entre 21°C y 24°C
        ciclo_diario = self.temp_amplitud * math.sin(2.0 * math.pi * self.horas_simuladas / 24.0)
        valor = self.temp_base + ciclo_diario + random.gauss(0.0, 0.15)
        return round(max(21.0, min(24.0, valor)), 2)

    @property
    def temperatura_ambiente(self) -> float:
        # Bodega fresca: amplitud diaria desfasada 6 h respecto al mosto
        valor = 20.5 + 3.0 * math.sin(2.0 * math.pi * (self.horas_simuladas + 6.0) / 24.0)
        valor += random.gauss(0.0, 0.3)
        return round(max(10.0, min(35.0, valor)), 2)

    @property
    def humedad_ambiente(self) -> float:
        valor = 60.0 + 8.0 * math.sin(2.0 * math.pi * self.horas_simuladas / 24.0)
        valor += random.gauss(0.0, 1.0)
        return round(max(35.0, min(95.0, valor)), 1)

    @property
    def ph(self) -> float:
        # TASK-BE-02B: desviacion de acidez forzada sin clamp ni ruido
        if self.drop_ph is not None:
            return round(self.drop_ph, 2)
        # El mosto se acidifica levemente a medida que avanza la fermentacion
        valor = 3.60 - 0.30 * self.progreso + random.gauss(0.0, 0.01)
        return round(max(3.10, min(3.90, valor)), 2)

    @property
    def voltaje_ph(self) -> float:
        """
        Invierte la formula de calibracion del backend para que este
        recupere exactamente el pH simulado:
            pH = 7.0 - (V - 2.50) / 0.18   =>   V = 2.50 + (7.0 - pH) * 0.18
        """
        voltaje = VOLTAJE_NEUTRO_PH7 + (7.0 - self.ph) * FACTOR_SENSIBILIDAD_PH
        return round(voltaje, 3)

    @property
    def angulo_tilt(self) -> float:
        """
        Inclinacion del flotador coherente con el °Brix simulado. El backend
        la convertira de vuelta con: Brix = (tilt - 25.0) * 0.60.
        """
        tilt = TILT_AGUA_CERO_BRIX + self.brix / FACTOR_TILT_A_BRIX
        tilt += random.gauss(0.0, 0.4)
        return round(max(25.0, min(70.0, tilt)), 2)

    @property
    def bateria_voltaje(self) -> float:
        # TASK-BE-02B: descarga de bateria forzada sin clamp ni descarga progresiva
        if self.drain_battery is not None:
            return round(self.drain_battery, 2)
        # Descarga progresiva de la celda Li-Po 1S durante la vendimia
        voltaje = BATERIA_V_MAX - (BATERIA_V_MAX - BATERIA_V_MIN) * self.progreso
        voltaje -= random.uniform(0.0, 0.03)
        return round(max(BATERIA_V_MIN, min(BATERIA_V_MAX, voltaje)), 2)

    @property
    def rssi(self) -> int:
        # Debe ser <= 0: la BD tiene la restriccion ck_nodo_rssi
        return int(random.randint(-85, -58))

    # -- Paquetes HTTP ----------------------------------------------------
    def paquete_esp32(self, mac: str) -> Dict[str, Any]:
        """Contrato de POST /api/telemetria/nodo-cuba (seccion 5 del doc)."""
        return {
            "mac_address": mac,
            "cuba_id": self.cuba_id,
            "temperatura_vino": self.temperatura_vino,
            "temperatura_ambiente": self.temperatura_ambiente,
            "humedad_ambiente": self.humedad_ambiente,
            "voltaje_ph": self.voltaje_ph,
            "bateria_voltaje": self.bateria_voltaje,
            "rssi": self.rssi,
        }

    def paquete_esp8266(self, mac: str) -> Dict[str, Any]:
        """
        Contrato de POST /api/telemetria/flotador (seccion 5 del doc).
        Se envia el angulo y los componentes raw del acelerometro, derivados
        de forma consistente: tilt = atan2(sqrt(ax^2 + ay^2), az).
        """
        tilt_rad = math.radians(self.angulo_tilt)
        return {
            "mac_address": mac,
            "cuba_id": self.cuba_id,
            "angulo_tilt": self.angulo_tilt,
            "ax": round(math.sin(tilt_rad), 3),
            "ay": 0.0,
            "az": round(math.cos(tilt_rad), 3),
            "temp_vino": self.temperatura_vino,
            "bateria_voltaje": self.bateria_voltaje,
            "rssi": self.rssi,
        }


# ---------------------------------------------------------------------------
# Transporte HTTP con manejo de excepciones (criterio de aceptacion N° 2)
# ---------------------------------------------------------------------------

class ResultadoEnvio:
    """Resultado no excepcional de un POST: codigo HTTP o causa del fallo."""

    def __init__(self, codigo: Optional[int] = None, detalle: str = "") -> None:
        self.codigo = codigo
        self.detalle = detalle

    @property
    def ok(self) -> bool:
        return self.codigo in CODIGOS_OK

    @property
    def sin_conexion(self) -> bool:
        return self.codigo is None

    def describir(self) -> str:
        if self.sin_conexion:
            return "SIN CONEXION ({0})".format(self.detalle)
        if self.ok:
            return "{0} OK".format(self.codigo)
        return "{0} ERROR {1}".format(self.codigo, self.detalle)


def post_json(url: str, payload: Dict[str, Any], timeout: float) -> ResultadoEnvio:
    """
    Realiza un POST JSON y captura TODA excepcion de red o de transporte,
    devolviendo un resultado en lugar de propagar el error.

    Esto permite que el simulador sobreviva a:
      * backend apagado o reiniciando
      * connection refused / host inexistente
      * timeout de conexion o de lectura
      * errores HTTP 4xx/5xx (no lanza, solo los reporta)
    """
    cuerpo = json.dumps(payload).encode("utf-8")
    peticion = url_request.Request(
        url,
        data=cuerpo,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    try:
        with url_request.urlopen(peticion, timeout=timeout) as respuesta:
            codigo = respuesta.getcode()
            texto = respuesta.read().decode("utf-8", errors="replace")
            return ResultadoEnvio(codigo=codigo, detalle=_resumen(texto))
    except url_error.HTTPError as exc:
        # El servidor respondio, pero con un error de negocio/validacion.
        try:
            texto = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - no queremos morir al leer el cuerpo
            texto = ""
        return ResultadoEnvio(codigo=exc.code, detalle=_resumen(texto))
    except (url_error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        # Fallo de red: el backend esta caido o inaccesible.
        return ResultadoEnvio(codigo=None, detalle=_causa(exc))


def _causa(exc: BaseException) -> str:
    """Extrae una causa legible de una excepcion de red."""
    if isinstance(exc, url_error.URLError) and exc.reason is not None:
        return str(exc.reason)
    return str(exc) or exc.__class__.__name__


def _resumen(texto: str, limite: int = 90) -> str:
    """Colapsa el cuerpo JSON de respuesta a una linea corta y legible."""
    texto = " ".join(texto.split())
    if not texto:
        return ""
    if len(texto) > limite:
        return texto[:limite] + "..."
    return texto


# ---------------------------------------------------------------------------
# Bucle principal
# ---------------------------------------------------------------------------

def construir_envios(
    sim: SimuladorFermentacion, args: argparse.Namespace
) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Devuelve [(etiqueta, url, payload), ...] para los nodos habilitados."""
    base = args.base_url.rstrip("/")
    envios: List[Tuple[str, str, Dict[str, Any]]] = []

    mac_32 = args.mac_esp32 if sim.cuba_id == 1 else args.mac_esp32[:-2] + "{0:02X}".format(sim.cuba_id % 90 + 10)
    mac_82 = args.mac_esp8266 if sim.cuba_id == 1 else args.mac_esp8266[:-2] + "{0:02X}".format(sim.cuba_id % 90 + 10)

    if args.nodo in ("ambos", "esp32"):
        envios.append((
            "ESP32-C{0}".format(sim.cuba_id),
            base + PATH_ESP32,
            sim.paquete_esp32(mac_32),
        ))
    if args.nodo in ("ambos", "esp8266"):
        envios.append((
            "ESP8266-C{0}".format(sim.cuba_id),
            base + PATH_ESP8266,
            sim.paquete_esp8266(mac_82),
        ))
    return envios


def imprimir_linea(
    sim: SimuladorFermentacion,
    resultados: List[Tuple[str, ResultadoEnvio]],
) -> None:
    """Salida visual limpia: un ciclo por linea con el codigo HTTP de cada paquete."""
    momento = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    partes = [
        "[{0:>4}] {1}".format(sim.ciclo, momento),
        "Cuba {0}".format(sim.cuba_id),
        "Dia {0:.1f}/{1:.0f}".format(sim.dia, sim.dias_totales),
        "{0:.2f} Bx".format(sim.brix),
        "{0:.2f} C".format(sim.temperatura_vino),
        "pH {0:.2f}".format(sim.ph),
    ]
    for etiqueta, resultado in resultados:
        partes.append("{0} -> {1}".format(etiqueta, resultado.describir()))
    print(" | ".join(partes), flush=True)


def imprimir_resumen(sim: SimuladorFermentacion, exito: bool, error: str = "") -> None:
    print("", flush=True)
    print("=" * 72, flush=True)
    estado = "FINALIZADO" if exito else "INTERRUMPIDO"
    print("Simulador de telemetria MOSTO — {0}".format(estado), flush=True)
    print("  Cuba destino      : {0}".format(sim.cuba_id), flush=True)
    print("  Ciclos ejecutados : {0}".format(sim.ciclo), flush=True)
    print("  Tiempo simulado   : {0:.1f} dias de fermentacion".format(sim.dia), flush=True)
    print("  Brix final        : {0:.2f} Bx".format(sim.brix), flush=True)
    print("=" * 72, flush=True)
    if error:
        print(error, file=sys.stderr, flush=True)


def ejecutar(args: argparse.Namespace) -> int:
    if args.seed is not None:
        random.seed(args.seed)

    cuba_ids = [int(x.strip()) for x in str(args.cuba).split(",") if x.strip()]
    simuladores = [SimuladorFermentacion(args, cuba_id=cid) for cid in cuba_ids]

    print("Simulador IoT MOSTO — TASK-BE-02A", flush=True)
    print("  Backend      : {0}".format(args.base_url), flush=True)
    print("  Cubas        : {0}".format(cuba_ids), flush=True)
    print("  Nodos        : {0}".format(args.nodo), flush=True)
    print("  Intervalo    : {0} s".format(args.interval), flush=True)
    print("  Duracion     : {0} dias simulados ({1} h/ciclo)".format(
        args.duracion_dias, args.horas_por_ciclo), flush=True)
    print("  Rango Brix   : {0}° -> {1}°".format(args.brix_inicial, args.brix_final), flush=True)
    print("  Ctrl+C para detener.", flush=True)
    print("-" * 72, flush=True)

    fallos_consecutivos = 0
    exito_total = True
    ciclos_ejecutados = 0
    error_final = ""

    while True:
        if args.ciclos > 0 and ciclos_ejecutados >= args.ciclos:
            break

        ciclos_ejecutados += 1
        perdidas: List[Tuple[str, str]] = []

        for sim in simuladores:
            sim.avanzar()
            envios = construir_envios(sim, args)
            resultados: List[Tuple[str, ResultadoEnvio]] = []

            for etiqueta, url, payload in envios:
                resultado = post_json(url, payload, timeout=args.timeout)
                resultados.append((etiqueta, resultado))
                if resultado.sin_conexion:
                    perdidas.append((etiqueta, resultado.detalle))

            imprimir_linea(sim, resultados)

        # --- Backoff ante perdida de conexion (criterio de aceptacion N° 2)
        if not perdidas:
            fallos_consecutivos = 0
            espera = args.interval
        else:
            fallos_consecutivos += 1
            espera = min(
                args.interval * (2 ** min(fallos_consecutivos, 4)),
                args.max_espera,
            )

            # Detalle de la causa: solo al perder la conexion y luego cada 10 ciclos
            if fallos_consecutivos == 1 or fallos_consecutivos % 10 == 0:
                for etiqueta, causa in perdidas:
                    print(
                        "  [RED] {0} sin conexion con el backend ({1})".format(
                            etiqueta, causa
                        ),
                        flush=True,
                    )
                if fallos_consecutivos == 1:
                    print(
                        "  [RED] Backend inaccesible. Reintentando cada "
                        "{0:.1f} s (max {1:.0f} s).".format(espera, args.max_espera),
                        flush=True,
                    )
                else:
                    print(
                        "  [RED] {0} ciclos sin conexion. Reintentando...".format(
                            fallos_consecutivos
                        ),
                        flush=True,
                    )

            if args.max_fallos > 0 and fallos_consecutivos >= args.max_fallos:
                error_final = (
                    "[ERROR] Se alcanzaron {0} fallos consecutivos de conexion "
                    "contra {1}. Verifica que el backend este levantado "
                    "(docker compose up -d).".format(fallos_consecutivos, args.base_url)
                )
                exito_total = False
                break

        try:
            time.sleep(espera)
        except KeyboardInterrupt:
            break

    imprimir_resumen(sim, exito_total, error_final)
    return 0 if exito_total else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _AyudaCompleta(argparse.HelpFormatter):
    """Muestra los defaults por opcion y conserva los saltos de linea del epilog."""

    def _get_help_string(self, action: argparse.Action) -> str:
        ayuda = action.help or ""
        if "%(default)" in ayuda:
            return ayuda
        # Flags con type None (strings sin type=) y flags de anomalia con
        # default None usan otra representacion: no se les pega el default.
        if action.type is None or action.default is None:
            return ayuda
        return "{0} (default: %(default)s)".format(ayuda)

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        return "".join(indent + linea for linea in text.splitlines(True))


def parsear_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="simulate_esp.py",
        description=(
            "Simulador de nodos IoT de MOSTO (ESP32 + ESP8266). "
            "Envia telemetria periodica al backend FastAPI simulando una "
            "fermentacion real: Brix de 24° a 2° y temperatura en torno a 18.5 °C."
        ),
        formatter_class=_AyudaCompleta,
        epilog=(
            "Ejemplos:\n"
            "  python backend/scripts/simulate_esp.py --cuba 1 --interval 5\n"
            "  python backend/scripts/simulate_esp.py --cuba 2 --interval 2 --nodo esp32\n"
            "  python backend/scripts/simulate_esp.py --ciclos 3 --seed 42   (prueba corta)\n"
        ),
    )

    destino = parser.add_argument_group("destino y frecuencia")
    destino.add_argument(
        "--cuba", default="1",
        help="ID o lista de IDs de cubas destino (ej: 1 o 1,12,13)",
    )
    destino.add_argument(
        "--interval", type=float, default=5.0,
        help="Segundos de espera entre ciclos de envio",
    )
    destino.add_argument(
        "--base-url", default="http://localhost:8000",
        help="URL base del backend MOSTO",
    )
    destino.add_argument(
        "--nodo", choices=("ambos", "esp32", "esp8266"), default="ambos",
        help="Que nodo(s) simular",
    )
    destino.add_argument(
        "--timeout", type=float, default=5.0,
        help="Timeout en segundos por peticion HTTP",
    )

    curva = parser.add_argument_group("curva de fermentacion")
    curva.add_argument(
        "--duracion-dias", type=float, default=14.0,
        help="Duracion total de la fermentacion en dias simulados",
    )
    curva.add_argument(
        "--horas-por-ciclo", type=float, default=2.0,
        help="Horas de fermentacion simuladas por ciclo",
    )
    curva.add_argument(
        "--brix-inicial", type=float, default=24.0,
        help="Grados Brix al inicio de la vendimia",
    )
    curva.add_argument(
        "--brix-final", type=float, default=2.0,
        help="Grados Brix objetivo al final de la vendimia",
    )
    curva.add_argument(
        "--temp-base", type=float, default=22.5,
        help="Temperatura base del mosto en grados Celsius (rango optimo 21°C - 24°C)",
    )
    curva.add_argument(
        "--temp-amplitud", type=float, default=0.6,
        help="Amplitud del ciclo diario de temperatura en grados Celsius",
    )

    hardware = parser.add_argument_group("identidad de los nodos")
    hardware.add_argument(
        "--mac-esp32", default="C8:F0:9E:4B:82:10",
        help="Direccion MAC del ESP32 (nodo termico)",
    )
    hardware.add_argument(
        "--mac-esp8266", default="5C:CF:7F:12:34:56",
        help="Direccion MAC del ESP8266 (flotador densimetro)",
    )

    ia_ml = parser.add_argument_group("inteligencia artificial y parada de fermentacion (ML)")
    ia_ml.add_argument(
        "--stuck-cuba", type=int, default=None, metavar="CUBA_ID",
        help="ID de cuba a forzar en escenario de parada de fermentacion (Brix congelado ~14.5, Temp 30-33°C)",
    )
    ia_ml.add_argument(
        "--stuck-after", type=int, default=4, metavar="TICKS",
        help="Cantidad de ticks saludables antes de entrar en parada de fermentacion (default: 4)",
    )
    ia_ml.add_argument(
        "--stuck-fermentation", action="store_true", default=False,
        help="Fuerza inmediatamente la anomalia de parada de fermentacion en la cuba simulada",
    )

    capa = parser.add_argument_group("inyector de anomalias (TASK-BE-02B)")
    capa.add_argument(
        "--spike-temp", type=float, default=None, metavar="CELSIUS",
        help="SPIKE de temperatura: fuerza temp_vino a este valor (°C) en TODOS los paquetes "
             "(p. ej. 33.0). Sin clamp ni ruido. Activa la alerta `temperatura_alta` si supera "
             "el maximo del perfil (severidad media/alta/critica segun el desvio).",
    )
    capa.add_argument(
        "--drain-battery", type=float, default=None, metavar="VOLTAJE",
        help="DRENADO de bateria: fija bateria_voltaje a este valor (V) en TODOS los paquetes "
             "(p. ej. 3.2, proximo al vacio de 3.30V). Prueba alertas de hardware.",
    )
    capa.add_argument(
        "--drop-ph", type=float, default=None, metavar="PH",
        help="CAIDA de pH: fuerza el pH a este valor en TODOS los paquetes "
             "(p. ej. 2.8, bajo el minimo de operacion 3.20 del perfil). "
             "Activa la alerta `ph_bajo` (severidad media/alta/critica segun el desvio).",
    )

    robustez = parser.add_argument_group("robustez y ejecucion")
    robustez.add_argument(
        "--ciclos", type=int, default=0,
        help="Maximo de ciclos a ejecutar (0 = infinito)",
    )
    robustez.add_argument(
        "--max-fallos", type=int, default=0,
        help="Fallos consecutivos de conexion antes de salir con error (0 = nunca salir)",
    )
    robustez.add_argument(
        "--max-espera", type=float, default=60.0,
        help="Tope en segundos del backoff exponencial ante perdida de conexion",
    )
    robustez.add_argument(
        "--seed", type=int, default=None,
        help="Semilla aleatoria para reproducir una simulacion exacta",
    )

    args = parser.parse_args(argv)

    if args.interval <= 0:
        parser.error("--interval debe ser mayor que 0")
    if args.ciclos < 0:
        parser.error("--ciclos no puede ser negativo")
    if args.max_fallos < 0:
        parser.error("--max-fallos no puede ser negativo")
    try:
        c_ids = [int(x.strip()) for x in str(args.cuba).split(",") if x.strip()]
        if not c_ids or any(c < 1 for c in c_ids):
            parser.error("--cuba debe contener IDs positivos separados por coma (ej: 1 o 1,12,13)")
    except ValueError:
        parser.error("--cuba debe ser un numero entero o lista de enteros (ej: 1,12,13)")
    if args.brix_inicial < args.brix_final:
        parser.error("--brix-inicial no puede ser menor que --brix-final")
    if not args.base_url.startswith(("http://", "https://")):
        parser.error("--base-url debe comenzar con http:// o https://")

    return args


def main(argv: Optional[List[str]] = None) -> int:
    args = parsear_args(argv)
    try:
        return ejecutar(args)
    except KeyboardInterrupt:
        print("\nSimulador detenido por el usuario.", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
