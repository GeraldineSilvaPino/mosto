
/*
  ==================================================
             MOSTO - DENSIMETRO v2.0
  ==================================================

  ESP8266 + MPU6050

  SDA -> GPIO4 / IO04
  SCL -> GPIO5 / IO05
  VCC -> 3V3
  GND -> GND

  Funciones:
  - Mide inclinacion del flotador
  - Permite calibrar grados Brix por WiFi
  - Guarda calibracion en EEPROM
  - Calcula Brix mediante interpolacion
  - Envia mediciones al ESP32
  - NO inventa Brix sin calibracion

  Monitor Serie: 115200
*/

#include <Arduino.h>
#include <Wire.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266WebServer.h>
#include <EEPROM.h>
#include <math.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>

// ================================================
// PINES Y SENSOR
// ================================================

#define SDA_PIN 4
#define SCL_PIN 5

uint8_t mpuDireccion = 0x68;
uint8_t mpuID = 0;

bool mpuActivo = false;
bool medicionValida = false;

// ================================================
// WIFI
// ================================================

const char* WIFI_NOMBRE = "MOSTO-IOT";
const char* WIFI_CLAVE = "mosto2026";

const char* URL_CENTRAL =
  "http://192.168.4.1/mpu";

// IP fija del ESP8266
IPAddress IP_LOCAL(192, 168, 4, 50);
IPAddress IP_CENTRAL(192, 168, 4, 1);
IPAddress MASCARA(255, 255, 255, 0);

ESP8266WebServer web(80);

// ================================================
// CALIBRACION
// ================================================

#define MAX_PUNTOS 8
#define FIRMA_CAL 0x4D53544FUL

struct Punto {
  float angulo;
  float brix;
};

struct Calibracion {
  uint32_t firma;
  uint8_t cantidad;
  Punto puntos[MAX_PUNTOS];
  uint32_t verificacion;
};

Calibracion cal;

// ================================================
// MEDICIONES
// ================================================

float ax = 0;
float ay = 0;
float az = 0;

float roll = 0;
float pitch = 0;

float angulo = 0;

// Promedio de 12 mediciones
#define N_MUESTRAS 12

float muestras[N_MUESTRAS];
uint8_t numeroMuestras = 0;
uint8_t indiceMuestra = 0;

unsigned long ultimoSensor = 0;
unsigned long ultimoEnvio = 0;
unsigned long ultimoWiFi = 0;
unsigned long ultimoIntentoMPU = 0;
unsigned long instanteMedicion = 0;

bool wifiAnterior = false;

const unsigned long CADA_SENSOR = 250;
const unsigned long CADA_ENVIO = 3000;

// ================================================
// EEPROM - GUARDAR CALIBRACION
// ================================================

uint32_t calcularVerificacion() {

  const uint8_t* bytes =
    (const uint8_t*)&cal;

  uint32_t hash = 2166136261UL;

  for (
    size_t i = 0;
    i < offsetof(Calibracion, verificacion);
    i++
  ) {
    hash ^= bytes[i];
    hash *= 16777619UL;
  }

  return hash;
}

void limpiarCalibracionRAM() {

  memset(&cal, 0, sizeof(cal));
  cal.firma = FIRMA_CAL;
}

void cargarCalibracion() {

  EEPROM.get(0, cal);

  if (
    cal.firma != FIRMA_CAL ||
    cal.cantidad > MAX_PUNTOS ||
    cal.verificacion != calcularVerificacion()
  ) {
    limpiarCalibracionRAM();
    Serial.println("[CAL] Sin calibracion guardada");
    return;
  }

  for (int i = 0; i < cal.cantidad; i++) {

    if (
      !isfinite(cal.puntos[i].angulo) ||
      !isfinite(cal.puntos[i].brix) ||
      cal.puntos[i].angulo < 0 ||
      cal.puntos[i].angulo > 180 ||
      cal.puntos[i].brix < 0 ||
      cal.puntos[i].brix > 40
    ) {
      limpiarCalibracionRAM();
      Serial.println("[CAL] Datos invalidos");
      return;
    }
  }

  Serial.print("[CAL] Puntos recuperados: ");
  Serial.println(cal.cantidad);
}

bool guardarCalibracion() {

  cal.verificacion = calcularVerificacion();

  EEPROM.put(0, cal);

  return EEPROM.commit();
}

// ================================================
// FUNCIONES I2C
// ================================================

