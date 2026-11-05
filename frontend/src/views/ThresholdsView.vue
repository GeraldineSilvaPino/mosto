<script setup>
/**
 * 📋 07. [FRONT - VUE] Pantalla de Perfiles Enológicos y Umbrales
 * Módulo 4: Hardware y Configuración Operativa
 *
 * Conectado con la API REST de FastAPI y PostgreSQL / Supabase:
 * - GET /api/perfiles (Carga de perfiles activos)
 * - POST /api/perfiles (Creación de nuevo perfil enológico)
 * - PUT /api/perfiles/{id} (Actualización de bandas térmicas y acidez)
 * - DELETE /api/perfiles/{id} (Desactivación soft-delete con control de procesos activos)
 */
import { ref, computed, onMounted } from 'vue'
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
  Sparkles,
  RefreshCw,
  X,
  FlaskConical
} from 'lucide-vue-next'
import profileService from '../services/profileService.js'
import cubaService from '../services/cubaService.js'

// ==========================================
// ESTADO REACTIVO PRINCIPAL
// ==========================================
const profiles = ref([])
const selectedProfileId = ref(null)
const isLoadingProfiles = ref(false)
const isSaving = ref(false)
const isDeleting = ref(false)
const toastMessage = ref('')
const formError = ref(null)
const globalError = ref(null)

// Modal de Creación de Perfil
const isCreateModalOpen = ref(false)
const isCreating = ref(false)
const createError = ref(null)
const newProfileForm = ref({
  nomb_perfil: '',
  cepa_id: 1,
  bodega_id: 5,
  temp_min: 18.0,
  temp_max: 26.0,
  ph_min: 3.20,
  ph_max: 3.80,
  brix_caida_min_dia: 1.50
})

// Modal de Desactivación de Perfil
const isDeleteModalOpen = ref(false)
const deleteError = ref(null)

// Catálogo de Cepas Disponibles para Selección
const availableCepas = ref([
  { id: 1, name: 'Cabernet Sauvignon' },
  { id: 2, name: 'Carménère' },
  { id: 3, name: 'Sauvignon Blanc' },
  { id: 4, name: 'Syrah' },
  { id: 5, name: 'Chardonnay' },
  { id: 6, name: 'Malbec' }
])

// Asignación de Cubas
const cubasMapping = ref([
  { id: '1', code: 'CB-01', name: 'Cuba 01 · Cabernet Sauvignon', profileId: 2, currentTemp: 24.6 },
  { id: '2', code: 'CB-02', name: 'Cuba 02 · Carménère Reserva', profileId: 2, currentTemp: 17.5 },
  { id: '3', code: 'CB-03', name: 'Cuba 03 · Sauvignon Blanc', profileId: 2, currentTemp: 15.2 },
  { id: '4', code: 'CB-04', name: 'Cuba 04 · Syrah Gran Corte', profileId: 2, currentTemp: 26.8 },
  { id: '5', code: 'CB-05', name: 'Cuba 05 · Chardonnay Finca', profileId: 2, currentTemp: 14.8 },
  { id: '6', code: 'CB-06', name: 'Cuba 06 · Malbec Single Vineyard', profileId: 2, currentTemp: 23.2 }
])

// ==========================================
// MAPEO DE DATOS BACKEND ⇄ VISTA
// ==========================================
function mapBackendProfile(p) {
  const tempMin = p.temp_min !== null && p.temp_min !== undefined ? Number(p.temp_min) : 18.0
  const tempMax = p.temp_max !== null && p.temp_max !== undefined ? Number(p.temp_max) : 28.0
  const critMin = p.crit_min !== null && p.crit_min !== undefined ? Number(p.crit_min) : Math.round((tempMin - 4.0) * 10) / 10
  const critMax = p.crit_max !== null && p.crit_max !== undefined ? Number(p.crit_max) : Math.round((tempMax + 3.0) * 10) / 10

  const phMin = p.ph_min !== null && p.ph_min !== undefined ? Number(p.ph_min) : 3.20
  const phMax = p.ph_max !== null && p.ph_max !== undefined ? Number(p.ph_max) : 3.80
  const brixCaida = p.brix_caida_min_dia !== null && p.brix_caida_min_dia !== undefined ? Number(p.brix_caida_min_dia) : 1.50

  return {
    id: p.id,
    name: p.nomb_perfil,
    varieties: p.cepa_nombre || 'Cepas Enológicas',
    description: `Perfil calibrado para ${p.cepa_nombre || 'variedad enológica'}. Bandas térmicas en bodega ${p.bodega_nombre || 'Principal'}.`,
    optimalMin: tempMin,
    optimalMax: tempMax,
    critMin: critMin,
    critMax: critMax,
    phMin: phMin,
    phMax: phMax,
    brixCaidaMinDia: brixCaida,
    bodegaId: p.bodega_id || 5,
    bodegaNombre: p.bodega_nombre || 'Bodega Principal',
    cepaId: p.cepa_id || 1,
    cepaNombre: p.cepa_nombre || 'Cabernet Sauvignon',
    activo: p.activo,
    // Reglas extendidas
    maxDelta2h: 2.0,
    stuckBrixHours: 16,
    tiltMin: 10,
    tiltMax: 70
  }
}

