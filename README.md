# Mosto: Plataforma de Telemetría IoT y Analítica Predictiva para Fermentación Vitivinícola

Plataforma orientada al monitoreo continuo y supervisión predictiva de variables críticas en cubas vitivinícolas, desarrollada para bodegas medianas y pequeñas. El sistema mitiga pérdidas económicas por fermentaciones detenidas o desvíos térmicos mediante la adquisición periódica de telemetría y detección temprana de anomalías con Machine Learning.

> **Estado del Proyecto:** Fase 1 (Definición, Análisis y Diseño de Arquitectura).

---

## Características Planificadas

### Módulos del Sistema
- **Módulo de Telemetría y Captura (IoT):** Adquisición continua de mediciones críticas (temperatura del mosto y densidad) desde microcontroladores, transmitiendo lecturas periódicas mediante MQTT.
- **Módulo de Analítica y Detección Temprana (ML):** Servicio de inferencia sobre series temporales enfocado en clasificar desviaciones térmicas y riesgos de estancamiento cinético (*stuck fermentation*) antes de que el daño biológico sea irreversible.
- **Panel de Supervisión (Dashboard Web):** Visualización interactiva por cuba/barril con curvas cinéticas en tiempo real, histórico de lotes, proyección de término y despachos de alarma.
- **Servicios Backend y Gestión Operacional:** Ingesta de paquetes telemáticos, persistencia de series de tiempo, reglas de negocio y control de acceso por roles.

---

## Stack Tecnológico Definido

### Captura y Telemetría (IoT)
- **Microcontrolador:** ESP32
- **Sensores:** Sondas estancas sumergibles (DS18B20 para temperatura)
- **Protocolo de Ingesta:** MQTT / API REST

### Backend y Analítica
- **Lenguaje:** Python
- **Framework API:** FastAPI / Flask
- **Modelos y Analítica:** Scikit-Learn, Pandas, NumPy (Pipeline bajo estándar CRISP-DM)
- **Base de Datos:** PostgreSQL (optimizado para persistencia de series de tiempo)

### Frontend
- **Framework:** Vue.js
- **Visualización de Datos:** Chart.js 
- **Estilos:** TailwindCSS

### Infraestructura 
- **Contenedores:** Docker & Docker Compose

---

## Estructura de la Solución (Arquitectura)

La solución se estructura bajo un enfoque modular desacoplado en capas:
- **Capa de Captura:** Microcontrolador en banco de pruebas enviando lecturas periódicas.
- **Capa de Ingesta y Datos:** Broker MQTT / API Backend validando payloads e insertando registros temporales en base de datos relacional.
- **Capa Analítica:** Pipeline de inferencia que evalúa las ventanas de tiempo recientes y detecta anomalías.
- **Capa de Presentación:** Dashboard web reactivo para consumo de los operadores y enólogos.

---

## Metodología y Planificación

El proyecto se gestiona mediante un **enfoque híbrido**:
- **Gestión Ágil (Scrum):** Sprints iterativos de 2 a 3 semanas para desarrollo de incrementos modulares.
- **CRISP-DM:** Marco sistemático para el preprocesamiento, ingeniería de variables y evaluación del modelo de Machine Learning.
- **Control Curricular por Fases:**
  - **Fase 1 (Actual):** Levantamiento de Requerimientos, Diseño Arquitectónico UML y Modelo de Datos.
  - **Fase 2:** Construcción del Prototipo IoT, Servicios Backend, Entrenamiento ML y Dashboard Web.
  - **Fase 3:** Plan Integral de Pruebas (QA), Contenedorización con Docker y Cierre Técnico.

---

## Integrantes y Roles

**CAPSTONE - Equipo de Proyecto**

- **Carlos Cartes** — Líder de Desarrollo Backend, Frontend y Arquitectura de Software
- **Matías González** — Especialista en Captura IoT, Redes y Modelo de Datos
- **Geraldine Silva** — Especialista en Machine Learning, Modelamiento Analítico y QA

---

## Información Institucional

- **Asignatura:** Proyecto APT (Capstone)
- **Institución:** Duoc UC
- **Versión:** 0.1.0 (Fase 1)  
- **Año:** 2026