bool escribirRegistro(
  uint8_t registro,
  uint8_t valor
) {

  Wire.beginTransmission(mpuDireccion);

  Wire.write(registro);
  Wire.write(valor);

  return Wire.endTransmission() == 0;
}

bool leerRegistros(
  uint8_t registro,
  uint8_t* datos,
  uint8_t cantidad
) {

  Wire.beginTransmission(mpuDireccion);
  Wire.write(registro);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (
    Wire.requestFrom(
      mpuDireccion,
      cantidad
    ) != cantidad
  ) {
    return false;
  }

  for (int i = 0; i < cantidad; i++) {
    datos[i] = Wire.read();
  }

  return true;
}

int16_t numero16(uint8_t alto, uint8_t bajo) {

  return (int16_t)(
    ((uint16_t)alto << 8) | bajo
  );
}

// ================================================
// INICIAR MPU
// ================================================

bool iniciarMPU() {

  const uint8_t direcciones[] = {0x68, 0x69};

  for (int i = 0; i < 2; i++) {

    mpuDireccion = direcciones[i];

    uint8_t id = 0;

    if (!leerRegistros(0x75, &id, 1)) {
      continue;
    }

    Serial.print("[MPU] WHO_AM_I: 0x");
    Serial.println(id, HEX);

    // MPU6050 normalmente devuelve 0x68.
    // Se admite 0x74 para probar la variante
    // detectada previamente en este modulo.

    if (id != 0x68 && id != 0x74) {
      continue;
    }

    mpuID = id;

    if (id == 0x74) {
      Serial.println(
        "[MPU] Aviso: identidad fisica por verificar"
      );
    }

    if (!escribirRegistro(0x6B, 0x01)) {
      return false;
    }

    delay(100);

    if (!escribirRegistro(0x1C, 0x00)) {
      return false;
    }

    if (!escribirRegistro(0x1B, 0x00)) {
      return false;
    }

    if (!escribirRegistro(0x1A, 0x03)) {
      return false;
    }

    Serial.println("[MPU] Inicializado");
    return true;
  }

  Serial.println("[MPU] No detectado");
  return false;
}

// ================================================
// MEDIR INCLINACION
// ================================================

void medirMPU() {

  if (!mpuActivo) {

    if (
      millis() - ultimoIntentoMPU < 4000
    ) {
      return;
    }

    ultimoIntentoMPU = millis();

    mpuActivo = iniciarMPU();

    return;
  }

  uint8_t datos[6];

  if (!leerRegistros(0x3B, datos, 6)) {

    mpuActivo = false;
    medicionValida = false;
    numeroMuestras = 0;

    Serial.println("[MPU] Error I2C");

    return;
  }

  ax = numero16(datos[0], datos[1]) / 16384.0f;
  ay = numero16(datos[2], datos[3]) / 16384.0f;
  az = numero16(datos[4], datos[5]) / 16384.0f;

  float modulo = sqrtf(
    ax * ax + ay * ay + az * az
  );

  // Comprobacion basica en reposo
  if (
    !isfinite(modulo) ||
    modulo < 0.65f ||
    modulo > 1.35f
  ) {
    medicionValida = false;
    numeroMuestras = 0;
    return;
  }

  roll = atan2f(ay, az) * 180.0f / PI;

  pitch = atan2f(
    -ax,
    sqrtf(ay * ay + az * az)
  ) * 180.0f / PI;

  float coseno = az / modulo;

  if (coseno > 1) coseno = 1;
  if (coseno < -1) coseno = -1;

  float anguloNuevo =
    acosf(coseno) * 180.0f / PI;

  // Suavizado con promedio movil
  muestras[indiceMuestra] = anguloNuevo;

  indiceMuestra =
    (indiceMuestra + 1) % N_MUESTRAS;

  if (numeroMuestras < N_MUESTRAS) {
    numeroMuestras++;
  }

  float suma = 0;

  for (int i = 0; i < numeroMuestras; i++) {
    suma += muestras[i];
  }

  angulo = suma / numeroMuestras;

  medicionValida = true;
  instanteMedicion = millis();
}

// ================================================
// COMPROBAR ESTABILIDAD
// ================================================

