
/*
 * ======================================================
 *                       MOSTO v1.1
 *          SISTEMA DE MONITOREO VITIVINICOLA
 * ======================================================
 *
 * CONTROLADOR PRINCIPAL: ESP32 Dev Module
 *
 * SENSORES LOCALES:
 * DS18B20  -> GPIO18 (Temperatura del vino)
 * DHT22    -> GPIO19 (Temperatura y humedad)
 * PH-4502C -> GPIO34 (Salida del divisor resistivo)
 *
 * SENSOR REMOTO:
 * ESP8266 + MPU6050 (Comunicacion por Wi-Fi)
 *
 * RED WIFI:
 * SSID: MOSTO-IOT
 * PASSWORD: mosto2026
 * ESP32 AP: 192.168.4.1
 *
 * RECEPCION HTTP:
 * POST /mpu
 * Campos: roll, pitch, inc, ax, ay, az
 *
 * MONITOR SERIE: 115200 baudios
 *
 * NOTAS:
 * - El pH requiere calibracion.
 * - La densidad requiere calibracion del flotador.
 * - V+ es una referencia manual del multimetro.
 * - No se muestran datos remotos antiguos como actuales.
 * ======================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <math.h>
#include <stdlib.h>

// ======================================================
// 01. CONFIGURACION GENERAL
// ======================================================

#define PIN_VINO       18
#define PIN_AMBIENTE   19
#define PIN_PH         34

#define DHT_TIPO DHT22

const unsigned long INTERVALO = 3000;
const unsigned long TIMEOUT_MPU = 9000;

// Divisor de tension del modulo PH-4502C
const float R_SUPERIOR = 10000.0f;
const float R_INFERIOR = 10000.0f;

const float FACTOR_DIVISOR =
  (R_SUPERIOR + R_INFERIOR) / R_INFERIOR;

// Valor obtenido previamente con multimetro.
// NO se mide automaticamente.
const float VOLTAJE_REFERENCIA = 5.10f;

// ======================================================
// 02. CONFIGURACION WIFI
// ======================================================

const char* WIFI_SSID = "MOSTO-IOT";
const char* WIFI_PASSWORD = "mosto2026";

WebServer servidor(80);

bool wifiActivo = false;

// ======================================================
// 03. OBJETOS DE SENSORES
// ======================================================

OneWire busOneWire(PIN_VINO);
DallasTemperature ds18b20(&busOneWire);

DHT dht(PIN_AMBIENTE, DHT_TIPO);

// ======================================================
// 04. DATOS DEL MPU6050 REMOTO
// ======================================================

struct DatosMPU {
  float roll = 0;
  float pitch = 0;
  float inclinacion = 0;

  float ax = 0;
  float ay = 0;
  float az = 0;

  bool recibido = false;

  unsigned long ultimoPaquete = 0;
  unsigned long paquetesRecibidos = 0;
};

DatosMPU mpu;

// ======================================================
// 05. VARIABLES DEL SISTEMA
// ======================================================

unsigned long tiempoAnterior = 0;
unsigned long numeroLectura = 0;

// ======================================================
// 06. FUNCIONES DE PRESENTACION
// ======================================================

void separador() {
  Serial.println(
    "----------------------------------------------------"
  );
}

void titulo(const char* texto) {
  Serial.println();
  separador();
  Serial.println(texto);
  separador();
}

void imprimirVoltaje(const char* nombre, float valor) {
  Serial.print("  ");
  Serial.print(nombre);
  Serial.print(": ");
  Serial.print(valor, 3);
  Serial.println(" V");
}

// ======================================================
// 07. VALIDACION DE DATOS HTTP
// ======================================================

bool leerCampo(const char* nombre, float &resultado) {

  if (!servidor.hasArg(nombre)) {
    return false;
  }

  String texto = servidor.arg(nombre);
  texto.trim();

  if (texto.length() == 0) {
    return false;
  }

  char* fin = nullptr;
  float numero = strtof(texto.c_str(), &fin);

  if (fin == texto.c_str() || *fin != '\0') {
    return false;
  }

  if (isnan(numero) || isinf(numero)) {
    return false;
  }

  resultado = numero;
  return true;
}

// ======================================================
// 08. RECIBIR DATOS DEL ESP8266
// ======================================================

void recibirMPU() {

  float rollNuevo;
  float pitchNuevo;
  float incNueva;

  float axNuevo;
  float ayNuevo;
  float azNuevo;

  bool correcto =
    leerCampo("roll", rollNuevo) &&
    leerCampo("pitch", pitchNuevo) &&
    leerCampo("inc", incNueva) &&
    leerCampo("ax", axNuevo) &&
    leerCampo("ay", ayNuevo) &&
    leerCampo("az", azNuevo);

  if (!correcto) {
    servidor.send(
      400,
      "text/plain",
      "ERROR: Datos incompletos o invalidos"
    );
    return;
  }

  // Validar limites fisicos basicos
  if (fabsf(rollNuevo) > 180.0f ||
      fabsf(pitchNuevo) > 180.0f ||
      incNueva < 0.0f ||
      incNueva > 180.0f ||
      fabsf(axNuevo) > 20.0f ||
      fabsf(ayNuevo) > 20.0f ||
      fabsf(azNuevo) > 20.0f) {

    servidor.send(
      400,
      "text/plain",
      "ERROR: Valores fuera de rango"
    );
    return;
  }

  // Guardar un paquete valido
  mpu.roll = rollNuevo;
  mpu.pitch = pitchNuevo;
  mpu.inclinacion = incNueva;

  mpu.ax = axNuevo;
  mpu.ay = ayNuevo;
  mpu.az = azNuevo;

  mpu.recibido = true;
  mpu.ultimoPaquete = millis();
  mpu.paquetesRecibidos++;

  servidor.send(200, "text/plain", "RECIBIDO");
}

// ======================================================
// 09. ESTADO DEL ESP8266
// ======================================================

bool mpuOnline() {

  if (!mpu.recibido) {
    return false;
  }

  return (millis() - mpu.ultimoPaquete)
         < TIMEOUT_MPU;
}

// ======================================================
// 10. LECTURA ANALOGICA DEL PH
// ======================================================

void leerAnalogico(
  uint16_t &adcPromedio,
  float &voltajeESP32,
  float &voltajePO
) {

  const int TOTAL_MUESTRAS = 30;

  uint32_t sumaADC = 0;
  uint32_t sumaMilivoltios = 0;

  for (int i = 0; i < TOTAL_MUESTRAS; i++) {

    sumaADC += analogRead(PIN_PH);

    sumaMilivoltios +=
      analogReadMilliVolts(PIN_PH);

    delay(5);
  }

  adcPromedio = sumaADC / TOTAL_MUESTRAS;

  voltajeESP32 =
    (sumaMilivoltios / (float)TOTAL_MUESTRAS)
    / 1000.0f;

  voltajePO =
    voltajeESP32 * FACTOR_DIVISOR;
}

// ======================================================
// 11. INICIALIZACION
// ======================================================

void setup() {

  Serial.begin(115200);
  delay(2000);

  // Inicializar sensores
  ds18b20.begin();
  ds18b20.setResolution(12);

  dht.begin();

  pinMode(PIN_PH, INPUT);

  analogReadResolution(12);
  analogSetPinAttenuation(PIN_PH, ADC_11db);

  // Inicializar Wi-Fi como punto de acceso
  WiFi.mode(WIFI_AP);

  wifiActivo = WiFi.softAP(
    WIFI_SSID,
    WIFI_PASSWORD
  );

  if (wifiActivo) {

    servidor.on(
      "/mpu",
      HTTP_POST,
      recibirMPU
    );

    servidor.on("/", HTTP_GET, []() {
      servidor.send(
        200,
        "text/plain",
        "MOSTO v1.1 | Central ESP32 activa"
      );
    });

    servidor.begin();
  }

  // Presentacion inicial
  Serial.println();
  Serial.println("====================================================");
  Serial.println("                         MOSTO");
  Serial.println("          SISTEMA DE MONITOREO VITIVINICOLA");
  Serial.println("====================================================");

  Serial.println(" Version       : 1.1");
  Serial.println(" Controlador   : ESP32 Dev Module");
  Serial.println(" Comunicacion  : USB / Wi-Fi");
  Serial.println(" Monitor Serie : 115200 baudios");
  Serial.println(" Muestreo      : Cada 3 segundos");

  Serial.println();
  separador();
  Serial.println(" SENSORES LOCALES");
  separador();

  Serial.println(" DS18B20       : GPIO18");
  Serial.println(" DHT22         : GPIO19");
  Serial.println(" PH-4502C      : GPIO34");

  Serial.print(" DS18B20 detectados: ");
  Serial.println(ds18b20.getDeviceCount());

  Serial.println();
  separador();
  Serial.println(" COMUNICACION INALAMBRICA");
  separador();

  if (wifiActivo) {

    Serial.println(" Estado Wi-Fi  : ACTIVO");

    Serial.print(" Red Wi-Fi    : ");
    Serial.println(WIFI_SSID);

    Serial.print(" Direccion IP : ");
    Serial.println(WiFi.softAPIP());

    Serial.println(" Puerto HTTP  : 80");
    Serial.println(" Receptor     : /mpu");

  } else {

    Serial.println(" Estado Wi-Fi : ERROR");
    Serial.println(" Receptor MPU : NO DISPONIBLE");
  }

  Serial.println();
  Serial.println(" Inicializacion completada.");
  Serial.println(" Iniciando monitoreo integrado...");
}

// ======================================================
// 12. PROGRAMA PRINCIPAL
// ======================================================

void loop() {

  // Atender continuamente mensajes entrantes
  if (wifiActivo) {
    servidor.handleClient();
  }

  if (millis() - tiempoAnterior < INTERVALO) {
    return;
  }

  tiempoAnterior = millis();
  numeroLectura++;

  // ====================================================
  // ADQUISICION DE SENSORES LOCALES
  // ====================================================

  ds18b20.requestTemperatures();

  float temperaturaVino =
    ds18b20.getTempCByIndex(0);

  float temperaturaAmbiente =
    dht.readTemperature();

  float humedadAmbiente =
    dht.readHumidity();

  uint16_t adcPH = 0;
  float voltajeGPIO = 0;
  float voltajePO = 0;

  leerAnalogico(
    adcPH,
    voltajeGPIO,
    voltajePO
  );

  bool vinoOK =
    temperaturaVino != DEVICE_DISCONNECTED_C &&
    temperaturaVino >= -55.0f &&
    temperaturaVino <= 125.0f &&
    temperaturaVino != 85.0f;

  bool ambienteOK =
    !isnan(temperaturaAmbiente) &&
    !isnan(humedadAmbiente) &&
    humedadAmbiente >= 0.0f &&
    humedadAmbiente <= 100.0f;

  bool voltajeSeguro =
    voltajeGPIO >= 0.0f &&
    voltajeGPIO < 3.10f;

  bool phAlto =
    voltajePO >= VOLTAJE_REFERENCIA - 0.15f;

  bool remotoOK = mpuOnline();

  // ====================================================
  // REPORTE GENERAL
  // ====================================================

  Serial.println();
  Serial.println("====================================================");
  Serial.println("              MOSTO | REPORTE DE MEDICION");
  Serial.println("====================================================");

  Serial.print(" Lectura numero : ");
  Serial.println(numeroLectura);

  Serial.print(" Tiempo activo  : ");
  Serial.print(millis() / 1000);
  Serial.println(" segundos");

  // ====================================================
  // 01. TEMPERATURA DEL VINO
  // ====================================================

  titulo("[01] TEMPERATURA DEL VINO | DS18B20");

  Serial.println("  Entrada digital : GPIO18");

  if (vinoOK) {

    Serial.print("  Temperatura     : ");
    Serial.print(temperaturaVino, 2);
    Serial.println(" C");

    Serial.println("  Comunicacion    : CORRECTA");

  } else {

    Serial.println("  Temperatura     : SIN DATOS");
    Serial.println("  Comunicacion    : ERROR");
  }

  // ====================================================
  // 02. AMBIENTE
  // ====================================================

  titulo("[02] CONDICIONES AMBIENTALES | DHT22");

  Serial.println("  Entrada digital : GPIO19");

  if (ambienteOK) {

    Serial.print("  Temperatura     : ");
    Serial.print(temperaturaAmbiente, 2);
    Serial.println(" C");

    Serial.print("  Humedad         : ");
    Serial.print(humedadAmbiente, 2);
    Serial.println(" % HR");

    Serial.println("  Comunicacion    : CORRECTA");

  } else {

    Serial.println("  Temperatura     : SIN DATOS");
    Serial.println("  Humedad         : SIN DATOS");
    Serial.println("  Comunicacion    : ERROR");
  }

  // ====================================================
  // 03. PH-4502C
  // ====================================================

  titulo("[03] MODULO DE PH | PH-4502C");

  Serial.println("  Entrada analogica : GPIO34");
  Serial.println("  Resolucion ADC    : 12 bits");

  Serial.print("  Valor ADC         : ");
  Serial.print(adcPH);
  Serial.println(" / 4095");

  Serial.println();
  Serial.println("  MEDICIONES ELECTRICAS");

  imprimirVoltaje(
    "GPIO34 - voltaje leido",
    voltajeGPIO
  );

  imprimirVoltaje(
    "PO - voltaje estimado",
    voltajePO
  );

  Serial.print("  V+ referencia manual : ");
  Serial.print(VOLTAJE_REFERENCIA, 2);
  Serial.println(" V");

  Serial.println();
  Serial.println("  DIVISOR DE TENSION");

  Serial.println("  Resistencia superior : 10 kOhm");
  Serial.println("  Resistencia inferior : 10 kOhm");

  Serial.print("  Factor aplicado      : ");
  Serial.println(FACTOR_DIVISOR, 2);

  Serial.println();

  if (voltajeSeguro) {
    Serial.println("  Entrada ADC          : RANGO MONITOREADO");
  } else {
    Serial.println("  Entrada ADC          : REVISAR VOLTAJE");
  }

  if (phAlto) {
    Serial.println("  Salida PO            : CERCA DE V+");
    Serial.println("  Diagnostico          : POSIBLE SATURACION");
  } else {
    Serial.println("  Salida PO            : SENAL DETECTADA");
  }

  Serial.println("  Medicion de pH       : NO VALIDADA");
  Serial.println("  Calibracion          : PENDIENTE");

  // ====================================================
  // 04. ESP8266 + MPU6050
  // ====================================================

  titulo("[04] DENSIMETRO REMOTO | ESP8266 + MPU6050");

  Serial.print("  Red Wi-Fi        : ");
  Serial.println(wifiActivo ? WIFI_SSID : "NO DISPONIBLE");

  Serial.print("  Direccion central: ");

  if (wifiActivo) {
    Serial.println(WiFi.softAPIP());
  } else {
    Serial.println("SIN IP");
  }

  Serial.print("  Clientes Wi-Fi   : ");

  if (wifiActivo) {
    Serial.println(WiFi.softAPgetStationNum());
  } else {
    Serial.println(0);
  }

  Serial.print("  Estado ESP8266   : ");

  if (remotoOK) {

    Serial.println("CONECTADO / ENVIANDO DATOS");

    Serial.println();
    Serial.println("  ORIENTACION");

    Serial.printf(
      "  Roll             : %+.2f grados\n",
      mpu.roll
    );

    Serial.printf(
      "  Pitch            : %+.2f grados\n",
      mpu.pitch
    );

    Serial.printf(
      "  Inclinacion      : %.2f grados\n",
      mpu.inclinacion
    );

    Serial.println();
    Serial.println("  ACELERACION");

    Serial.printf(
      "  Eje X            : %+.4f g\n",
      mpu.ax
    );

    Serial.printf(
      "  Eje Y            : %+.4f g\n",
      mpu.ay
    );

    Serial.printf(
      "  Eje Z            : %+.4f g\n",
      mpu.az
    );

    Serial.println();
    Serial.println("  COMUNICACION");

    Serial.print("  Paquetes recibidos: ");
    Serial.println(mpu.paquetesRecibidos);

    Serial.print("  Ultimo paquete    : hace ");

    Serial.print(
      (millis() - mpu.ultimoPaquete) / 1000
    );

    Serial.println(" segundos");

  } else {

    Serial.println("SIN DATOS RECIENTES");

    Serial.println("  Roll             : SIN DATOS");
    Serial.println("  Pitch            : SIN DATOS");
    Serial.println("  Inclinacion      : SIN DATOS");
    Serial.println("  Aceleracion      : SIN DATOS");

    if (mpu.recibido) {
      Serial.println(
        "  Diagnostico      : COMUNICACION INTERRUMPIDA"
      );
    } else {
      Serial.println(
        "  Diagnostico      : ESPERANDO PRIMER PAQUETE"
      );
    }
  }

  Serial.println();
  Serial.println("  Densidad          : NO CALIBRADA");
  Serial.println("  Gravedad especifica: NO DISPONIBLE");

  // ====================================================
  // 05. DIAGNOSTICO GENERAL
  // ====================================================

  titulo("[05] DIAGNOSTICO GENERAL");

  Serial.print("  DS18B20 : ");
  Serial.println(vinoOK ? "OPERATIVO" : "ERROR");

  Serial.print("  DHT22   : ");
  Serial.println(ambienteOK ? "OPERATIVO" : "ERROR");

  Serial.print("  ADC PH  : ");
  Serial.println(
    voltajeSeguro ? "LECTURA DISPONIBLE" :
                    "REVISAR ENTRADA"
  );

  Serial.print("  PH REAL : ");
  Serial.println("PENDIENTE DE VALIDACION");

  Serial.print("  WIFI    : ");
  Serial.println(wifiActivo ? "ACTIVO" : "ERROR");

  Serial.print("  ESP8266 : ");
  Serial.println(remotoOK ? "TRANSMITIENDO" :
                              "SIN DATOS RECIENTES");

  Serial.print("  MPU6050 : ");
  Serial.println(remotoOK ? "DATOS DISPONIBLES" :
                              "SIN DATOS RECIENTES");

  Serial.println();

  if (vinoOK &&
      ambienteOK &&
      voltajeSeguro &&
      remotoOK) {

    Serial.println(
      "  ESTADO: ADQUISICION INTEGRADA ACTIVA"
    );

  } else if (vinoOK &&
             ambienteOK &&
             voltajeSeguro) {

    Serial.println(
      "  ESTADO: SENSORES LOCALES ACTIVOS"
    );

    Serial.println(
      "  MODULO REMOTO: PENDIENTE DE RECEPCION"
    );

  } else {

    Serial.println(
      "  ESTADO: REVISAR COMPONENTES"
    );
  }

  Serial.println();
  Serial.println("====================================================");
  Serial.println("              MOSTO | FIN DEL REPORTE");
  Serial.println("====================================================");
}