const currentProfile = computed(() => {
  return profiles.value.find(p => p.id === selectedProfileId.value) || profiles.value[0] || null
})

// Porcentajes para visualizador de espectro térmico
const spectrumBarWidths = computed(() => {
  if (!currentProfile.value) {
    return { leftCold: 20, warnLow: 15, optimal: 30, warnHigh: 15, leftDanger: 20 }
  }

  const minScale = 5.0
  const maxScale = 35.0
  const range = maxScale - minScale

  const p = currentProfile.value
  const leftCold = Math.max(0, ((p.critMin - minScale) / range) * 100)
  const warnLow = Math.max(0, Math.min(100, ((p.optimalMin - p.critMin) / range) * 100))
  const optimal = Math.max(0, Math.min(100, ((p.optimalMax - p.optimalMin) / range) * 100))
  const warnHigh = Math.max(0, Math.min(100, ((p.critMax - p.optimalMax) / range) * 100))
  const leftDanger = Math.max(0, ((maxScale - p.critMax) / range) * 100)

  return { leftCold, warnLow, optimal, warnHigh, leftDanger }
})

// ==========================================
// ACCIONES Y LLAMADAS A LA API
// ==========================================
function showToast(msg) {
  toastMessage.value = msg
  setTimeout(() => {
    toastMessage.value = ''
  }, 4000)
}

// Carga inicial del catálogo de perfiles activos
async function loadProfiles(isManual = false) {
  if (isManual) isLoadingProfiles.value = true
  globalError.value = null
  try {
    const data = await profileService.listarPerfiles({ activo: true })
    if (Array.isArray(data) && data.length > 0) {
      profiles.value = data.map(mapBackendProfile)
      if (!selectedProfileId.value || !profiles.value.some(p => p.id === selectedProfileId.value)) {
        selectedProfileId.value = profiles.value[0].id
      }
    } else {
      // Si no hay activos, intentar cargar catálogo general
      const allData = await profileService.listarPerfiles({})
      if (Array.isArray(allData) && allData.length > 0) {
        profiles.value = allData.map(mapBackendProfile)
        selectedProfileId.value = profiles.value[0].id
      }
    }

    // Cargar sincronización de cubas
    try {
      const cubasData = await cubaService.listarCubas()
      if (Array.isArray(cubasData) && cubasData.length > 0) {
        cubasMapping.value = cubasData.map(c => ({
          id: String(c.id),
          code: c.codigo_cuba || `CB-${String(c.id).padStart(2, '0')}`,
          name: c.nombre || `Cuba ${c.codigo_cuba || c.id}`,
          profileId: c.proceso_activo_id && c.proceso_activo?.perfil_id ? c.proceso_activo.perfil_id : (profiles.value[0]?.id || null),
          currentTemp: c.ultima_temperatura || 21.5
        }))
      }
    } catch {
      // Ignorar fallback de cubas
    }
  } catch (err) {
    console.error('Error al conectar con GET /api/perfiles:', err)
    globalError.value = err.message || 'Error de conexión con el catálogo de perfiles enológicos'
    showToast('Aviso: Catálogo cargado en modo contingencia.')
  } finally {
    if (isManual) isLoadingProfiles.value = false
  }
}