bool flotadorEstable() {

  if (
    !medicionValida ||
    numeroMuestras < N_MUESTRAS ||
    millis() - instanteMedicion > 1000
  ) {
    return false;
  }

  float menor = muestras[0];
  float mayor = muestras[0];

  for (int i = 1; i < N_MUESTRAS; i++) {

    if (muestras[i] < menor) {
      menor = muestras[i];
    }

    if (muestras[i] > mayor) {
      mayor = muestras[i];
    }
  }

  return (mayor - menor) <= 1.5f;
}

// ================================================
// INTERPOLAR ANGULO A BRIX
// ================================================

bool calcularBrix(
  float anguloMedido,
  float& resultado
) {

  if (cal.cantidad < 2) {
    return false;
  }

  // No extrapolar fuera del rango calibrado
  if (
    anguloMedido < cal.puntos[0].angulo ||
    anguloMedido >
    cal.puntos[cal.cantidad - 1].angulo
  ) {
    return false;
  }

  for (int i = 0; i < cal.cantidad - 1; i++) {

    Punto a = cal.puntos[i];
    Punto b = cal.puntos[i + 1];

    if (
      anguloMedido >= a.angulo &&
      anguloMedido <= b.angulo
    ) {

      float proporcion =
        (anguloMedido - a.angulo) /
        (b.angulo - a.angulo);

      resultado =
        a.brix +
        proporcion * (b.brix - a.brix);

      return isfinite(resultado);
    }
  }

  return false;
}

// ================================================
// VALIDAR Y ORDENAR CALIBRACION
// ================================================

void ordenarPuntos() {

  for (int i = 1; i < cal.cantidad; i++) {

    Punto actual = cal.puntos[i];
    int j = i - 1;

    while (
      j >= 0 &&
      cal.puntos[j].angulo > actual.angulo
    ) {
      cal.puntos[j + 1] = cal.puntos[j];
      j--;
    }

    cal.puntos[j + 1] = actual;
  }
}

bool puntosCoherentes() {

  int direccion = 0;

  for (int i = 1; i < cal.cantidad; i++) {

    float deltaAngulo =
      cal.puntos[i].angulo -
      cal.puntos[i - 1].angulo;

    float deltaBrix =
      cal.puntos[i].brix -
      cal.puntos[i - 1].brix;

    if (
      deltaAngulo < 0.8f ||
      fabsf(deltaBrix) < 0.15f
    ) {
      return false;
    }

    int signo = deltaBrix > 0 ? 1 : -1;

    if (direccion != 0 && signo != direccion) {
      return false;
    }

    direccion = signo;
  }

  return true;
}

// ================================================
// PAGINA WEB
// ================================================

void mostrarWeb() {

  String html = F(
    "<!doctype html><html lang='es'>"
    "<head><meta charset='utf-8'>"
    "<meta name='viewport' "
    "content='width=device-width,initial-scale=1'>"
    "<title>MOSTO - Calibracion</title>"
    "<style>"
    "body{font-family:Arial,sans-serif;"
    "max-width:600px;margin:25px auto;"
    "padding:15px;background:#f5f6f8;color:#17212b}"
    ".c{background:white;padding:18px;"
    "border-radius:12px;margin-bottom:12px}"
    "input,button{font-size:17px;padding:10px;"
    "margin:6px 0}"
    "a{color:#126b83}"
    "table{width:100%;border-collapse:collapse}"
    "td,th{padding:8px;border-bottom:1px solid #ddd}"
    "</style></head><body>"
    "<h2>MOSTO | Densimetro</h2>"
  );

  html += F("<div class='c'><h3>Medicion actual</h3>");

  if (medicionValida) {

    html += F("<p>Inclinacion: <b>");
    html += String(angulo, 2);
    html += F(" grados</b></p>");

    float brix = 0;

    if (calcularBrix(angulo, brix)) {

      html += F("<p>Brix estimado: <b>");
      html += String(brix, 2);
      html += F(" &deg;Bx</b></p>");

    } else {

      html += F(
        "<p>Brix: SIN CALIBRAR "
        "O FUERA DE RANGO</p>"
      );
    }

    html += F("<p>Flotador: ");

    html += flotadorEstable()
      ? "ESTABLE"
      : "EN MOVIMIENTO";

    html += F("</p>");

  } else {

    html += F("<p>Esperando datos del sensor</p>");
  }

  html += F("</div>");

  html += F(
    "<div class='c'>"
    "<h3>Agregar punto de calibracion</h3>"
    "<p>Introduce el valor real del refractometro "
    "cuando el flotador este estable.</p>"
    "<form action='/cal' method='GET'>"
    "<label>Grados Brix de referencia:</label><br>"
    "<input type='number' name='brix' "
    "min='0' max='40' step='0.01' required>"
    "<br><button type='submit'>Guardar punto</button>"
    "</form></div>"
  );

  html += F("<div class='c'><h3>Puntos guardados</h3>");

  html += F("<table><tr><th>Angulo</th><th>Brix</th></tr>");

  for (int i = 0; i < cal.cantidad; i++) {

    html += F("<tr><td>");
    html += String(cal.puntos[i].angulo, 2);
    html += F("&deg;</td><td>");
    html += String(cal.puntos[i].brix, 2);
    html += F(" &deg;Bx</td></tr>");
  }

  html += F("</table><p>");

  html += String(cal.cantidad);
  html += F(" de 8 puntos registrados</p>");

  html += F(
    "<a href='/borrar?confirmar=SI' "
    "onclick=\"return confirm('Borrar calibracion?')\">"
    "Borrar calibracion</a></div>"
    "<p><a href='/'>Actualizar mediciones</a></p>"
    "<p>Calibrar con el flotador definitivo.</p>"
    "</body></html>"
  );

  web.sendHeader("Cache-Control", "no-store");
  web.send(200, "text/html; charset=utf-8", html);
}

