<script setup>
/**
 * 📋 07. [FRONT - VUE] Pantalla de Perfil y Umbrales
 * Módulo 4: Hardware y Configuración Operativa
 *
 * Características implementadas:
 * 1. Catálogo interactivo de perfiles enológicos: Tinto Robusto, Tinto Frutal, Blanco Aromático y Perfil Personalizado.
 * 2. Visualizador gráfico del espectro térmico (Zonas: Crítica Fría, Alerta Baja, Banda Óptima, Alerta Alta, Crítica Alta).
 * 3. Formulario con inputs y sliders para calibrar rangos ideales de temperatura (sensor DS18B20).
 * 4. Configuración de reglas de detección de paradas:
 *    - Tasa máxima de gradiente térmico permitido en 2 horas (ej: ±2.0°C).
 *    - Horas de estancamiento de grados Brix antes de alerta (sensor MPU-6050).
 *    - Rango angular de calibración cinemática del flotador.
 * 5. Matriz de asignación de perfiles a cada cuba activa de la viña.
 * 6. Persistencia reactiva local (localStorage y feedback visual con toasts).
 */
import { ref, computed, watch, onMounted } from 'vue'
import {
  SlidersHorizontal,
  Thermometer,
  Compass,
  AlertTriangle,
  CheckCircle2,
  RotateCcw,
  Save,
  Plus,
  Trash2,
  Cylinder,
  Check,
  ShieldCheck,
  Activity,
  Zap,
  Info,
  Layers,
  Sparkles
} from 'lucide-vue-next'

// ==========================================
// PERFILES ENOLÓGICOS PREDETERMINADOS
// ==========================================
const defaultProfiles = [
  {
    id: 'tinto-robusto',
    name: 'Tinto Robusto & Guarda',
    varieties: 'Cabernet Sauvignon, Syrah, Malbec',
    description: 'Perfil para extracción profunda de taninos y color. Permite temperaturas elevadas controladas.',
    critMin: 18.0,
    optimalMin: 22.0,
    optimalMax: 28.0,
    critMax: 31.0,
    maxDelta2h: 2.0,
    stuckBrixHours: 16,
    tiltMin: 10,
    tiltMax: 70
  },
  {
    id: 'tinto-frutal',
    name: 'Tinto Frutal & Joven',
    varieties: 'Carménère, Merlot, Pinot Noir',
    description: 'Enfocado en preservar notas florales y frutales frescas. Moderación térmica continua.',
    critMin: 19.0,
    optimalMin: 23.0,
    optimalMax: 27.0,
    critMax: 29.5,
    maxDelta2h: 1.8,
    stuckBrixHours: 12,
    tiltMin: 12,
    tiltMax: 68
  },
  {
    id: 'blanco-aromatico',
    name: 'Blanco Aromático & Fresco',
    varieties: 'Sauvignon Blanc, Chardonnay, Riesling',
    description: 'Fermentación en frío para retención máxima de ésteres aromáticos y acidez crujiente.',
    critMin: 11.0,
    optimalMin: 13.5,
    optimalMax: 17.0,
    critMax: 19.0,
    maxDelta2h: 1.5,
    stuckBrixHours: 24,
    tiltMin: 15,
    tiltMax: 65
  },
  {
    id: 'personalizado',
    name: 'Perfil Especial de Autor',
    varieties: 'Ensamblajes / Cosecha Tardía',
    description: 'Parámetros a medida configurados por el equipo enológico de la planta principal.',
    critMin: 17.0,
    optimalMin: 21.0,
    optimalMax: 26.5,
    critMax: 29.0,
    maxDelta2h: 1.8,
    stuckBrixHours: 18,
    tiltMin: 10,
    tiltMax: 70
  }
]

// ==========================================
// ASIGNACIÓN DE CUBAS A PERFILES
// ==========================================
const cubasMapping = ref([
  { id: '01', code: 'CB-01', name: 'Cuba 01 · Cabernet Sauvignon', profileId: 'tinto-robusto', currentTemp: 24.6 },
  { id: '02', code: 'CB-02', name: 'Cuba 02 · Carménère Reserva', profileId: 'tinto-frutal', currentTemp: 17.5 },
  { id: '03', code: 'CB-03', name: 'Cuba 03 · Sauvignon Blanc', profileId: 'blanco-aromatico', currentTemp: 15.2 },
  { id: '04', code: 'CB-04', name: 'Cuba 04 · Syrah Gran Corte', profileId: 'tinto-robusto', currentTemp: 26.8 },
  { id: '05', code: 'CB-05', name: 'Cuba 05 · Chardonnay Finca', profileId: 'blanco-aromatico', currentTemp: 14.8 },
  { id: '06', code: 'CB-06', name: 'Cuba 06 · Malbec Single Vineyard', profileId: 'tinto-robusto', currentTemp: 23.2 }
])

