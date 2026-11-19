# 📋 Tarjetas de Trabajo Frontend — Proyecto MOSTO
## Desglose de Pantallas y Tareas Técnicas (Vue 3)

Este documento contiene **exclusivamente** el listado y detalle de las tarjetas de Trello asignadas para el desarrollo del frontend. Cada tarjeta tiene un identificador numérico correlativo (`01` al `11`) para facilitar la organización de ramas y asignaciones.

---

## 📌 Tabla Resumen de Pantallas

| N° | Módulo | Pantalla / Tarjeta de Trello | Archivo Asignado | Ruta Local |
| :---: | :--- | :--- | :--- | :--- |
| **01** | Módulo 1: Autenticación | Inicio de Sesión | `frontend/src/views/LoginView.vue` | `/login` |
| **02** | Módulo 1: Autenticación | Recuperación de Contraseña | `frontend/src/views/ForgotPasswordView.vue` | `/recuperar-password` |
| **03** | Módulo 2: Monitoreo en Vivo | Dashboard General (Dash) | `frontend/src/views/DashboardView.vue` | `/` o `/dashboard` |
| **04** | Módulo 2: Monitoreo en Vivo | Detalle de Cuba | `frontend/src/views/CubaDetailView.vue` | `/cuba-detalle` |
| **05** | Módulo 3: Alertas y Protocolo | Alertas y Gestión de Incidencias | `frontend/src/views/AlertsView.vue` | `/alertas` |
| **06** | Módulo 4: Hardware y Config. | Dispositivos IoT | `frontend/src/views/DevicesView.vue` | `/dispositivos` |
| **07** | Módulo 4: Hardware y Config. | Perfil y Umbrales | `frontend/src/views/ThresholdsView.vue` | `/perfiles-umbrales` |
| **08** | Módulo 4: Hardware y Config. | Bitácora Enológica | `frontend/src/views/BinnacleView.vue` | `/bitacora` |
| **09** | Módulo 5: Administración SaaS | Gestión de Usuarios y Roles | `frontend/src/views/UsersView.vue` | `/usuarios` |
| **10** | Módulo 5: Administración SaaS | Configuración Empresa / Viña | `frontend/src/views/CompanyConfigView.vue` | `/configuracion-empresa` |
| **11** | Módulo 5: Administración SaaS | Historial de Alertas / Auditoría | `frontend/src/views/AlertsAuditView.vue` | `/historial-alertas` |

---

## 📂 Módulo 1: Autenticación y Acceso

### 01. [FRONT - VUE] Pantalla de Inicio de Sesión
- **Archivo:** `frontend/src/views/LoginView.vue`
- **Ruta:** `/login`
- **Rama recomendada:** `feature/01-login`
- **Descripción:** Desarrollar la vista estática e interactiva de autenticación para el acceso inicial al SaaS.
- **Tareas técnicas (Vue.js):**
  1. Maquetar el formulario con campos de correo y contraseña (usando componentes reutilizables y validaciones visuales).
  2. Simular la autenticación localmente (mock de respuesta exitosa/fallida con un token falso) sin requerir el backend aún.
  3. Implementar la redirección al Dashboard general al hacer clic en entrar.

---

### 02. [FRONT - VUE] Pantalla de Recuperación de Contraseña
- **Archivo:** `frontend/src/views/ForgotPasswordView.vue`
- **Ruta:** `/recuperar-password`
- **Rama recomendada:** `feature/02-recuperar-password`
- **Descripción:** Crear la vista de apoyo para restablecer la contraseña en caso de olvido.
- **Tareas técnicas (Vue.js):**
  1. Diseñar la interfaz con el campo de correo electrónico y un botón de envío.
  2. Añadir un mensaje visual de éxito simulado (feedback al usuario) confirmando que se envió el enlace de recuperación.

---

## 📂 Módulo 2: Monitoreo en Vivo (Core)

### 03. [FRONT - VUE] Pantalla de Dashboard General (Dash)
- **Archivo:** `frontend/src/views/DashboardView.vue`
- **Ruta:** `/` o `/dashboard`
- **Rama recomendada:** `feature/03-dashboard`
- **Descripción:** Panel principal que muestra una vista panorámica y simulada de todas las cubas activas en la bodega.
- **Tareas técnicas (Vue.js):**
  1. Crear una cuadrícula (grid) responsive de tarjetas de cubas utilizando datos mock estáticos o un array local (ej. Cuba 1, Cuba 2, etc.).
  2. Diseñar los indicadores visuales rápidos (temperatura actual, grados Brix y semáforos de estado: Normal, Advertencia, Crítico) basándose en los datos simulados.

---

