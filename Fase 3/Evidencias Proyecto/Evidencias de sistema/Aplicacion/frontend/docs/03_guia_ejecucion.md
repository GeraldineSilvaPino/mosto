# 🚀 Guía de Ejecución Local — Frontend MOSTO

Instrucciones claras para poner en marcha el servidor de desarrollo en tu computador, tanto si es la primera vez como para el trabajo de todos los días.

---

## 🛠️ Prerrequisitos

Debes tener instalado **Node.js** (versión 18 o superior). Para comprobarlo, abre una terminal y ejecuta:

```bash
node -v
npm -v
```
*(Si no lo tienes instalado, descárgalo desde [nodejs.org](https://nodejs.org/)).*

---

## 🟢 CASO 1: Si es la PRIMERA VEZ en tu computador

Sigue estos 4 pasos cuando recién descargas o clonas el proyecto:

### 1. Ubícate en la rama `develop`
Abre una terminal en la raíz del proyecto (`mosto`) y escribe:
```bash
git checkout develop
git pull origin develop
```

### 2. Entra a la carpeta `frontend`
```bash
cd frontend
```

### 3. Instala las dependencias del proyecto
Este paso descargará Vue 3, Vite, Vue Router y los iconos. Creará la carpeta `node_modules`:
```bash
npm install
```
*(Este paso solo se realiza una vez).*

### 4. Inicia el servidor de desarrollo
```bash
npm run dev
```

### 5. Abre en tu navegador
Verás un mensaje en la terminal con la dirección local. Abre tu navegador en:
👉 **[http://localhost:5173](http://localhost:5173)**

---

## 🔵 CASO 2: Si YA lo ejecutaste antes (Trabajo Diario)

Las siguientes veces que vayas a trabajar en tu pantalla asignada:

1. Abre tu terminal.
2. Entra a la carpeta del frontend:
   ```bash
   cd frontend
   ```
3. Ejecuta directamente:
   ```bash
   npm run dev
   ```
4. Abre en tu navegador: **http://localhost:5173**

Cada vez que guardes cambios en tu archivo `.vue` o `.css`, la página en el navegador se actualizará automáticamente (Hot Module Replacement).

---

## 🟡 CASO 3: Si un compañero agregó nuevas librerías

Si alguien del equipo instaló un paquete nuevo y subió cambios a `develop`:

```bash
git checkout develop
git pull origin develop
cd frontend
npm install
npm run dev
```

---

## 🛑 Cómo detener el servidor

Cuando hayas terminado tu jornada de trabajo:
1. Haz clic en la terminal donde está corriendo el servidor.
2. Presiona la combinación de teclas **`Ctrl + C`**.
3. Escribe **`S`** o **`Y`** para confirmar si te lo pregunta.

---

## ⚠️ Solución de Problemas Frecuentes

| Problema | Causa | Solución |
| :--- | :--- | :--- |
| **"Could not determine Node.js install directory"** | Abriste la terminal en una ruta que ya no existe o cambió de nombre. | Cierra esa terminal, abre una nueva, entra a `cd frontend` y ejecuta `npm run dev`. |
| **"Port 5173 is in use"** | Tienes otra ventana u otra sesión corriendo Vite. | Vite abrirá automáticamente el puerto `http://localhost:5174`. Si deseas cerrar el anterior, detén la terminal anterior con `Ctrl + C`. |
| **"Cannot find module..."** | Faltan paquetes de npm. | Ejecuta `npm install` dentro de la carpeta `frontend`. |