// ==========================================
// ESTADO REACTIVO DE CONFIGURACIÓN
// ==========================================
const profiles = ref(JSON.parse(JSON.stringify(defaultProfiles)))
const selectedProfileId = ref('tinto-robusto')
const toastMessage = ref('')

const currentProfile = computed(() => {
  return profiles.value.find(p => p.id === selectedProfileId.value) || profiles.value[0]
})

// Porcentajes para visualizador de espectro térmico
const spectrumBarWidths = computed(() => {
  const minScale = 5.0
  const maxScale = 35.0
  const range = maxScale - minScale

  const p = currentProfile.value
  const leftCold = Math.max(0, ((p.critMin - minScale) / range) * 100)
  const warnLow = Math.max(0, ((p.optimalMin - p.critMin) / range) * 100)
  const optimal = Math.max(0, ((p.optimalMax - p.optimalMin) / range) * 100)
  const warnHigh = Math.max(0, ((p.critMax - p.optimalMax) / range) * 100)
  const leftDanger = Math.max(0, ((maxScale - p.critMax) / range) * 100)

  return { leftCold, warnLow, optimal, warnHigh, leftDanger }
})

// ==========================================
// ACCIONES
// ==========================================
function showToast(msg) {
  toastMessage.value = msg
  setTimeout(() => {
    toastMessage.value = ''
  }, 4000)
}

function handleSaveSettings() {
  localStorage.setItem('mosto_threshold_profiles', JSON.stringify(profiles.value))
  localStorage.setItem('mosto_cubas_mapping', JSON.stringify(cubasMapping.value))
  showToast(`¡Configuración del perfil "${currentProfile.value.name}" guardada con éxito!`)
}

function handleResetDefaults() {
  profiles.value = JSON.parse(JSON.stringify(defaultProfiles))
  localStorage.removeItem('mosto_threshold_profiles')
  showToast('Se han restaurado los valores y umbrales enológicos por defecto.')
}

function handleAssignProfile(cubaId, profileId) {
  const target = cubasMapping.value.find(c => c.id === cubaId)
  if (target) {
    target.profileId = profileId
    const profName = profiles.value.find(p => p.id === profileId)?.name
    showToast(`${target.code} ahora utiliza el perfil: ${profName}.`)
  }
}

// Cargar desde localStorage si existe
onMounted(() => {
  const savedProfiles = localStorage.getItem('mosto_threshold_profiles')
  if (savedProfiles) {
    try {
      profiles.value = JSON.parse(savedProfiles)
    } catch (e) {
      console.error(e)
    }
  }

  const savedMapping = localStorage.getItem('mosto_cubas_mapping')
  if (savedMapping) {
    try {
      cubasMapping.value = JSON.parse(savedMapping)
    } catch (e) {
      console.error(e)
    }
  }
})
</script>