// ================================================
// MENSAJES DE ERROR WEB
// ================================================

void errorWeb(const String& mensaje) {

  web.send(
    400,
    "text/html; charset=utf-8",
    "<h3>" + mensaje +
    "</h3><p><a href='/'>Volver</a></p>"
  );
}

// ================================================
// GUARDAR PUNTO DESDE NAVEGADOR
// ================================================

void agregarPuntoWeb() {

  if (!flotadorEstable()) {

    errorWeb(
      "Flotador inestable. "
      "Espera a que deje de moverse."
    );

    return;
  }

  if (cal.cantidad >= MAX_PUNTOS) {

    errorWeb("Capacidad maxima: 8 puntos.");
    return;
  }

  if (!web.hasArg("brix")) {

    errorWeb("Falta valor Brix.");
    return;
  }

  String entrada = web.arg("brix");

  char* finalNumero;
  float referencia =
    strtof(entrada.c_str(), &finalNumero);

  if (
    finalNumero == entrada.c_str() ||
    *finalNumero != '\0' ||
    !isfinite(referencia) ||
    referencia < 0 ||
    referencia > 40
  ) {

    errorWeb("Valor Brix no valido.");
    return;
  }

  Calibracion respaldo = cal;

  cal.puntos[cal.cantidad].angulo = angulo;
  cal.puntos[cal.cantidad].brix = referencia;

  cal.cantidad++;

  ordenarPuntos();

  if (!puntosCoherentes()) {

    cal = respaldo;

    errorWeb(
      "Punto rechazado: angulos demasiado "
      "similares o tendencia inconsistente."
    );

    return;
  }

  if (!guardarCalibracion()) {

    cal = respaldo;

    errorWeb("No se pudo guardar en memoria.");
    return;
  }

  Serial.println();
  Serial.println("[CAL] NUEVO PUNTO GUARDADO");

  Serial.print("Angulo: ");
  Serial.println(angulo, 2);

  Serial.print("Brix referencia: ");
  Serial.println(referencia, 2);

  web.sendHeader("Location", "/");
  web.send(303, "text/plain", "Guardado");
}

// ================================================
// BORRAR CALIBRACION
// ================================================

void borrarCalibracionWeb() {

  if (
    !web.hasArg("confirmar") ||
    web.arg("confirmar") != "SI"
  ) {
    errorWeb("Confirmacion requerida.");
    return;
  }

  Calibracion respaldo = cal;

  limpiarCalibracionRAM();

  if (!guardarCalibracion()) {

    cal = respaldo;
    errorWeb("No se pudo borrar.");
    return;
  }

  Serial.println("[CAL] Calibracion borrada");

  web.sendHeader("Location", "/");
  web.send(303, "text/plain", "Borrado");
}

// ================================================
// COMUNICACION WIFI
// ================================================