// Guardar / Actualizar configuración de umbrales
async function handleSaveSettings() {
  if (!currentProfile.value) return
  formError.value = null

  // 1. Validación estricta previa en frontend (ck_perfil_temp)
  if (Number(currentProfile.value.optimalMin) > Number(currentProfile.value.optimalMax)) {
    formError.value = `Inconsistencia térmica: temp_min (${currentProfile.value.optimalMin}°C) no puede ser mayor que temp_max (${currentProfile.value.optimalMax}°C) [ck_perfil_temp].`
    return
  }

  // 2. Validación estricta previa en frontend (ck_perfil_ph)
  if (
    currentProfile.value.phMin !== null &&
    currentProfile.value.phMax !== null &&
    Number(currentProfile.value.phMin) > Number(currentProfile.value.phMax)
  ) {
    formError.value = `Inconsistencia de acidez: ph_min (${currentProfile.value.phMin}) no puede ser mayor que ph_max (${currentProfile.value.phMax}) [ck_perfil_ph].`
    return
  }

  isSaving.value = true
  try {
    if (typeof currentProfile.value.id === 'number') {
      const payload = {
        nomb_perfil: currentProfile.value.name,
        temp_min: Number(currentProfile.value.optimalMin),
        temp_max: Number(currentProfile.value.optimalMax),
        ph_min: Number(currentProfile.value.phMin),
        ph_max: Number(currentProfile.value.phMax),
        brix_caida_min_dia: Number(currentProfile.value.brixCaidaMinDia)
      }

      const updated = await profileService.actualizarPerfil(currentProfile.value.id, payload)
      const mapped = mapBackendProfile(updated)
      const idx = profiles.value.findIndex(p => p.id === currentProfile.value.id)
      if (idx !== -1) {
        profiles.value[idx] = { ...profiles.value[idx], ...mapped }
      }
    }

    showToast(`¡Configuración del perfil "${currentProfile.value.name}" guardada y sincronizada con éxito!`)
  } catch (err) {
    console.error('Error al actualizar perfil en backend:', err)
    formError.value = err.message || 'Error del servidor al persistir los umbrales del perfil.'
  } finally {
    isSaving.value = false
  }
}

// Modal de Desactivación
function openDeleteModal() {
  if (!currentProfile.value) return
  deleteError.value = null
  isDeleteModalOpen.value = true
}

function closeDeleteModal() {
  if (isDeleting.value) return
  isDeleteModalOpen.value = false
  deleteError.value = null
}

async function handleConfirmDelete() {
  if (!currentProfile.value) return
  isDeleting.value = true
  deleteError.value = null

  try {
    if (typeof currentProfile.value.id === 'number') {
      await profileService.desactivarPerfil(currentProfile.value.id)
    }

    const deletedName = currentProfile.value.name
    const deletedId = currentProfile.value.id

    // Remover del catálogo local reactivo
    profiles.value = profiles.value.filter(p => p.id !== deletedId)
    if (profiles.value.length > 0) {
      selectedProfileId.value = profiles.value[0].id
    } else {
      selectedProfileId.value = null
    }

    closeDeleteModal()
    showToast(`Perfil "${deletedName}" desactivado con éxito.`)
  } catch (err) {
    console.error('Error al desactivar perfil:', err)
    // Mostrar mensaje explícito de negocio (ej: si está asignado a un proceso activo)
    deleteError.value = err.message || 'No se pudo desactivar el perfil de fermentación.'
  } finally {
    isDeleting.value = false
  }
}

// Modal de Creación de Perfil
function openCreateModal() {
  newProfileForm.value = {
    nomb_perfil: '',
    cepa_id: 1,
    bodega_id: 5,
    temp_min: 18.0,
    temp_max: 26.0,
    ph_min: 3.20,
    ph_max: 3.80,
    brix_caida_min_dia: 1.50
  }
  createError.value = null
  isCreateModalOpen.value = true
}

function closeCreateModal() {
  if (isCreating.value) return
  isCreateModalOpen.value = false
  createError.value = null
}

