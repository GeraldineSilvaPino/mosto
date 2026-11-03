# Hardware, Sensores y Calibracion Fisica de Telemetria

Este documento detalla la integracion tecnica entre los microcontroladores fisicos (ESP32 y ESP8266) y el backend de MOSTO, especificando el circuito electronico, las formulas matematicas de calibracion y los contratos de comunicacion HTTP.

---

## 1. Topologia de Nodos de Hardware

El monitoreo de cada cuba de fermentacion se compone de dos dispositivos fisicos independientes:

```
                  ARQUITECTURA DE SENSORES POR CUBA
 ┌───────────────────────────────────────┐   ┌──────────────────────────────────┐
 │       NODO 1: ESP32 (Exterior Cuba)   │   │   NODO 2: ESP8266 (Capsula Flotante)
 ├───────────────────────────────────────┤   ├──────────────────────────────────┤
 │ - DS18B20: Temperatura Vino (Vaina)   │   │ - MPU-6050: Inclinacion angular  │
 │ - DHT22: Temperatura/Humedad Ambiente │   │ - Celda Li-Po 1S (3.7V / 4.2V)   │
 │ - PH-4502C: Sonda Analogica de pH     │   │ - Mide densidad y azucar (°Bx)   │
 └───────────────────────────────────────┘   └──────────────────────────────────┘
```

---

## 2. Nodo 1: ESP32 (Sonda Termica y de pH)

* **Archivo Arduino de Referencia:** `Downloads/tempsensmosto.ino`
* **Pines y Circuitos:**
  * **GPIO 18:** Sensor de temperatura digital sumergible **DS18B20** con protocolo OneWire y resistencia pull-up de 4.7 kOhms conectada a 3.3V.
  * **GPIO 19:** Sensor digital de temperatura y humedad ambiental **DHT22**.
  * **GPIO 34 (Entrada Analogica ADC):** Modulo de pH **PH-4502C**.
    * Debido a que el modulo entrega senales de hasta 5.0V y los pines ADC del ESP32 toleran maximo 3.3V, se implemento un divisor de voltaje resistivo:
      PO -> Resistencia 10k -> GPIO 34 -> Resistencia 10k -> GND (Factor Divisor = 2.0).
    * El firmware promedia 20 muestras analogicas consecutivas para amortiguar ruido electrico:
      Voltaje PO = Voltaje GPIO 34 * 2.0

### Formula de Calibracion de pH (Backend):
La sonda entrega aproximadamente 2.50 V en solucion neutra (pH 7.0) a 25°C, con una pendiente negativa de aproximadamente 0.18 V por unidad de pH (a mayor acidez del mosto, mayor voltaje entrega el electrodo):
$$pH = 7.0 - \left( \frac{\text{Voltaje PO} - 2.50}{0.18} \right)$$
* En mostos y vinos tintos tipicos (pH entre 3.1 y 3.8), el voltaje medido ronda entre 3.08 V y 3.20 V.

---

## 3. Nodo 2: ESP8266 (Flotador Hidrometro / Densimetro IoT)

* **Archivo Arduino de Referencia:** `Downloads/esp86xyz.ino`
* **Pines y Comunicacion:**
  * **D2 (GPIO 4):** SDA (I2C)
  * **D1 (GPIO 5):** SCL (I2C)
  * **Sensor:** Acelerometro de 3 ejes **MPU-6050** (Direccion I2C `0x68` o `0x69`).
  * **Alimentacion:** Bateria recargable Li-Po 1S (3.7V nominal, 4.2V en carga maxima).

### Principio Fisico del Hidrometro Flotante (Tilt Hydrometer):
El dispositivo flota dentro del mosto en fermentacion dentro de una capsula hermetica contrapesada en su base:
1. **Inicio de fermentacion:** El mosto contiene alta concentracion de azucares disueltos (~24 °Bx, Gravedad Especifica SG ~ 1.096). Al ser un medio mas denso, el flotador se inclina con un angulo pronunciado respecto al eje vertical (~65°).
2. **Fin de fermentacion:** A medida que las levaduras convierten el azucar en alcohol etilico (cuya densidad es menor a la del agua), el flotador se sumerge gradualmente y adopta una posicion mas vertical (~25°).