void revisarWiFi() {

  if (WiFi.status() == WL_CONNECTED) {

    if (!wifiAnterior) {

      wifiAnterior = true;

      Serial.println();
      Serial.println("[WIFI] CONECTADO");

      Serial.print("[WIFI] IP ESP8266: ");
      Serial.println(WiFi.localIP());

      Serial.println(
        "[WEB] http://192.168.4.50"
      );
    }

    return;
  }

  wifiAnterior = false;

  if (millis() - ultimoWiFi >= 10000) {

    ultimoWiFi = millis();

    Serial.println("[WIFI] Reconectando...");

    WiFi.begin(WIFI_NOMBRE, WIFI_CLAVE);
  }
}

// ================================================
// ENVIAR MEDICIONES AL ESP32
// ================================================

void enviarESP32() {

  if (!medicionValida) {

    Serial.println("[ENVIO] Sensor sin datos validos");
    return;
  }

  if (WiFi.status() != WL_CONNECTED) {

    Serial.println("[ENVIO] Sin WiFi");
    return;
  }

  String cuerpo =
    "roll=" + String(roll, 2) +
    "&pitch=" + String(pitch, 2) +
    "&inc=" + String(angulo, 2) +
    "&ax=" + String(ax, 4) +
    "&ay=" + String(ay, 4) +
    "&az=" + String(az, 4);

  float brix = 0;

  if (calcularBrix(angulo, brix)) {

    cuerpo += "&brix=" + String(brix, 2);
    cuerpo += "&cal=1";

  } else {

    cuerpo += "&cal=0";
  }

  WiFiClient cliente;
  HTTPClient http;

  http.setTimeout(2000);

  if (!http.begin(cliente, URL_CENTRAL)) {
    Serial.println("[HTTP] Error de inicio");
    return;
  }

  http.addHeader(
    "Content-Type",
    "application/x-www-form-urlencoded"
  );

  int respuesta = http.POST(cuerpo);

  if (respuesta == 200) {

    Serial.println("[ENVIO] ESP32 recibio datos");

  } else {

    Serial.print("[ENVIO] Error HTTP: ");
    Serial.println(respuesta);
  }

  http.end();
}

// ================================================
// CONFIGURACION INICIAL
// ================================================

void setup() {

  Serial.begin(115200);
  delay(1000);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);

  EEPROM.begin(256);
  cargarCalibracion();

  Serial.println();
  Serial.println("===============================");
  Serial.println(" MOSTO | DENSIMETRO ESP8266");
  Serial.println("===============================");

  Serial.println("SDA: GPIO4");
  Serial.println("SCL: GPIO5");

  mpuActivo = iniciarMPU();

  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);

  WiFi.config(
    IP_LOCAL,
    IP_CENTRAL,
    MASCARA
  );

  WiFi.begin(WIFI_NOMBRE, WIFI_CLAVE);

  ultimoWiFi = millis();

  web.on("/", HTTP_GET, mostrarWeb);
  web.on("/cal", HTTP_GET, agregarPuntoWeb);
  web.on("/borrar", HTTP_GET, borrarCalibracionWeb);

  web.begin();

  Serial.println();
  Serial.println("Web de calibracion:");
  Serial.println("http://192.168.4.50");

  Serial.println();
  Serial.println("Esperando mediciones...");
}

// ================================================
// BUCLE PRINCIPAL
// ================================================

void loop() {

  revisarWiFi();

  web.handleClient();

  // Medicion cada 250 ms
  if (millis() - ultimoSensor >= CADA_SENSOR) {

    ultimoSensor = millis();
    medirMPU();
  }

  // Reporte y envio cada 3 segundos
  if (millis() - ultimoEnvio >= CADA_ENVIO) {

    ultimoEnvio = millis();

    Serial.println();
    Serial.println("===============================");
    Serial.println(" MOSTO | MEDICION");
    Serial.println("===============================");

    if (medicionValida) {

      Serial.print("Inclinacion: ");
      Serial.print(angulo, 2);
      Serial.println(" grados");

      Serial.print("Estabilidad: ");
      Serial.println(
        flotadorEstable()
        ? "ESTABLE"
        : "EN MOVIMIENTO"
      );

      float brix = 0;

      if (calcularBrix(angulo, brix)) {

        Serial.print("Brix estimado: ");
        Serial.print(brix, 2);
        Serial.println(" grados Brix");

      } else {

        Serial.println(
          "Brix: SIN CALIBRAR / FUERA DE RANGO"
        );
      }

    } else {

      Serial.println("Sensor sin lectura valida");
    }

    Serial.print("Puntos de calibracion: ");
    Serial.println(cal.cantidad);

    enviarESP32();
  }

  delay(5);
}