async function handleCreateProfile() {
  createError.value = null

  if (!newProfileForm.value.nomb_perfil || newProfileForm.value.nomb_perfil.trim().length < 2) {
    createError.value = 'El nombre descriptivo del perfil debe tener al menos 2 caracteres.'
    return
  }

  // Validación previa de rangos
  if (Number(newProfileForm.value.temp_min) > Number(newProfileForm.value.temp_max)) {
    createError.value = `Inconsistencia térmica: temp_min (${newProfileForm.value.temp_min}°C) no puede ser mayor que temp_max (${newProfileForm.value.temp_max}°C) [ck_perfil_temp].`
    return
  }

  if (
    newProfileForm.value.ph_min !== null &&
    newProfileForm.value.ph_max !== null &&
    Number(newProfileForm.value.ph_min) > Number(newProfileForm.value.ph_max)
  ) {
    createError.value = `Inconsistencia de acidez: ph_min (${newProfileForm.value.ph_min}) no puede ser mayor que ph_max (${newProfileForm.value.ph_max}) [ck_perfil_ph].`
    return
  }

  isCreating.value = true
  try {
    const payload = {
      nomb_perfil: newProfileForm.value.nomb_perfil.trim(),
      cepa_id: Number(newProfileForm.value.cepa_id),
      bodega_id: Number(newProfileForm.value.bodega_id),
      temp_min: Number(newProfileForm.value.temp_min),
      temp_max: Number(newProfileForm.value.temp_max),
      ph_min: Number(newProfileForm.value.ph_min),
      ph_max: Number(newProfileForm.value.ph_max),
      brix_caida_min_dia: Number(newProfileForm.value.brix_caida_min_dia),
      activo: true
    }

    const nuevo = await profileService.crearPerfil(payload)
    const mapped = mapBackendProfile(nuevo)
    profiles.value.push(mapped)
    selectedProfileId.value = mapped.id

    closeCreateModal()
    showToast(`¡Perfil enológico "${mapped.name}" creado y persistido con éxito!`)
  } catch (err) {
    console.error('Error al crear perfil en backend:', err)
    createError.value = err.message || 'Error del servidor al crear el nuevo perfil enológico.'
  } finally {
    isCreating.value = false
  }
}

function handleAssignProfile(cubaId, profileId) {
  const target = cubasMapping.value.find(c => c.id === cubaId)
  if (target) {
    target.profileId = Number(profileId) || profileId
    const profName = profiles.value.find(p => p.id === target.profileId)?.name
    showToast(`${target.code} ahora utiliza el perfil: ${profName || 'Personalizado'}.`)
  }
}