### Formulas Matematicas (Backend):
1. **Calculo del Angulo de Inclinacion:**
   $$\text{tilt} = \text{atan2}\left(\sqrt{a_x^2 + a_y^2}, a_z\right) \times \frac{180}{\pi}$$
2. **Conversion a Grados Brix (°Bx):**
   $$\text{Brix} = \max\Big(0.0,\, \min\big(35.0,\, (\text{tilt} - 25.0) \times 0.60\big)\Big)$$
3. **Conversion a Gravedad Especifica (SG):**
   $$\text{SG} = 1.0000 + (\text{Brix} \times 0.0039)$$

---

## 4. Metricas de Salud de Hardware

### Bateria Li-Po (1S):
* 4.20 V -> 100%
* 3.85 V -> 50%
* 3.30 V -> 0%
$$\text{Porcentaje Bateria} = \max\left(0,\, \min\left(100,\, \frac{\text{Voltaje} - 3.30}{4.20 - 3.30} \times 100\right)\right)$$

### Calidad de Senal Wi-Fi (RSSI):
* >= -60 dBm: Excelente
* -61 dBm a -75 dBm: Buena
* -76 dBm a -85 dBm: Regular
* < -85 dBm: Debil

---

## 5. Contratos de Comunicacion HTTP para el Firmware Arduino

El backend ya se encuentra operativo para recibir peticiones HTTP POST en formato JSON:

### POST /api/telemetria/nodo-cuba (ESP32)
```json
{
  "mac_address": "C8:F0:9E:4B:82:10",
  "cuba_id": 1,
  "temperatura_vino": 18.75,
  "temperatura_ambiente": 20.40,
  "humedad_ambiente": 62.5,
  "voltaje_ph": 2.48,
  "bateria_voltaje": 4.05,
  "rssi": -64
}
```

### POST /api/telemetria/flotador (ESP8266)
```json
{
  "mac_address": "5C:CF:7F:12:34:56",
  "cuba_id": 1,
  "angulo_tilt": 42.50,
  "ax": 0.04,
  "ay": 0.67,
  "az": 0.74,
  "temp_vino": 18.60,
  "bateria_voltaje": 3.90,
  "rssi": -72
}
```

---

## 6. Codigo de Referencia C++ para el Microcontrolador

Para integrar la conexion Wi-Fi y HTTP en los sketches de Arduino existentes, se puede utilizar el siguiente bloque modular dentro del ciclo `loop()`:

```cpp
#include <WiFi.h>        // En ESP8266: #include <ESP8266WiFi.h>
#include <HTTPClient.h>  // En ESP8266: #include <ESP8266HTTPClient.h>

const char* ssid = "WIFI_BODEGA";
const char* password = "PASSWORD_WIFI";
const char* serverUrl = "http://192.168.1.100:8000/api/telemetria/nodo-cuba";

void enviarTelemetria(float tempVino, float tempAmb, float humAmb, float voltPH) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    String json = "{";
    json += "\"mac_address\":\"" + WiFi.macAddress() + "\",";
    json += "\"cuba_id\":1,";
    json += "\"temperatura_vino\":" + String(tempVino, 2) + ",";
    json += "\"temperatura_ambiente\":" + String(tempAmb, 2) + ",";
    json += "\"humedad_ambiente\":" + String(humAmb, 2) + ",";
    json += "\"voltaje_ph\":" + String(voltPH, 3) + ",";
    json += "\"bateria_voltaje\":4.10,";
    json += "\"rssi\":" + String(WiFi.RSSI());
    json += "}";

    int httpCode = http.POST(json);
    if (httpCode > 0) {
      Serial.printf("Telemetria enviada exitosamente (Codigo: %d)\n", httpCode);
    } else {
      Serial.printf("Error en envio HTTP: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  }
}
```