### 04. [FRONT - VUE] Pantalla de Detalle de Cuba
- **Archivo:** `frontend/src/views/CubaDetailView.vue`
- **Ruta:** `/cuba-detalle` (o `/cubas/:id`)
- **Rama recomendada:** `feature/04-detalle-cuba`
- **Descripción:** Vista profunda enfocada en el comportamiento individual y simulado de una cuba seleccionada.
- **Tareas técnicas (Vue.js):**
  1. Integrar una librería de gráficos (como Chart.js o Vue-Chartjs) para graficar curvas temporales de temperatura (DS18B20) y densidad/inclinación (MPU-6050) usando datasets de prueba.
  2. Crear paneles numéricos que muestren los valores métricos simulados de la cuba activa.

---

## 📂 Módulo 3: Alertas y Protocolo

### 05. [FRONT - VUE] Pantalla de Alertas y Gestión de Incidencias
- **Archivo:** `frontend/src/views/AlertsView.vue`
- **Ruta:** `/alertas`
- **Rama recomendada:** `feature/05-alertas`
- **Descripción:** Centro de control visual para mostrar alertas simuladas por cambios bruscos de temperatura o fallas en sensores.
- **Tareas técnicas (Vue.js):**
  1. Maquetar la tabla o lista de alertas activas con datos estáticos de prueba clasificados por nivel de severidad.
  2. Diseñar la interfaz para simular el protocolo de revisión del enólogo (permite probar visualmente la acción de anular el sensor o registrar notas estáticas de prueba).

---

## 📂 Módulo 4: Hardware y Configuración Operativa

### 06. [FRONT - VUE] Pantalla de Dispositivos IoT
- **Archivo:** `frontend/src/views/DevicesView.vue`
- **Ruta:** `/dispositivos`
- **Rama recomendada:** `feature/06-dispositivos`
- **Descripción:** Panel visual de administración para listar el estado simulado del hardware instalado en la bodega.
- **Tareas técnicas (Vue.js):**
  1. Listar dispositivos ESP32 ficticios, mostrando su estado simulado de conexión (Online/Offline) y nivel de señal.
  2. Crear un formulario o modal interactivo de prueba para simular el emparejamiento de un nuevo sensor físico a una cuba.

---

### 07. [FRONT - VUE] Pantalla de Perfil y Umbrales
- **Archivo:** `frontend/src/views/ThresholdsView.vue`
- **Ruta:** `/perfiles-umbrales`
- **Rama recomendada:** `feature/07-perfiles-umbrales`
- **Descripción:** Vista de formulario para ajustar de manera visual los parámetros y límites de temperatura.
- **Tareas técnicas (Vue.js):**
  1. Maquetar los campos de configuración para definir rangos ideales de temperatura y delta de cambio permitido (los cambios se guardan localmente o muestran alerta de éxito visual sin backend).

---

### 08. [FRONT - VUE] Pantalla de Bitácora
- **Archivo:** `frontend/src/views/BinnacleView.vue`
- **Ruta:** `/bitacora`
- **Rama recomendada:** `feature/08-bitacora`
- **Descripción:** Registro cronológico visual de notas y eventos simulados realizados por los enólogos.
- **Tareas técnicas (Vue.js):**
  1. Crear una vista en formato de línea de tiempo (timeline) o tabla alimentada con notas estáticas de prueba.
  2. Añadir un formulario rápido para agregar nuevas notas simuladas a la lista localmente.

---

## 📂 Módulo 5: Administración SaaS y Gestión de Empresa

### 09. [FRONT - VUE] Pantalla de Gestión de Usuarios y Roles
- **Archivo:** `frontend/src/views/UsersView.vue`
- **Ruta:** `/usuarios`
- **Rama recomendada:** `feature/09-usuarios-roles`
- **Descripción:** Interfaz visual para controlar al personal interno de la viña de forma simulada.
- **Tareas técnicas (Vue.js):**
  1. Listar usuarios ficticios de la empresa con sus respectivos roles (Administrador, Enólogo, Operario).
  2. Crear la interfaz visual para simular la invitación de nuevos usuarios por correo y asignación de permisos.

---

### 10. [FRONT - VUE] Pantalla de Configuración de la Empresa / Viña
- **Archivo:** `frontend/src/views/CompanyConfigView.vue`
- **Ruta:** `/configuracion-empresa`
- **Rama recomendada:** `feature/10-configuracion-empresa`
- **Descripción:** Vista administrativa estática de los datos generales del cliente dentro del SaaS.
- **Tareas técnicas (Vue.js):**
  1. Maquetar los campos de datos fiscales, nombre de la bodega y logotipo de prueba.
  2. Mostrar de forma informativa el plan contratado simulado y el estado de la cuenta.

---

### 11. [FRONT - VUE] Pantalla de Historial de Alertas / Auditoría
- **Archivo:** `frontend/src/views/AlertsAuditView.vue`
- **Ruta:** `/historial-alertas`
- **Rama recomendada:** `feature/11-historial-alertas`
- **Descripción:** Archivo general visual con datos de prueba de todas las alarmas pasadas.
- **Tareas técnicas (Vue.js):**
  1. Diseñar una tabla estática con filtros visuales por rango de fechas y estados de resolución para validar la interfaz de reportes.