onMounted(() => {
  loadProfiles(true)
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
          Definición de límites térmicos (sensor DS18B20), bandas de acidez pH (PH-4502C), reglas de parada por estancamiento de Brix y persistencia REST.
        </p>
      </div>

      <div class="header-actions">
        <button
          class="btn-secondary"
          :disabled="isLoadingProfiles"
          @click="loadProfiles(true)"
          title="Recargar catálogo desde el backend"
        >
          <RefreshCw :size="15" :class="{ 'spin-icon': isLoadingProfiles }" />
          <span>{{ isLoadingProfiles ? 'Sincronizando...' : 'Recargar Catálogo' }}</span>
        </button>

        <button class="btn-secondary btn-new-profile" @click="openCreateModal">
          <Plus :size="16" />
          <span>Nuevo Perfil</span>
        </button>

        <button
          v-if="currentProfile"
          class="btn-danger-outline"
          :disabled="isDeleting"
          @click="openDeleteModal"
          title="Desactivar este perfil del catálogo de fermentación"
        >
          <Trash2 :size="15" />
          <span>Desactivar Perfil</span>
        </button>

        <button
          class="btn-primary"
          :disabled="isSaving || !currentProfile"
          @click="handleSaveSettings"
        >
          <RefreshCw v-if="isSaving" :size="16" class="spin-icon" />
          <Save v-else :size="16" />
          <span>{{ isSaving ? 'Guardando en BD...' : 'Guardar Configuración' }}</span>
        </button>
      </div>
    </header>

    <!-- Banner de Error Global o Formulario -->
    <transition name="toast-fade">
      <div v-if="globalError || formError" class="validation-error-banner">
        <AlertTriangle :size="18" class="error-banner-icon" />
        <div class="error-banner-body">
          <strong>Restricción Operativa Enológica:</strong>
          <p>{{ formError || globalError }}</p>
        </div>
        <button class="error-banner-close" @click="formError = null; globalError = null">
          <X :size="14" />
        </button>
      </div>
    </transition>

    <!-- Selector de Perfiles Enológicos (Tabs) -->
    <section class="profiles-catalog">
      <div class="catalog-header">
        <h2 class="section-title">Catálogo de Perfiles de Fermentación</h2>
        <span class="catalog-hint">Selecciona un perfil para calibrar sus umbrales o haz clic en "Nuevo Perfil"</span>
      </div>

      <div v-if="profiles.length === 0 && !isLoadingProfiles" class="empty-profiles-notice">
        <AlertTriangle :size="24" />
        <p>No se encontraron perfiles enológicos activos. Crea uno nuevo para comenzar.</p>
      </div>

      <div class="profiles-grid">
        <div
          v-for="prof in profiles"
          :key="prof.id"
          class="profile-card"
          :class="{ active: selectedProfileId === prof.id }"
          @click="selectedProfileId = prof.id; formError = null"
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

          <div class="profile-pill-ph">
            <FlaskConical :size="13" />
            <span>pH: <strong>{{ prof.phMin }} - {{ prof.phMax }}</strong> · Azúcar: <strong>{{ prof.brixCaidaMinDia }} °Bx/d</strong></span>
          </div>
        </div>
      </div>
    </section>

    <!-- Visualizador del Espectro Térmico (Termómetro Gráfico) -->
    <section v-if="currentProfile" class="spectrum-section">
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

          <!-- Zona 3: Banda Óptima -->
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
    <div v-if="currentProfile" class="config-grid">
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
          Ajusta los puntos de corte donde el sistema disparará advertencias enológicas o alertas térmicas en bodega.
        </p>

        <div class="form-inputs-stack">
          <!-- Mínimo Crítico -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Temperatura Mínima Crítica</span>
              <span class="field-value-badge">{{ Number(currentProfile.critMin).toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.critMin"
                type="range"
                min="8.0"
                max="20.0"
                step="0.5"
                class="slider-input slider--cold"
              />
            </div>
            <span class="field-hint">Bajo este valor las levaduras se aletargan y caen al fondo.</span>
          </div>

          <!-- Mínimo Óptimo (temp_min) -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Temperatura Mínima Óptima (temp_min) *</span>
              <span class="field-value-badge badge--optimal">{{ Number(currentProfile.optimalMin).toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.optimalMin"
                type="range"
                min="10.0"
                max="26.0"
                step="0.5"
                class="slider-input slider--optimal"
              />
            </div>
            <span class="field-hint">Punto inferior ideal para la cinética fermentativa de esta cepa (restricción ck_perfil_temp).</span>
          </div>

          <!-- Máximo Óptimo (temp_max) -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Temperatura Máxima Óptima (temp_max) *</span>
              <span class="field-value-badge badge--optimal">{{ Number(currentProfile.optimalMax).toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.optimalMax"
                type="range"
                min="16.0"
                max="32.0"
                step="0.5"
                class="slider-input slider--optimal"
              />
            </div>
            <span class="field-hint">Límite superior antes de activar camisas de refrigeración en cuba.</span>
          </div>

          <!-- Máximo Crítico -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Temperatura Máxima Crítica</span>
              <span class="field-value-badge badge--danger">{{ Number(currentProfile.critMax).toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.critMax"
                type="range"
                min="20.0"
                max="36.0"
                step="0.5"
                class="slider-input slider--danger"
              />
            </div>
            <span class="field-hint">Superado este punto, las levaduras sufren muerte por shock térmico.</span>
          </div>
        </div>
      </section>

      <!-- 2. Bandas de Acidez pH y Caída de Brix -->
      <section class="config-card">
        <div class="card-header-clean">
          <div class="card-title-icon icon-amber">
            <FlaskConical :size="18" />
            <h3 class="card-title">Bandas de Acidez (pH) y Cinética de Azúcar</h3>
          </div>
          <span class="sensor-chip-tag">Sonda PH-4502C & Hidrómetro</span>
        </div>

        <p class="config-card-desc">
          Calibración de límites físicoquímicos para control microbiológico y seguimiento del consumo de azúcares.
        </p>

        <div class="form-inputs-stack">
          <!-- pH Mínimo -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">pH Mínimo Aceptable (ph_min) *</span>
              <span class="field-value-badge">{{ Number(currentProfile.phMin).toFixed(2) }} pH</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.phMin"
                type="range"
                min="2.80"
                max="3.60"
                step="0.05"
                class="slider-input slider--amber"
              />
            </div>
            <span class="field-hint">pH excesivamente ácido inhibe la fermentación alcohólica (restricción ck_perfil_ph).</span>
          </div>

          <!-- pH Máximo -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">pH Máximo Aceptable (ph_max) *</span>
              <span class="field-value-badge">{{ Number(currentProfile.phMax).toFixed(2) }} pH</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.phMax"
                type="range"
                min="3.40"
                max="4.20"
                step="0.05"
                class="slider-input slider--amber"
              />
            </div>
            <span class="field-hint">pH elevado incrementa el riesgo de contaminación bacteriana y pérdida de frescura.</span>
          </div>

          <!-- Caída mínima diaria de Brix -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Caída Mínima Diaria de Azúcar (°Bx/día)</span>
              <span class="field-value-badge">{{ Number(currentProfile.brixCaidaMinDia).toFixed(2) }} °Bx</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.brixCaidaMinDia"
                type="range"
                min="0.5"
                max="3.5"
                step="0.1"
                class="slider-input slider--optimal"
              />
            </div>
            <span class="field-hint">Velocidad mínima de atenuación de densidad para no declarar parada de fermentación.</span>
          </div>

          <!-- Regla de Detección Térmica Brusca -->
          <div class="threshold-field">
            <div class="field-label-row">
              <span class="field-title">Gradiente Térmico Máximo Permitido (2 horas)</span>
              <span class="field-value-badge">± {{ Number(currentProfile.maxDelta2h).toFixed(1) }} °C</span>
            </div>
            <div class="slider-row">
              <input
                v-model.number="currentProfile.maxDelta2h"
                type="range"
                min="0.5"
                max="3.5"
                step="0.1"
                class="slider-input slider--cold"
              />
            </div>
            <span class="field-hint">Alerta por falla en sistemas de refrigeración o calentamiento de bodega.</span>
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

    <!-- MODAL: CREAR NUEVO PERFIL ENOLÓGICO (POST /api/perfiles) -->
    <div v-if="isCreateModalOpen" class="modal-backdrop" @click.self="closeCreateModal">
      <div class="threshold-modal">
        <!-- Header Modal -->
        <div class="modal-header">
          <div class="modal-title-group">
            <div class="modal-icon-badge">
              <Sparkles :size="20" />
            </div>
            <div>
              <h2 class="modal-title">Nuevo Perfil de Fermentación</h2>
              <p class="modal-sub">
                Registra bandas térmicas y de acidez persistidas en la base de datos de Supabase.
              </p>
            </div>
          </div>

          <button class="modal-close-btn" :disabled="isCreating" @click="closeCreateModal">
            <X :size="18" />
          </button>
        </div>

        <!-- Formulario Modal -->
        <form @submit.prevent="handleCreateProfile" class="modal-form">
          <!-- Alerta de Error en Creación -->
          <div v-if="createError" class="modal-error-banner">
            <AlertTriangle :size="16" class="error-banner-icon" />
            <div class="error-banner-content">
              <strong>Error de Validación:</strong>
              <p>{{ createError }}</p>
            </div>
          </div>

          <div class="form-grid">
            <!-- Nombre del Perfil -->
            <div class="form-group form-group--full">
              <label class="form-label">Nombre del Perfil Enológico *</label>
              <input
                v-model="newProfileForm.nomb_perfil"
                type="text"
                required
                placeholder="Ej: Tinto Robusto Carménère Especial"
                class="form-input"
              />
              <span class="form-hint">Nombre descriptivo para identificarlo en las cubas.</span>
            </div>

            <!-- Cepa Asociada -->
            <div class="form-group">
              <label class="form-label">Cepa Vinífera *</label>
              <select v-model="newProfileForm.cepa_id" class="form-select" required>
                <option v-for="c in availableCepas" :key="c.id" :value="c.id">
                  {{ c.name }}
                </option>
              </select>
            </div>

            <!-- Bodega -->
            <div class="form-group">
              <label class="form-label">Bodega Operativa *</label>
              <select v-model="newProfileForm.bodega_id" class="form-select" required>
                <option :value="5">Bodega Principal (ID 5)</option>
                <option :value="1">Bodega Finca Central (ID 1)</option>
              </select>
            </div>

            <!-- Banda Térmica: temp_min -->
            <div class="form-group">
              <label class="form-label">Temperatura Mínima Óptima (°C) *</label>
              <input
                v-model.number="newProfileForm.temp_min"
                type="number"
                step="0.5"
                min="5"
                max="35"
                required
                class="form-input"
              />
              <span class="form-hint">Límite inferior (temp_min).</span>
            </div>

            <!-- Banda Térmica: temp_max -->
            <div class="form-group">
              <label class="form-label">Temperatura Máxima Óptima (°C) *</label>
              <input
                v-model.number="newProfileForm.temp_max"
                type="number"
                step="0.5"
                min="5"
                max="35"
                required
                class="form-input"
              />
              <span class="form-hint">Límite superior (temp_max &gt;= temp_min).</span>
            </div>

            <!-- Banda Acidez: ph_min -->
            <div class="form-group">
              <label class="form-label">pH Mínimo (ph_min)</label>
              <input
                v-model.number="newProfileForm.ph_min"
                type="number"
                step="0.05"
                min="2.5"
                max="4.5"
                class="form-input"
              />
            </div>

            <!-- Banda Acidez: ph_max -->
            <div class="form-group">
              <label class="form-label">pH Máximo (ph_max)</label>
              <input
                v-model.number="newProfileForm.ph_max"
                type="number"
                step="0.05"
                min="2.5"
                max="4.5"
                class="form-input"
              />
            </div>

            <!-- Caída Brix Diaria -->
            <div class="form-group form-group--full">
              <label class="form-label">Caída Mínima Esperada Diaria (°Bx/día)</label>
              <input
                v-model.number="newProfileForm.brix_caida_min_dia"
                type="number"
                step="0.1"
                min="0.5"
                max="5.0"
                class="form-input"
              />
            </div>
          </div>

          <!-- Footer Modal -->
          <div class="modal-footer">
            <button type="button" class="btn-secondary" :disabled="isCreating" @click="closeCreateModal">
              Cancelar
            </button>
            <button type="submit" class="btn-primary" :disabled="isCreating">
              <RefreshCw v-if="isCreating" :size="16" class="spin-icon" />
              <Check v-else :size="16" />
              <span>{{ isCreating ? 'Guardando en BD...' : 'Crear Perfil en Servidor' }}</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- MODAL: CONFIRMAR DESACTIVACIÓN DE PERFIL (DELETE /api/perfiles/{id}) -->
    <div v-if="isDeleteModalOpen && currentProfile" class="modal-backdrop" @click.self="closeDeleteModal">
      <div class="threshold-modal threshold-modal--compact">
        <!-- Header Modal -->
        <div class="modal-header">
          <div class="modal-title-group">
            <div class="modal-icon-badge modal-icon-badge--danger">
              <Trash2 :size="20" />
            </div>
            <div>
              <h2 class="modal-title">Confirmar Desactivación</h2>
              <p class="modal-sub">Soft-delete en tabla PERFIL_FERMENTACION</p>
            </div>
          </div>

          <button class="modal-close-btn" :disabled="isDeleting" @click="closeDeleteModal">
            <X :size="18" />
          </button>
        </div>

        <div class="modal-body-confirm">
          <!-- Alerta de Rechazo de Backend (ej: Proceso Activo) -->
          <div v-if="deleteError" class="modal-error-banner">
            <AlertTriangle :size="18" class="error-banner-icon" />
            <div class="error-banner-content">
              <strong>Rechazo de Regla de Negocio:</strong>
              <p>{{ deleteError }}</p>
            </div>
          </div>

          <div class="confirm-warning-box">
            <AlertTriangle :size="20" class="warning-icon" />
            <div class="warning-text">
              <p>
                ¿Estás seguro de que deseas desactivar el perfil <strong>"{{ currentProfile.name }}"</strong>?
              </p>
            </div>
          </div>

          <div class="profile-delete-summary">
            <div class="summary-row">
              <span class="lbl">ID de Perfil:</span>
              <span class="val font-mono">#{{ currentProfile.id }}</span>
            </div>
            <div class="summary-row">
              <span class="lbl">Variedad / Cepa:</span>
              <span class="val">{{ currentProfile.varieties }}</span>
            </div>
            <div class="summary-row">
              <span class="lbl">Bandas Térmicas:</span>
              <span class="val">{{ currentProfile.optimalMin }}°C — {{ currentProfile.optimalMax }}°C</span>
            </div>
          </div>

          <p class="confirm-footnote">
            El perfil no podrá ser seleccionado en nuevas fermentaciones. Si está en uso en una cuba activa, el servidor bloqueará la desactivación para resguardar la trazabilidad enológica.
          </p>

          <div class="modal-footer">
            <button type="button" class="btn-secondary" :disabled="isDeleting" @click="closeDeleteModal">
              Cancelar
            </button>
            <button
              type="button"
              class="btn-danger-confirm"
              :disabled="isDeleting"
              @click="handleConfirmDelete"
            >
              <RefreshCw v-if="isDeleting" :size="16" class="spin-icon" />
              <Trash2 v-else :size="16" />
              <span>{{ isDeleting ? 'Desactivando...' : 'Sí, Desactivar Perfil' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
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

.btn-new-profile {
  color: var(--wine-700);
  border-color: var(--wine-600);
  font-weight: 600;
}

.btn-new-profile:hover {
  background-color: var(--wine-100);
}

.btn-danger-outline {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--status-danger-border);
  color: var(--status-danger);
  padding: 0.55rem 1rem;
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-danger-outline:hover:not(:disabled) {
  background-color: var(--status-danger-bg);
  border-color: var(--status-danger);
}

.btn-danger-outline:disabled {
  opacity: 0.5;
  cursor: wait;
}

/* Banner de Error de Validación */
.validation-error-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  background-color: var(--status-danger-bg);
  border: 1px solid var(--status-danger-border);
  border-radius: var(--radius-md);
  padding: 0.9rem 1.25rem;
  color: var(--status-danger);
  box-shadow: 0 4px 12px rgba(153, 27, 46, 0.08);
}

.error-banner-icon {
  flex-shrink: 0;
  margin-top: 0.15rem;
}

.error-banner-body {
  flex: 1;
  font-size: 0.84rem;
  line-height: 1.4;
}

.error-banner-body strong {
  display: block;
  font-weight: 700;
  margin-bottom: 0.2rem;
}

.error-banner-body p {
  color: var(--text-primary);
}

.error-banner-close {
  color: var(--status-danger);
  padding: 0.2rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.error-banner-close:hover {
  opacity: 0.7;
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

.empty-profiles-notice {
  background-color: var(--bg-surface);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-md);
  padding: 2.5rem;
  text-align: center;
  color: var(--text-muted);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.profiles-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
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

.profile-pill-ph {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.profile-pill-ph strong {
  font-family: var(--font-mono);
  color: var(--text-primary);
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

/* Modales */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(35, 22, 28, 0.65);
  backdrop-filter: blur(3px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.threshold-modal {
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  background-color: var(--bg-surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: 0 20px 45px rgba(35, 22, 28, 0.25);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: modal-pop 0.2s ease-out;
}

.threshold-modal--compact {
  max-width: 480px;
}

@keyframes modal-pop {
  from { opacity: 0; transform: scale(0.96) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-title-group {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.modal-icon-badge {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  background-color: var(--wine-100);
  color: var(--wine-700);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-icon-badge--danger {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
}

.modal-title {
  font-family: var(--font-serif);
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--wine-900);
}

.modal-sub {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.modal-close-btn {
  color: var(--text-muted);
  padding: 0.4rem;
  border-radius: var(--radius-sm);
  transition: color 0.15s ease;
  cursor: pointer;
}

.modal-close-btn:hover {
  color: var(--text-primary);
  background-color: var(--bg-subtle);
}

.modal-form {
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.1rem;
}

@media (max-width: 580px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-group--full {
  grid-column: 1 / -1;
}

.form-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-primary);
}

.form-hint {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.form-input,
.form-select {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  font-family: inherit;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
  outline: none;
}

.form-input:focus,
.form-select:focus {
  border-color: var(--wine-700);
  background-color: #FFFFFF;
}

.modal-footer {
  padding-top: 1rem;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.75rem;
}

.modal-error-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.85rem 1.1rem;
  border-radius: var(--radius-md);
  background-color: var(--status-danger-bg);
  border: 1px solid var(--status-danger-border);
  color: var(--status-danger);
  font-size: 0.82rem;
  line-height: 1.4;
}

.modal-error-banner .error-banner-content strong {
  display: block;
  font-weight: 700;
  margin-bottom: 0.15rem;
}

.modal-error-banner .error-banner-content p {
  color: var(--text-primary);
  font-size: 0.8rem;
  word-break: break-word;
}

.modal-body-confirm {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

.confirm-warning-box {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  padding: 0.9rem 1.1rem;
  border-radius: var(--radius-md);
  background-color: var(--status-warn-bg);
  border: 1px solid var(--status-warn-border);
  color: var(--status-warn);
}

.confirm-warning-box .warning-icon {
  flex-shrink: 0;
  margin-top: 0.15rem;
}

.confirm-warning-box .warning-text p {
  font-size: 0.86rem;
  line-height: 1.45;
  color: var(--text-primary);
}

.profile-delete-summary {
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.profile-delete-summary .summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
}

.profile-delete-summary .lbl {
  color: var(--text-muted);
}

.profile-delete-summary .val {
  color: var(--text-primary);
  font-weight: 600;
}

.confirm-footnote {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.btn-danger-confirm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  background-color: var(--status-danger);
  color: #FFFFFF;
  padding: 0.55rem 1.1rem;
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
  font-weight: 600;
  transition: background-color 0.15s ease;
  cursor: pointer;
}

.btn-danger-confirm:hover:not(:disabled) {
  background-color: #7A1424;
}

.btn-danger-confirm:disabled {
  opacity: 0.6;
  cursor: wait;
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.font-mono {
  font-family: var(--font-mono);
}
</style>