<template>
  <div class="view-container thresholds-view">
    <!-- Toast Flotante -->
    <transition name="toast-fade">
      <div v-if="toastMessage" class="toast-popup">
        <CheckCircle2 :size="16" />
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

    <!-- Header Principal -->
    <header class="thresholds-header">
      <div>
        <div class="module-tag">Módulo 4 · Hardware y Configuración Operativa</div>
        <h1 class="view-title">Perfiles Enológicos y Umbrales</h1>
        <p class="view-subtitle">
          Definición de límites térmicos para sensores DS18B20, reglas de parada por estancamiento de Brix (MPU-6050) y asignación por tipo de cepa.
        </p>
      </div>

      <div class="header-actions">
        <button class="btn-secondary" @click="handleResetDefaults" title="Restablece los umbrales estándar de la industria">
          <RotateCcw :size="15" />
          <span>Restaurar Predeterminados</span>
        </button>

        <button class="btn-primary" @click="handleSaveSettings">
          <Save :size="16" />
          <span>Guardar Configuración</span>
        </button>
      </div>
    </header>

    <!-- Selector de Perfiles Enológicos (Tabs) -->
    <section class="profiles-catalog">
      <div class="catalog-header">
        <h2 class="section-title">Seleccionar Perfil de Fermentación</h2>
        <span class="catalog-hint">Elige un perfil para ajustar sus umbrales o crear uno nuevo</span>
      </div>

      <div class="profiles-grid">
        <div
          v-for="prof in profiles"
          :key="prof.id"
          class="profile-card"
          :class="{ active: selectedProfileId === prof.id }"
          @click="selectedProfileId = prof.id"
        >
          <div class="profile-card-top">
            <span class="profile-tag">{{ prof.varieties }}</span>
            <div class="profile-check-icon">
              <Check :size="14" />
            </div>
          </div>
          <h3 class="profile-name">{{ prof.name }}</h3>
          <p class="profile-desc">{{ prof.description }}</p>

          <div class="profile-pill-range">
            <Thermometer :size="14" />
            <span>Banda óptima: <strong>{{ prof.optimalMin }}°C - {{ prof.optimalMax }}°C</strong></span>
          </div>
        </div>
      </div>
    </section>

    <!-- Visualizador del Espectro Térmico (Termómetro Gráfico) -->
    <section class="spectrum-section">
      <div class="spectrum-header">
        <div class="spectrum-title-area">
          <h3 class="spectrum-title">Espectro de Temperaturas: {{ currentProfile.name }}</h3>
          <p class="spectrum-subtitle">
            Comportamiento de alarmas según la lectura del sensor sumergible DS18B20
          </p>
        </div>

        <div class="spectrum-badge-optimal">
          <ShieldCheck :size="16" />
          <span>Rango seguro activo: {{ currentProfile.optimalMin }}°C a {{ currentProfile.optimalMax }}°C</span>
        </div>
      </div>

      <!-- Barra de Espectro Gráfico -->
      <div class="spectrum-bar-wrapper">
        <div class="spectrum-bar">
          <!-- Zona 1: Frío crítico -->
          <div
            class="zone zone--cold"
            :style="{ width: spectrumBarWidths.leftCold + '%' }"
            title="Parada de fermentación por frío"
          >
            <span>Crítico Frío</span>
          </div>

          <!-- Zona 2: Alerta baja -->
          <div
            class="zone zone--warn-low"
            :style="{ width: spectrumBarWidths.warnLow + '%' }"
            title="Alerta: Baja temperatura"
          >
            <span>Alerta</span>
          </div>

          <!-- Zona 3: Banda Óptima (Verde/Borgoña elegante) -->
          <div
            class="zone zone--optimal"
            :style="{ width: spectrumBarWidths.optimal + '%' }"
            title="Banda óptima de fermentación"
          >
            <span>★ Rango Óptimo de Fermentación</span>
          </div>

          <!-- Zona 4: Alerta alta -->
          <div
            class="zone zone--warn-high"
            :style="{ width: spectrumBarWidths.warnHigh + '%' }"
            title="Alerta: Alta temperatura"
          >
            <span>Alerta</span>
          </div>

          <!-- Zona 5: Calor crítico -->
          <div
            class="zone zone--danger"
            :style="{ width: spectrumBarWidths.leftDanger + '%' }"
            title="Muerte de levaduras por calor"
          >
            <span>Pico Crítico</span>
          </div>
        </div>

        <!-- Marcas numéricas de grados en la escala -->
        <div class="spectrum-markers">
          <div class="marker" :style="{ left: spectrumBarWidths.leftCold + '%' }">
            <span class="marker-line"></span>
            <span class="marker-val">{{ currentProfile.critMin }}°C</span>
            <span class="marker-label">Mín. Crítico</span>
          </div>

          <div class="marker" :style="{ left: (spectrumBarWidths.leftCold + spectrumBarWidths.warnLow) + '%' }">
            <span class="marker-line"></span>
            <span class="marker-val">{{ currentProfile.optimalMin }}°C</span>
            <span class="marker-label">Mín. Óptimo</span>
          </div>

          <div class="marker" :style="{ left: (spectrumBarWidths.leftCold + spectrumBarWidths.warnLow + spectrumBarWidths.optimal) + '%' }">
            <span class="marker-line"></span>
            <span class="marker-val">{{ currentProfile.optimalMax }}°C</span>
            <span class="marker-label">Máx. Óptimo</span>
          </div>

          <div class="marker" :style="{ left: (100 - spectrumBarWidths.leftDanger) + '%' }">
            <span class="marker-line"></span>
            <span class="marker-val">{{ currentProfile.critMax }}°C</span>
            <span class="marker-label">Máx. Crítico</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Formularios de Calibración de Umbrales -->
    <div class="config-grid">
      <!-- 1. Calibración de Límites Térmicos (DS18B20) -->
      <section class="config-card">
        <div class="card-header-clean">
          <div class="card-title-icon icon-wine">
            <Thermometer :size="18" />
            <h3 class="card-title">Límites Térmicos (Sensor DS18B20)</h3>
          </div>
          <span class="sensor-chip-tag">Sonda Térmica</span>
        </div>

        <p class="config-card-desc">
          Ajusta los puntos de corte donde el sistema disparará advertencias enológicas o alertas de emergencia.
        </p>

        <div class="form-inputs-stack">
          <!-- Mínimo Crítico -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Temperatura Mínima Crítica (Riesgo Parada)</span>
              <span class="field-value-badge">{{ currentProfile.critMin.toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.critMin"
                type="range"
                min="10.0"
                max="20.0"
                step="0.5"
                class="slider-input slider--cold"
              />
            </div>
            <span class="field-hint">Bajo este valor las levaduras se aletargan y caen al fondo.</span>
          </div>

          <!-- Mínimo Óptimo -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Temperatura Mínima Óptima</span>
              <span class="field-value-badge badge--optimal">{{ currentProfile.optimalMin.toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.optimalMin"
                type="range"
                min="12.0"
                max="25.0"
                step="0.5"
                class="slider-input slider--optimal"
              />
            </div>
            <span class="field-hint">Punto inferior ideal para la cinética fermentativa de esta cepa.</span>
          </div>

          <!-- Máximo Óptimo -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Temperatura Máxima Óptima</span>
              <span class="field-value-badge badge--optimal">{{ currentProfile.optimalMax.toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.optimalMax"
                type="range"
                min="16.0"
                max="30.0"
                step="0.5"
                class="slider-input slider--optimal"
              />
            </div>
            <span class="field-hint">Límite superior antes de activar camisas de refrigeración.</span>
          </div>

          <!-- Máximo Crítico -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Temperatura Máxima Crítica (Pico Peligroso)</span>
              <span class="field-value-badge badge--danger">{{ currentProfile.critMax.toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.critMax"
                type="range"
                min="20.0"
                max="34.0"
                step="0.5"
                class="slider-input slider--danger"
              />
            </div>
            <span class="field-hint">Superado este punto, las levaduras sufren muerte por shock térmico.</span>
          </div>
        </div>
      </section>

      <!-- 2. Reglas de Detección de Parada y Variaciones Bruscas -->
      <section class="config-card">
        <div class="card-header-clean">
          <div class="card-title-icon icon-amber">
            <Activity :size="18" />
            <h3 class="card-title">Reglas de Detección de Parada</h3>
          </div>
          <span class="sensor-chip-tag">Algoritmo de Reglas</span>
        </div>

        <p class="config-card-desc">
          Reglas basadas en umbrales físicos para detectar anomalías tempranas sin requerir modelos complejos.
        </p>

        <div class="form-inputs-stack">
          <!-- Regla 1: Gradiente Térmico -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Variación Térmica Brusca Permitida (2h)</span>
              <span class="field-value-badge">± {{ currentProfile.maxDelta2h.toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.maxDelta2h"
                type="range"
                min="0.5"
                max="4.0"
                step="0.1"
                class="slider-input slider--amber"
              />
            </div>
            <span class="field-hint">
              Dispara alerta si la cuba sube o baja más de {{ currentProfile.maxDelta2h }}°C en menos de 2 horas.
            </span>
          </div>

          <!-- Regla 2: Estancamiento de Brix -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Horas de Estancamiento de Azúcar (Brix)</span>
              <span class="field-value-badge">{{ currentProfile.stuckBrixHours }} horas</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.stuckBrixHours"
                type="range"
                min="6"
                max="36"
                step="2"
                class="slider-input slider--amber"
              />
            </div>
            <span class="field-hint">
              Si el hidrómetro MPU-6050 no registra descenso en {{ currentProfile.stuckBrixHours }}h, se emite alarma de aletargamiento.
            </span>
          </div>

          <!-- Regla 3: Calibración del Inclinómetro MPU-6050 -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Rango de Calibración Inclinómetro MPU-6050</span>
              <span class="field-value-badge">{{ currentProfile.tiltMin }}° a {{ currentProfile.tiltMax }}°</span>
            </div>
            <div class="dual-range-inputs">
              <div class="range-sub-input">
                <label>Ángulo Mínimo (Líquido Ligero):</label>
                <input
                  v-model.number="currentProfile.tiltMin"
                  type="number"
                  min="5"
                  max="30"
                  class="num-input"
                />
              </div>
              <div class="range-sub-input">
                <label>Ángulo Máximo (Mosto Denso):</label>
                <input
                  v-model.number="currentProfile.tiltMax"
                  type="number"
                  min="50"
                  max="85"
                  class="num-input"
                />
              </div>
            </div>
            <span class="field-hint">Valores fuera de este rango indican sensor encallado en hollejos o descalibrado.</span>
          </div>
        </div>
      </section>
    </div>

    <!-- Panel de Asignación de Perfiles a las Cubas de la Viña -->
    <section class="assignment-section">
      <div class="catalog-header">
        <div>
          <h2 class="section-title">Asignación de Perfiles a Cubas Activas</h2>
          <span class="catalog-hint">Selecciona qué perfil enológico gobierna la telemetría de cada cuba</span>
        </div>
      </div>

      <div class="cubas-assignment-grid">
        <div
          v-for="cuba in cubasMapping"
          :key="cuba.id"
          class="cuba-assignment-card"
        >
          <div class="cuba-assign-top">
            <div class="cuba-badge">
              <Cylinder :size="16" />
              <span>{{ cuba.code }}</span>
            </div>
            <span class="cuba-live-temp">{{ cuba.currentTemp }} °C</span>
          </div>

          <h4 class="cuba-assign-name">{{ cuba.name }}</h4>

          <div class="assign-selector-wrapper">
            <label class="assign-label">Perfil Enológico Aplicado:</label>
            <select
              :value="cuba.profileId"
              @change="handleAssignProfile(cuba.id, $event.target.value)"
              class="assign-select"
            >
              <option v-for="p in profiles" :key="p.id" :value="p.id">
                {{ p.name }} ({{ p.optimalMin }}° - {{ p.optimalMax }}°)
              </option>
            </select>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* =========================================
   ESTILOS DE PERFIL Y UMBRALES
   ========================================= */
.thresholds-view {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
  padding-bottom: 3rem;
}

/* Toast flotante */
.toast-popup {
  position: fixed;
  top: 1.5rem;
  right: 2rem;
  z-index: 9999;
  background-color: var(--wine-900);
  color: #FFFFFF;
  padding: 0.8rem 1.35rem;
  border-radius: var(--radius-md);
  box-shadow: 0 10px 30px rgba(48, 12, 21, 0.3);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.86rem;
  font-weight: 500;
  border: 1px solid var(--wine-700);
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* Header */
.thresholds-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.module-tag {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--wine-700);
  margin-bottom: 0.25rem;
}

.view-title {
  font-family: var(--font-serif);
  font-size: 2.1rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1.15;
  margin-bottom: 0.4rem;
}

.view-subtitle {
  font-size: 0.88rem;
  color: var(--text-secondary);
  max-width: 720px;
  line-height: 1.45;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

/* Catálogo de Perfiles */
.profiles-catalog {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.catalog-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.section-title {
  font-family: var(--font-serif);
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--wine-900);
}

.catalog-hint {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.profiles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.15rem;
}

.profile-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.15rem 1.25rem;
  box-shadow: var(--shadow-subtle);
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.65rem;
  user-select: none;
}

.profile-card:hover {
  border-color: #D3C3BE;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(35, 22, 28, 0.08);
}

.profile-card.active {
  border-color: var(--wine-700);
  background-color: var(--wine-50);
  box-shadow: 0 4px 14px rgba(92, 24, 40, 0.12);
}

.profile-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.profile-tag {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--wine-700);
  letter-spacing: 0.04em;
}

.profile-check-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  color: transparent;
  transition: all 0.15s ease;
}

.profile-card.active .profile-check-icon {
  background-color: var(--wine-700);
  border-color: var(--wine-700);
  color: #FFFFFF;
}

.profile-name {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wine-900);
}

.profile-desc {
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.35;
}

.profile-pill-range {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  padding: 0.3rem 0.6rem;
  border-radius: var(--radius-sm);
  font-size: 0.74rem;
  color: var(--text-primary);
  margin-top: 0.35rem;
}

.profile-pill-range strong {
  font-family: var(--font-mono);
  color: var(--wine-800);
}

/* Espectro Gráfico */
.spectrum-section {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.5rem 1.75rem;
  box-shadow: var(--shadow-subtle);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.spectrum-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.spectrum-title {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--wine-900);
}

.spectrum-subtitle {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.spectrum-badge-optimal {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border: 1px solid var(--status-good-border);
  padding: 0.35rem 0.85rem;
  border-radius: var(--radius-full);
  font-size: 0.78rem;
  font-weight: 600;
}

.spectrum-bar-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-bottom: 1.5rem;
}

.spectrum-bar {
  width: 100%;
  height: 38px;
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);
}

.zone {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  transition: width 0.3s ease;
  overflow: hidden;
  white-space: nowrap;
  padding: 0 0.5rem;
}

.zone--cold {
  background-color: #60A5FA;
  color: #1E3A8A;
}

.zone--warn-low {
  background-color: #FEF3C7;
  color: #92400E;
}

.zone--optimal {
  background-color: #2A6644;
  color: #FFFFFF;
}

.zone--warn-high {
  background-color: #FED7AA;
  color: #9A3412;
}

.zone--danger {
  background-color: #991B2E;
  color: #FFFFFF;
}

.spectrum-markers {
  position: relative;
  width: 100%;
  height: 36px;
}

.marker {
  position: absolute;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: left 0.3s ease;
}

.marker-line {
  width: 2px;
  height: 8px;
  background-color: var(--wine-700);
}

.marker-val {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 700;
  color: var(--wine-900);
  margin-top: 2px;
}

.marker-label {
  font-size: 0.66rem;
  color: var(--text-muted);
  white-space: nowrap;
}

/* Formularios de Configuración */
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

@media (max-width: 900px) {
  .config-grid {
    grid-template-columns: 1fr;
  }
}

.config-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  box-shadow: var(--shadow-subtle);
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

.card-header-clean {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 0.65rem;
}

.card-title-icon {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.icon-wine {
  color: var(--wine-700);
}

.icon-amber {
  color: #C47F17;
}

.card-title {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wine-900);
}

.sensor-chip-tag {
  font-size: 0.7rem;
  font-family: var(--font-mono);
  background-color: var(--bg-subtle);
  color: var(--text-muted);
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.config-card-desc {
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.form-inputs-stack {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.threshold-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.field-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.field-value-badge {
  font-family: var(--font-mono);
  font-size: 0.84rem;
  font-weight: 700;
  color: var(--wine-900);
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  padding: 0.15rem 0.55rem;
  border-radius: var(--radius-sm);
}

.badge--optimal {
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border-color: var(--status-good-border);
}

.badge--danger {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border-color: var(--status-danger-border);
}

.slider-row {
  display: flex;
  align-items: center;
}

.slider-input {
  width: 100%;
  accent-color: var(--wine-700);
  cursor: pointer;
}

.slider--cold {
  accent-color: #3B82F6;
}

.slider--optimal {
  accent-color: #2A6644;
}

.slider--danger {
  accent-color: #991B2E;
}

.slider--amber {
  accent-color: #D97706;
}

.field-hint {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.3;
}

.dual-range-inputs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.range-sub-input {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.range-sub-input label {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.num-input {
  width: 100%;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.82rem;
  background-color: var(--bg-canvas);
}

/* Asignación a Cubas */
.assignment-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.cubas-assignment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.15rem;
}

.cuba-assignment-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.15rem;
  box-shadow: var(--shadow-subtle);
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.cuba-assign-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cuba-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background-color: var(--wine-100);
  color: var(--wine-800);
  font-weight: 700;
  font-size: 0.76rem;
  padding: 0.2rem 0.5rem;
  border-radius: var(--radius-sm);
}

.cuba-live-temp {
  font-family: var(--font-mono);
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-secondary);
}

.cuba-assign-name {
  font-size: 0.86rem;
  font-weight: 600;
  color: var(--text-primary);
}

.assign-selector-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-top: 0.25rem;
}

.assign-label {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.assign-select {
  width: 100%;
  padding: 0.45rem 0.65rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.78rem;
  font-family: inherit;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.assign-select:focus {
  border-color: var(--wine-700);
}
</style>
