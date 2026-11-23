# 🌿 Guía de Flujo Git y Metodología de Trabajo

Esta guía establece el estándar de desarrollo colaborativo para el equipo en el repositorio de **MOSTO**.

---

## 🏛️ 1. Estructura de Ramas

Trabajamos bajo una versión simplificada de **Gitflow**:

- **`main`**: Rama de producción / entregables evaluados. **Nadie sube código directo aquí.**
- **`develop`**: Rama base de integración y trabajo activo del equipo. Aquí se integran las pantallas terminadas.
- **`feature/<numero>-<nombre>`**: Ramas temporales e independientes que cada integrante crea para su pantalla asignada.

---

## 🚀 2. Flujo de Trabajo Paso a Paso (Al tomar una tarjeta)

### Paso 1: Actualizar `develop` en tu máquina
Antes de crear cualquier rama nueva, asegúrate de tener la última versión del proyecto:
```bash
git checkout develop
git pull origin develop
```

### Paso 2: Crear tu rama según el número de tarjeta
Usa el prefijo `feature/`, el número correlativo de dos dígitos (`01`, `02`, etc.) y el nombre breve de la pantalla:
```bash
# Ejemplos:
git checkout -b feature/01-login
git checkout -b feature/03-dashboard
git checkout -b feature/06-dispositivos
```

### Paso 3: Desarrollar exclusivamente en tu pantalla
1. Dirígete a la carpeta `frontend/`:
   ```bash
   cd frontend
   npm run dev
   ```
2. Abre tu archivo asignado en `frontend/src/views/` (ej. `LoginView.vue`).
3. Realiza la maquetación y la lógica simulada requerida por la tarjeta.
4. **Importante:** No modifiques los archivos de vistas de tus compañeros para evitar conflictos de merge.

### Paso 4: Guardar commits descriptivos
Haz commits frecuentes y claros siguiendo el estándar convencional:
```bash
git add .
git commit -m "feat(front): maquetar formulario de login con validaciones visuales"
```

### Paso 5: Subir tu rama al repositorio remoto
```bash
git push -u origin feature/01-login
```

### Paso 6: Integración hacia `develop`
Una vez terminada y probada la pantalla:
1. Si utilizan GitHub/GitLab: Crea un **Pull Request (PR)** desde `feature/01-login` hacia `develop`.
2. Si hacen merge local:
   ```bash
   git checkout develop
   git pull origin develop
   git merge feature/01-login
   git push origin develop
   ```
3. Mueve la tarjeta correspondiente en Trello a la columna **"Terminada" / "Hecho"**.

---

## 🛡️ 3. Reglas de Convivencia y Buenas Prácticas

1. **Nunca trabajes directo sobre `develop` ni `main`:** Siempre crea una rama `feature/`.
2. **Archivos ignorados:** Nunca subas carpetas como `node_modules/` o `dist/`. Ya están protegidas en el archivo `.gitignore`.
3. **Mantén el diseño coherente:** Usa las clases y variables CSS definidas en `frontend/src/style.css` (colores vino `--wine-700`, fondos oscuros, botones reutilizables).
4. **Simulación sin backend:** Como esta fase es 100% frontend, utiliza datos mock locales (`ref([])` o arrays estáticos) y `setTimeout` para simular llamadas asíncronas.
5. **Si necesitas ayuda con un conflicto de Git:** Notifica al equipo antes de forzar cambios (`git push -f` está prohibido).
