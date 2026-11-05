<script setup>
/**
 * 📋 03. [FRONT - VUE] Pantalla de Dashboard General (Dash)
 * Módulo 2: Monitoreo en Vivo (Core)
 *
 * Características implementadas:
 * 1. Consumo asíncrono en tiempo real de GET /api/cubas mediante cubaService.
 * 2. Indicadores visuales en tiempo real: Temperatura (°C), Grados Brix (°Bx) y Semáforos de Estado (Normal, Advertencia, Crítico).
 * 3. Detección dinámica de fluctuaciones del simulador IoT con cálculo reactivo de tendencia térmica (alza/baja/estable) y resplandor visual (flash-update).
 * 4. Polling automático en tiempo real cada 5 segundos con limpieza en onBeforeUnmount y cache-busting.
 * 5. Manejo robusto de estados de carga (Skeleton cards) y error de conexión con botón "Reintentar".
 * 6. Barra de métricas resumen (KPIs) calculadas reactivamente con computed en base a la API (Cubas Totales, En Fermentación, Advertencias).
 * 7. Barra de herramientas con buscador por cepa/cuba y filtros de estado.
 * 8. Navegación hacia /cubas/:id preservando el ID real de la cuba.
 */

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import {
  Cylinder,
  Thermometer,
  Droplets,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  Search,
  Filter,
  RefreshCw,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Layers,
  Clock,
  Sparkles,
  Radio
} from 'lucide-vue-next'
import cubaService from '../services/cubaService'

const router = useRouter()

// Estado Asíncrono y Datos de Cubas
const cubas = ref([])
const loading = ref(true)
const error = ref(null)
const isRefreshing = ref(false)
const lastSyncTime = ref(null)
const updatedCubaIds = ref(new Set())
let pollInterval = null
let secondTicker = null
const currentSecondsTick = ref(Date.now())

// Filtros y Búsqueda
const searchQuery = ref('')
const selectedFilter = ref('todos') // 'todos' | 'fermentacion' | 'normal' | 'advertencia' | 'critico'
const sortBy = ref('id') // 'id' | 'temp-desc' | 'temp-asc' | 'brix-asc' | 'brix-desc' | 'alerta'

/**
 * Mapeo de DTO Backend (CubaOut) a Modelo Frontend con detección de cambios
 * cuba.id ➔ id
 * cuba.codigo ➔ codigo_cuba
 * cuba.variedad ➔ variedad
 * cuba.volumenActual ➔ volumen_actual_lts
 * cuba.temperatura ➔ ultima_temperatura
 * cuba.brix ➔ ultimos_brix
 * cuba.fase ➔ estado_operativo ("en_uso" = Activa, "disponible" = Disponible)
 */
const mapearCuba = (item, previa = null) => {
  const estaEnUso = item.estado_operativo === 'en_uso'
  const fase = estaEnUso
    ? 'Activa'
    : item.estado_operativo === 'disponible'
      ? 'Disponible'
      : item.estado_operativo || 'Disponible'

  const temp =
    item.ultima_temperatura !== null && item.ultima_temperatura !== undefined
      ? Number(item.ultima_temperatura)
      : null
  const brix =
    item.ultimos_brix !== null && item.ultimos_brix !== undefined
      ? Number(item.ultimos_brix)
      : null

  // Detección de tendencia térmica y cambios respecto a la lectura previa
  let tendenciaTemp = 'estable'
  let haCambiado = false

  if (previa && typeof previa.temperatura === 'number' && typeof temp === 'number') {
    const diffTemp = Math.round((temp - previa.temperatura) * 100) / 100
    if (diffTemp > 0.05) {
      tendenciaTemp = 'alza'
    } else if (diffTemp < -0.05) {
      tendenciaTemp = 'baja'
    } else {
      tendenciaTemp = previa.tendenciaTemp || 'estable'
    }

    const diffBrix =
      typeof previa.brix === 'number' && typeof brix === 'number'
        ? Math.abs(brix - previa.brix)
        : 0

    if (Math.abs(diffTemp) >= 0.05 || diffBrix >= 0.05) {
      haCambiado = true
    }
  }

  const tempMin = typeof item.temp_min_perfil === 'number' ? item.temp_min_perfil : 16.0
  const tempMax = typeof item.temp_max_perfil === 'number' ? item.temp_max_perfil : 26.0

  // Diagnóstico de estado térmico según umbrales del proceso
  let estado = 'normal'
  let alertaMsg = null

  if (temp !== null) {
    if (temp > tempMax + 1.5) {
      estado = 'critico'
      alertaMsg = `Alerta crítica de sobrecalentamiento (${temp.toFixed(1)} °C > ${tempMax} °C)`
    } else if (temp > tempMax) {
      estado = 'advertencia'
      alertaMsg = `Temperatura sobre límite superior (${temp.toFixed(1)} °C > ${tempMax} °C)`
    } else if (temp < tempMin - 1.5) {
      estado = 'critico'
      alertaMsg = `Alerta crítica de enfriamiento excesivo (${temp.toFixed(1)} °C < ${tempMin} °C)`
    } else if (temp < tempMin) {
      estado = 'advertencia'
      alertaMsg = `Temperatura bajo límite inferior (${temp.toFixed(1)} °C < ${tempMin} °C)`
    }
  }

  return {
    id: item.id,
    codigo: item.codigo_cuba || `Cuba ${item.id}`,
    nombre: item.nombre || `Cuba ${item.codigo_cuba || item.id}`,
    variedad: item.variedad || (estaEnUso ? 'Sin asignar' : 'Disponible'),
    lote: item.lote || (estaEnUso ? `Lote ${item.id}-2026` : 'Sin Lote'),
    volumenActual: typeof item.volumen_actual_lts === 'number' ? item.volumen_actual_lts : 0,
    volumenTotal: typeof item.capacidad_lts === 'number' ? item.capacidad_lts : 10000,
    temperatura: temp,
    tempMin,
    tempMax,
    brix,
    brixInicial: 24.5,
    fase,
    dia: item.dia_fermentacion || 1,
    estado_operativo: item.estado_operativo || 'disponible',
    estado,
    alertaMsg,
    tendenciaTemp,
    ultima_lectura_timestamp: item.ultima_lectura_timestamp,
    _haCambiado: haCambiado
  }
}

/**
 * Formatea el tiempo transcurrido desde la última lectura de telemetría
 */
const formatTiempoLectura = (timestamp, estaEnUso) => {
  // Para forzar reactividad en el segundo
  void currentSecondsTick.value

  if (!timestamp) {
    return estaEnUso ? 'En línea' : 'Sin lecturas'
  }

  const lecturaDate = new Date(timestamp)
  const ahora = Date.now()
  const diffSec = Math.floor((ahora - lecturaDate.getTime()) / 1000)

  const horaStr = lecturaDate.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })

  if (isNaN(diffSec) || diffSec < 5) {
    return `Hace instantes (${horaStr})`
  }
  if (diffSec < 60) {
    return `Hace ${diffSec}s (${horaStr})`
  }
  if (diffSec < 3600) {
    return `Hace ${Math.floor(diffSec / 60)}m (${horaStr})`
  }
  return `Hace ${Math.floor(diffSec / 3600)}h (${horaStr})`
}

/**
 * Consulta la lista de cubas y telemetría mediante cubaService
 * @param {boolean} isInitial Indica si es la carga inicial (activa skeleton cards)
 */
const fetchCubas = async (isInitial = false) => {
  if (isInitial) {
    loading.value = true
    error.value = null
  } else {
    isRefreshing.value = true
  }

  try {
    const data = await cubaService.listarCubas()
    const nuevasCubas = []
    const changedIds = new Set()

    for (const item of data || []) {
      const previa = cubas.value.find((c) => c.id === item.id)
      const nueva = mapearCuba(item, previa)
      if (nueva._haCambiado) {
        changedIds.add(item.id)
      }
      nuevasCubas.push(nueva)
    }

    cubas.value = nuevasCubas

    // Si hubo cambios en telemetría, activar resplandor visual temporal
    if (changedIds.size > 0) {
      updatedCubaIds.value = changedIds
      setTimeout(() => {
        updatedCubaIds.value = new Set()
      }, 1500)
    }

    lastSyncTime.value = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
    error.value = null
  } catch (err) {
    console.error('[DashboardView] Error cargando cubas:', err)
    error.value = err.message || 'Error de comunicación con el servidor MOSTO'
  } finally {
    if (isInitial) {
      loading.value = false
    }
    isRefreshing.value = false
  }
}

// Métricas Globales (KPIs) calculadas reactivamente con computed
const stats = computed(() => {
  const total = cubas.value.length
  const enFermentacion = cubas.value.filter(
    (c) => c.estado_operativo === 'en_uso' || c.fase === 'Activa'
  ).length
  const normales = cubas.value.filter((c) => c.estado === 'normal').length
  const advertencias = cubas.value.filter((c) => c.estado === 'advertencia').length
  const criticos = cubas.value.filter((c) => c.estado === 'critico').length

  const cubasConTemp = cubas.value.filter(
    (c) => typeof c.temperatura === 'number' && !isNaN(c.temperatura)
  )
  const sumTemp = cubasConTemp.reduce((acc, c) => acc + c.temperatura, 0)
  const avgTemp = cubasConTemp.length > 0 ? (sumTemp / cubasConTemp.length).toFixed(1) : '--'

  return { total, enFermentacion, normales, advertencias, criticos, avgTemp }
})

// Lista filtrada y ordenada
const filteredCubas = computed(() => {
  return cubas.value
    .filter((c) => {
      // Filtro por estado o proceso
      if (selectedFilter.value === 'fermentacion') {
        if (c.estado_operativo !== 'en_uso' && c.fase !== 'Activa') return false
      } else if (selectedFilter.value !== 'todos' && c.estado !== selectedFilter.value) {
        return false
      }

      // Búsqueda por texto (código o cepa o lote)
      if (searchQuery.value.trim()) {
        const q = searchQuery.value.toLowerCase()
        return (
          (c.codigo && c.codigo.toLowerCase().includes(q)) ||
          (c.variedad && c.variedad.toLowerCase().includes(q)) ||
          (c.lote && c.lote.toLowerCase().includes(q)) ||
          (c.fase && c.fase.toLowerCase().includes(q))
        )
      }
      return true
    })
    .sort((a, b) => {
      if (sortBy.value === 'temp-desc') return (b.temperatura ?? -999) - (a.temperatura ?? -999)
      if (sortBy.value === 'temp-asc') return (a.temperatura ?? 999) - (b.temperatura ?? 999)
      if (sortBy.value === 'brix-asc') return (a.brix ?? 999) - (b.brix ?? 999)
      if (sortBy.value === 'brix-desc') return (b.brix ?? -999) - (a.brix ?? -999)
      if (sortBy.value === 'alerta') {
        const order = { critico: 0, advertencia: 1, normal: 2 }
        return (order[a.estado] ?? 2) - (order[b.estado] ?? 2)
      }
      return a.id - b.id
    })
})

// Helpers de Semáforo y UI
const getStatusBadge = (estado) => {
  switch (estado) {
    case 'critico':
      return { label: 'Crítico', class: 'badge-danger', icon: AlertCircle }
    case 'advertencia':
      return { label: 'Advertencia', class: 'badge-warn', icon: AlertTriangle }
    default:
      return { label: 'Normal', class: 'badge-good', icon: CheckCircle2 }
  }
}

// Porcentaje de azúcar convertida (Progreso de fermentación)
const getBrixProgress = (cuba) => {
  if (cuba.brix === null || cuba.brix === undefined) return 0
  const brixInicial = cuba.brixInicial || 24.5
  const consumed = Math.max(0, brixInicial - cuba.brix)
  const percentage = (consumed / brixInicial) * 100
  return Math.min(100, Math.max(0, Math.round(percentage)))
}

// Navegación hacia detalle de cuba preservando el ID real (/cubas/:id)
const goToDetail = (cubaId) => {
  router.push(`/cubas/${cubaId}`)
}

// Ciclo de vida y Polling reactivo cada 5 segundos
onMounted(() => {
  fetchCubas(true)

  // Polling automático cada 5 segundos para sincronizar en vivo con simulate_esp.py
  pollInterval = setInterval(() => {
    fetchCubas(false)
  }, 5000)

  // Ticker de segundos para refrescar contador relativo del pie de tarjeta
  secondTicker = setInterval(() => {
    currentSecondsTick.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
  if (secondTicker) {
    clearInterval(secondTicker)
    secondTicker = null
  }
})
</script>

<template>
  <div class="dashboard-page">
    <!-- Encabezado de la Vista -->
    <header class="dashboard-header">
      <div>
        <div class="header-pretitle">
          <span>Monitoreo en Tiempo Real</span>
          <span class="live-dot"></span>
          <span v-if="lastSyncTime" class="sync-badge">
            <Radio :size="12" class="sync-icon-pulse" />
            <span>Sincronizado {{ lastSyncTime }}</span>
          </span>
        </div>
        <h1 class="header-title">Vista General de Cubas</h1>
        <p class="header-description">
          Supervisión termométrica y enológica de las cubas activas en la bodega central.
        </p>
      </div>

      <!-- Botón de actualización manual -->
      <div class="header-actions">
        <button
          type="button"
          class="btn-refresh"
          :class="{ 'is-spinning': isRefreshing }"
          :disabled="isRefreshing"
          title="Actualizar telemetría IoT desde el servidor"
          @click="fetchCubas(false)"
        >
          <RefreshCw :size="15" />
          <span>{{ isRefreshing ? 'Leyendo Sensores...' : 'Actualizar Telemetría' }}</span>
        </button>
      </div>
    </header>

    <!-- Barra de Métricas y Semáforos Resumen (KPIs) -->
    <section class="kpi-grid">
      <!-- Cubas Totales -->
      <div
        class="kpi-card"
        :class="{ active: selectedFilter === 'todos' }"
        @click="selectedFilter = 'todos'"
      >
        <div class="kpi-icon-box total">
          <Cylinder :size="20" />
        </div>
        <div class="kpi-data">
          <span class="kpi-number">{{ stats.total }}</span>
          <span class="kpi-label">Cubas Totales</span>
        </div>
      </div>

      <!-- En Fermentación -->
      <div
        class="kpi-card fermentation"
        :class="{ active: selectedFilter === 'fermentacion' }"
        @click="selectedFilter = 'fermentacion'"
      >
        <div class="kpi-icon-box fermentation">
          <Sparkles :size="20" />
        </div>
        <div class="kpi-data">
          <div class="kpi-number-row">
            <span class="kpi-number">{{ stats.enFermentacion }}</span>
            <span class="kpi-indicator wine"></span>
          </div>
          <span class="kpi-label">En Fermentación</span>
        </div>
      </div>

      <!-- Cubas en Advertencia -->
      <div
        class="kpi-card warn"
        :class="{ active: selectedFilter === 'advertencia' }"
        @click="selectedFilter = 'advertencia'"
      >
        <div class="kpi-icon-box warn">
          <AlertTriangle :size="20" />
        </div>
        <div class="kpi-data">
          <div class="kpi-number-row">
            <span class="kpi-number">{{ stats.advertencias }}</span>
            <span class="kpi-indicator amber"></span>
          </div>
          <span class="kpi-label">Advertencias</span>
        </div>
      </div>

      <!-- Cubas Críticas -->
      <div
        class="kpi-card danger"
        :class="{ active: selectedFilter === 'critico' }"
        @click="selectedFilter = 'critico'"
      >
        <div class="kpi-icon-box danger">
          <AlertCircle :size="20" />
        </div>
        <div class="kpi-data">
          <div class="kpi-number-row">
            <span class="kpi-number">{{ stats.criticos }}</span>
            <span class="kpi-indicator red"></span>
          </div>
          <span class="kpi-label">Riesgo Crítico</span>
        </div>
      </div>

      <!-- Promedio Temperatura -->
      <div class="kpi-card avg">
        <div class="kpi-icon-box avg">
          <Thermometer :size="20" />
        </div>
        <div class="kpi-data">
          <span class="kpi-number">{{ stats.avgTemp }}<small v-if="stats.avgTemp !== '--'">°C</small></span>
          <span class="kpi-label">Temp. Promedio Bodega</span>
        </div>
      </div>
    </section>

    <!-- Barra de Herramientas: Búsqueda y Filtros -->
    <section class="toolbar-section">
      <!-- Buscador -->
      <div class="search-input-wrapper">
        <Search :size="16" class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="Buscar por cuba, cepa (ej. Cabernet, CB-01)..."
        />
        <button
          v-if="searchQuery"
          type="button"
          class="clear-search-btn"
          @click="searchQuery = ''"
        >
          ×
        </button>
      </div>

      <!-- Selector de Estado (Pills) -->
      <div class="filter-pills">
        <button
          type="button"
          class="pill-btn"
          :class="{ active: selectedFilter === 'todos' }"
          @click="selectedFilter = 'todos'"
        >
          Todas ({{ stats.total }})
        </button>
        <button
          type="button"
          class="pill-btn pill-fermentation"
          :class="{ active: selectedFilter === 'fermentacion' }"
          @click="selectedFilter = 'fermentacion'"
        >
          <span class="pill-dot wine"></span>
          En Fermentación ({{ stats.enFermentacion }})
        </button>
        <button
          type="button"
          class="pill-btn pill-good"
          :class="{ active: selectedFilter === 'normal' }"
          @click="selectedFilter = 'normal'"
        >
          <span class="pill-dot green"></span>
          Normales ({{ stats.normales }})
        </button>
        <button
          type="button"
          class="pill-btn pill-warn"
          :class="{ active: selectedFilter === 'advertencia' }"
          @click="selectedFilter = 'advertencia'"
        >
          <span class="pill-dot amber"></span>
          Advertencias ({{ stats.advertencias }})
        </button>
        <button
          type="button"
          class="pill-btn pill-danger"
          :class="{ active: selectedFilter === 'critico' }"
          @click="selectedFilter = 'critico'"
        >
          <span class="pill-dot red"></span>
          Críticas ({{ stats.criticos }})
        </button>
      </div>

      <!-- Ordenamiento -->
      <div class="sort-wrapper">
        <Filter :size="15" class="sort-icon" />
        <select v-model="sortBy" class="sort-select">
          <option value="id">Orden por Cuba (ID)</option>
          <option value="alerta">Por Gravedad (Críticas 1°)</option>
          <option value="temp-desc">Mayor Temperatura</option>
          <option value="temp-asc">Menor Temperatura</option>
          <option value="brix-desc">Mayor Azúcar (°Bx)</option>
          <option value="brix-asc">Menor Azúcar (°Bx)</option>
        </select>
      </div>
    </section>

    <!-- Alerta de Error Visual con Botón de Reintento (Criterio 3) -->
    <section v-if="error && cubas.length === 0" class="error-state-card">
      <div class="error-icon-box">
        <AlertCircle :size="32" />
      </div>
      <div class="error-info">
        <h3 class="error-title">No fue posible conectar con el servidor de telemetría</h3>
        <p class="error-message">{{ error }}</p>
        <p class="error-hint">Verifique que el backend de MOSTO esté iniciado en http://localhost:8000.</p>
      </div>
      <button
        type="button"
        class="btn-retry"
        :disabled="loading"
        @click="fetchCubas(true)"
      >
        <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
        <span>Reintentar</span>
      </button>
    </section>

    <!-- Banner discreto si falla el polling de fondo con datos previos cargados -->
    <div v-if="error && cubas.length > 0" class="polling-warning-banner">
      <AlertTriangle :size="16" />
      <span>Error al actualizar telemetría en tiempo real: {{ error }}. Mostrando última lectura conocida.</span>
      <button type="button" class="btn-banner-retry" @click="fetchCubas(false)">
        Reintentar ahora
      </button>
    </div>

    <!-- Skeleton Cards durante el loading inicial (Criterio 2) -->
    <div v-if="loading && cubas.length === 0" class="cubas-grid" role="region" aria-label="Cargando cubas">
      <div v-for="n in 6" :key="n" class="cuba-card skeleton-card">
        <div class="skeleton-header">
          <div class="skeleton-circle shimmer"></div>
          <div class="skeleton-text-group">
            <div class="skeleton-bar bar-title shimmer"></div>
            <div class="skeleton-bar bar-subtitle shimmer"></div>
          </div>
          <div class="skeleton-badge shimmer"></div>
        </div>
        <div class="skeleton-subinfo shimmer"></div>
        <div class="skeleton-metrics">
          <div class="skeleton-metric-box shimmer"></div>
          <div class="skeleton-metric-box shimmer"></div>
        </div>
        <div class="skeleton-footer">
          <div class="skeleton-bar bar-footer shimmer"></div>
          <div class="skeleton-bar bar-action shimmer"></div>
        </div>
      </div>
    </div>

    <!-- Cuadrícula Responsive de Tarjetas de Cubas -->
    <main
      v-else-if="cubas.length > 0"
      class="cubas-grid"
      role="region"
      aria-label="Cuadrícula de cubas"
    >
      <article
        v-for="cuba in filteredCubas"
        :key="cuba.id"
        class="cuba-card"
        :class="[`card-status-${cuba.estado}`, { 'cuba-card-pulse': updatedCubaIds.has(cuba.id) }]"
        @click="goToDetail(cuba.id)"
      >
        <!-- Encabezado de la Tarjeta -->
        <header class="cuba-card-header">
          <div class="cuba-ident">
            <div class="cuba-icon-avatar" :class="{ 'avatar-glow': updatedCubaIds.has(cuba.id) }">
              <Cylinder :size="18" />
            </div>
            <div>
              <h3 class="cuba-code">{{ cuba.codigo }}</h3>
              <span class="cuba-variety">{{ cuba.variedad }}</span>
            </div>
          </div>

          <!-- Semáforo de Estado -->
          <div class="status-badge" :class="getStatusBadge(cuba.estado).class">
            <span class="status-dot"></span>
            <span>{{ getStatusBadge(cuba.estado).label }}</span>
          </div>
        </header>

        <!-- Lote y Fase Actual -->
        <div class="cuba-subinfo">
          <span class="cuba-lot">{{ cuba.lote }}</span>
          <span class="cuba-phase">
            {{ cuba.fase }}
            <template v-if="cuba.estado_operativo === 'en_uso'"> · Día {{ cuba.dia }}</template>
          </span>
        </div>

        <!-- Banner de Alerta si aplica -->
        <div v-if="cuba.alertaMsg" class="cuba-alert-banner">
          <AlertTriangle :size="14" class="alert-banner-icon" />
          <span>{{ cuba.alertaMsg }}</span>
        </div>

        <!-- Medidores Principales: Temperatura y Brix -->
        <div class="metrics-container">
          <!-- Métrica: Temperatura -->
          <div
            class="metric-box temp-box"
            :class="[`temp-${cuba.estado}`, { 'metric-highlight': updatedCubaIds.has(cuba.id) }]"
          >
            <div class="metric-header">
              <span class="metric-label">
                <Thermometer :size="14" />
                <span>Temperatura</span>
              </span>
              <span class="metric-target">Rango: {{ cuba.tempMin }}° - {{ cuba.tempMax }}°C</span>
            </div>

            <div class="metric-main-value">
              <span class="metric-digits">
                {{ cuba.temperatura !== null ? cuba.temperatura.toFixed(1) : '--' }}
              </span>
              <span class="metric-unit">°C</span>

              <span
                v-if="cuba.tendenciaTemp === 'alza'"
                class="trend-tag trend-up"
                title="Tendencia al alza (+ temp)"
              >
                <TrendingUp :size="13" />
              </span>
              <span
                v-else-if="cuba.tendenciaTemp === 'baja'"
                class="trend-tag trend-down"
                title="Tendencia a la baja (- temp)"
              >
                <TrendingDown :size="13" />
              </span>
            </div>

            <!-- Indicador gráfico de rango -->
            <div class="temp-range-bar">
              <div
                class="temp-range-marker"
                :style="{
                  left: `${cuba.temperatura !== null ? Math.min(95, Math.max(5, ((cuba.temperatura - 10) / 25) * 100)) : 50}%`
                }"
              ></div>
            </div>
          </div>

          <!-- Métrica: Grados Brix -->
          <div
            class="metric-box brix-box"
            :class="{ 'metric-highlight': updatedCubaIds.has(cuba.id) }"
          >
            <div class="metric-header">
              <span class="metric-label">
                <Droplets :size="14" />
                <span>Densidad / Azúcar</span>
              </span>
              <span class="metric-target">Inicial: {{ cuba.brixInicial }} °Bx</span>
            </div>

            <div class="metric-main-value">
              <span class="metric-digits">
                {{ cuba.brix !== null ? cuba.brix.toFixed(1) : '--' }}
              </span>
              <span class="metric-unit">°Bx</span>

              <span
                v-if="cuba.brix !== null"
                class="progress-percent"
                title="Progreso estimado de fermentación"
              >
                {{ getBrixProgress(cuba) }}% conv.
              </span>
            </div>

            <!-- Barra de conversión de azúcar -->
            <div class="brix-progress-track">
              <div
                class="brix-progress-fill"
                :style="{ width: `${getBrixProgress(cuba)}%` }"
              ></div>
            </div>
          </div>
        </div>

        <!-- Pie de la Tarjeta -->
        <footer class="cuba-card-footer">
          <div class="footer-meta">
            <div class="meta-item">
              <Layers :size="13" />
              <span>
                {{ cuba.volumenTotal > 0 ? ((cuba.volumenActual / cuba.volumenTotal) * 100).toFixed(0) : 0 }}% ·
                {{ cuba.volumenActual ? cuba.volumenActual.toLocaleString() : 0 }} L
              </span>
            </div>
            <div class="meta-item time" :title="cuba.ultima_lectura_timestamp || 'Sin fecha'">
              <Clock :size="13" />
              <span>{{ formatTiempoLectura(cuba.ultima_lectura_timestamp, cuba.estado_operativo === 'en_uso') }}</span>
            </div>
          </div>

          <div class="card-action-btn">
            <span>Ver Detalle</span>
            <ChevronRight :size="15" />
          </div>
        </footer>
      </article>
    </main>

    <!-- Estado vacío cuando no hay resultados de búsqueda -->
    <div
      v-if="!loading && !error && filteredCubas.length === 0"
      class="empty-state"
    >
      <div class="empty-icon-box">
        <Search :size="32" />
      </div>
      <h3>No se encontraron cubas</h3>
      <p>
        No hay registros que coincidan con "{{ searchQuery }}" bajo el filtro seleccionado.
      </p>
      <button
        type="button"
        class="btn-reset-filters"
        @click="searchQuery = ''; selectedFilter = 'todos'"
      >
        Restablecer Filtros
      </button>
    </div>
  </div>
</template>

<style scoped>
/* Contenedor General de la Vista */
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
  max-width: 1400px;
  margin: 0 auto;
}

/* Encabezado */
.dashboard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.header-pretitle {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--wine-700);
  margin-bottom: 0.25rem;
}

.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: var(--status-good);
  box-shadow: 0 0 0 2px rgba(42, 102, 68, 0.25);
  animation: pulse-dot 1.8s infinite ease-in-out;
}

.sync-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background-color: var(--status-good-bg);
  border: 1px solid var(--status-good-border);
  color: var(--status-good);
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-full);
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 600;
}

.sync-icon-pulse {
  animation: pulse-dot 1.5s infinite;
}

@keyframes pulse-dot {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.3);
    opacity: 0.7;
  }
}

.header-title {
  font-family: var(--font-serif);
  font-size: 2.1rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1.15;
  letter-spacing: -0.01em;
  margin: 0;
}

.header-description {
  font-size: 0.88rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  padding: 0.55rem 0.95rem;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--wine-800);
  transition: all 0.15s ease;
  box-shadow: var(--shadow-subtle);
  cursor: pointer;
}

.btn-refresh:hover:not(:disabled) {
  background-color: var(--wine-50);
  border-color: var(--wine-700);
  color: var(--wine-900);
}

.btn-refresh:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.is-spinning svg {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Cuadrícula de KPIs */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.9rem;
}

.kpi-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1rem 1.15rem;
  display: flex;
  align-items: center;
  gap: 0.9rem;
  transition: all 0.15s ease;
  cursor: pointer;
  box-shadow: var(--shadow-subtle);
  user-select: none;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card);
  border-color: var(--text-muted);
}

.kpi-card.active {
  border-color: var(--wine-700);
  background-color: var(--wine-50);
}

.kpi-icon-box {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kpi-icon-box.total {
  background-color: var(--bg-subtle);
  color: var(--wine-800);
  border: 1px solid var(--border-color);
}

.kpi-icon-box.fermentation {
  background-color: var(--wine-100);
  color: var(--wine-700);
  border: 1px solid var(--wine-600);
}

.kpi-icon-box.good {
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border: 1px solid var(--status-good-border);
}

.kpi-icon-box.warn {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
  border: 1px solid var(--status-warn-border);
}

.kpi-icon-box.danger {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border: 1px solid var(--status-danger-border);
}

.kpi-icon-box.avg {
  background-color: var(--wine-100);
  color: var(--wine-700);
  border: 1px solid var(--border-color);
}

.kpi-data {
  display: flex;
  flex-direction: column;
}

.kpi-number-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.kpi-number {
  font-family: var(--font-mono);
  font-size: 1.45rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.kpi-number small {
  font-size: 0.9rem;
  color: var(--text-muted);
  font-weight: 500;
}

.kpi-label {
  font-size: 0.73rem;
  font-weight: 500;
  color: var(--text-secondary);
  margin-top: 0.15rem;
}

.kpi-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.kpi-indicator.wine {
  background-color: var(--wine-700);
}

.kpi-indicator.green {
  background-color: var(--status-good);
}

.kpi-indicator.amber {
  background-color: var(--status-warn);
}

.kpi-indicator.red {
  background-color: var(--status-danger);
}

/* Barra de Herramientas */
.toolbar-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-subtle);
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 240px;
  max-width: 380px;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 38px;
  padding: 0 2rem 0 2.2rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.83rem;
  color: var(--text-primary);
  outline: none;
  transition: all 0.15s ease;
}

.search-input:focus {
  border-color: var(--wine-600);
  background-color: #FFFFFF;
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.08);
}

.clear-search-btn {
  position: absolute;
  right: 0.65rem;
  font-size: 1.1rem;
  color: var(--text-muted);
  line-height: 1;
}

.filter-pills {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.75rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--text-secondary);
  transition: all 0.12s ease;
  cursor: pointer;
}

.pill-btn:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.pill-btn.active {
  background-color: var(--wine-700);
  border-color: var(--wine-700);
  color: #FFFFFF;
}

.pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.pill-dot.wine { background-color: var(--wine-700); }
.pill-dot.green { background-color: var(--status-good); }
.pill-dot.amber { background-color: var(--status-warn); }
.pill-dot.red { background-color: var(--status-danger); }

.pill-btn.active .pill-dot {
  background-color: #FFFFFF;
}

.sort-wrapper {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.sort-icon {
  color: var(--text-muted);
}

.sort-select {
  height: 38px;
  padding: 0 1.75rem 0 0.65rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

/* Estado de Error Visual */
.error-state-card {
  background-color: var(--status-danger-bg);
  border: 1px solid var(--status-danger-border);
  border-radius: var(--radius-md);
  padding: 1.75rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  box-shadow: var(--shadow-subtle);
}

.error-icon-box {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-full);
  background-color: rgba(153, 27, 46, 0.12);
  color: var(--status-danger);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.error-info {
  flex: 1;
}

.error-title {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--status-danger);
  margin-bottom: 0.25rem;
}

.error-message {
  font-size: 0.88rem;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}

.error-hint {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.btn-retry {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--wine-700);
  color: #FFFFFF;
  border-radius: var(--radius-sm);
  padding: 0.65rem 1.2rem;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
  border: none;
}

.btn-retry:hover:not(:disabled) {
  background-color: var(--wine-800);
  transform: translateY(-1px);
}

.btn-retry:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Banner de Alerta de Polling de Fondo */
.polling-warning-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background-color: var(--status-warn-bg);
  border: 1px solid var(--status-warn-border);
  color: var(--status-warn);
  padding: 0.65rem 1rem;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  font-weight: 500;
}

.btn-banner-retry {
  margin-left: auto;
  text-decoration: underline;
  cursor: pointer;
  font-weight: 600;
  color: var(--wine-800);
  background: none;
  border: none;
}

/* Cuadrícula de Cubas */
.cubas-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1.25rem;
}

/* Tarjeta Individual de Cuba */
.cuba-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.35rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  cursor: pointer;
  box-shadow: var(--shadow-subtle);
  position: relative;
  overflow: hidden;
}

.cuba-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(35, 22, 28, 0.08);
  border-color: var(--wine-600);
}

/* Resplandor visual cuando la cuba recibe nueva telemetría */
.cuba-card-pulse {
  animation: card-glow 1.4s ease-out;
}

@keyframes card-glow {
  0% {
    box-shadow: 0 0 0 3px rgba(42, 102, 68, 0.4), 0 8px 24px rgba(42, 102, 68, 0.15);
  }
  100% {
    box-shadow: var(--shadow-subtle);
  }
}

.avatar-glow {
  animation: avatar-pulse 1.4s ease-out;
}

@keyframes avatar-pulse {
  0% {
    background-color: var(--status-good-bg);
    color: var(--status-good);
    transform: scale(1.1);
  }
  100% {
    background-color: var(--wine-50);
    color: var(--wine-700);
    transform: scale(1);
  }
}

/* Borde semántico de acento superior */
.cuba-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3.5px;
  background-color: var(--border-color);
  transition: background-color 0.15s ease;
}

.card-status-normal::before {
  background-color: var(--status-good);
}

.card-status-advertencia::before {
  background-color: var(--status-warn);
}

.card-status-critico::before {
  background-color: var(--status-danger);
}

/* Encabezado de la Tarjeta */
.cuba-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.cuba-ident {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.cuba-icon-avatar {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  background-color: var(--wine-50);
  border: 1px solid var(--wine-100);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--wine-700);
  transition: all 0.25s ease;
}

.cuba-code {
  font-family: var(--font-serif);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1.1;
}

.cuba-variety {
  font-size: 0.77rem;
  font-weight: 600;
  color: var(--text-secondary);
  display: block;
}

/* Badges de Semáforo */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.6rem;
  border-radius: var(--radius-full);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.badge-good {
  background-color: var(--status-good-bg);
  border: 1px solid var(--status-good-border);
  color: var(--status-good);
}
.badge-good .status-dot { background-color: var(--status-good); }

.badge-warn {
  background-color: var(--status-warn-bg);
  border: 1px solid var(--status-warn-border);
  color: var(--status-warn);
}
.badge-warn .status-dot { background-color: var(--status-warn); }

.badge-danger {
  background-color: var(--status-danger-bg);
  border: 1px solid var(--status-danger-border);
  color: var(--status-danger);
}
.badge-danger .status-dot {
  background-color: var(--status-danger);
  animation: pulse-dot 1.2s infinite ease-in-out;
}

/* Lote y Fase */
.cuba-subinfo {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.73rem;
  color: var(--text-muted);
  padding-bottom: 0.4rem;
  border-bottom: 1px dashed var(--border-subtle);
}

.cuba-lot {
  font-family: var(--font-mono);
  background-color: var(--bg-subtle);
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
}

.cuba-phase {
  font-weight: 500;
  color: var(--wine-800);
}

/* Alerta interna de la tarjeta */
.cuba-alert-banner {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.65rem;
  border-radius: var(--radius-sm);
  background-color: var(--status-danger-bg);
  border: 1px solid var(--status-danger-border);
  color: var(--status-danger);
  font-size: 0.74rem;
  font-weight: 600;
  line-height: 1.3;
}

.alert-banner-icon {
  flex-shrink: 0;
}

/* Métricas: Contenedor Dual */
.metrics-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.metric-box {
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  transition: all 0.25s ease;
}

/* Resplandor visual en las cajas de métricas */
.metric-highlight {
  border-color: var(--status-good);
  background-color: var(--status-good-bg);
}

.metric-header {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.metric-label {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.metric-target {
  font-size: 0.66rem;
  color: var(--text-muted);
}

.metric-main-value {
  display: flex;
  align-items: baseline;
  gap: 0.25rem;
  margin: 0.15rem 0;
}

.metric-digits {
  font-family: var(--font-mono);
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
  transition: color 0.2s ease;
}

.metric-unit {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
}

/* Colores condicionales en temperatura */
.temp-normal .metric-digits {
  color: var(--status-good);
}

.temp-advertencia .metric-digits {
  color: var(--status-warn);
}

.temp-critico .metric-digits {
  color: var(--status-danger);
}

.trend-tag {
  margin-left: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-sm);
}

.trend-up {
  color: var(--status-danger);
  background-color: var(--status-danger-bg);
}

.trend-down {
  color: #1A5FB4;
  background-color: #EDF3FC;
}

/* Barra de rango de temperatura */
.temp-range-bar {
  position: relative;
  width: 100%;
  height: 4px;
  background: linear-gradient(to right, #4A90E2 0%, var(--status-good) 45%, var(--status-warn) 75%, var(--status-danger) 100%);
  border-radius: var(--radius-full);
  margin-top: 0.35rem;
}

.temp-range-marker {
  position: absolute;
  top: -3px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #FFFFFF;
  border: 2px solid var(--text-primary);
  transform: translateX(-50%);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  transition: left 0.3s ease;
}

/* Barra de progreso de Brix */
.progress-percent {
  margin-left: auto;
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--wine-700);
}

.brix-progress-track {
  width: 100%;
  height: 4px;
  background-color: var(--border-color);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-top: 0.35rem;
}

.brix-progress-fill {
  height: 100%;
  background: linear-gradient(to right, var(--wine-600), var(--wine-800));
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}

/* Pie de Tarjeta */
.cuba-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 0.6rem;
  border-top: 1px solid var(--border-subtle);
  font-size: 0.74rem;
}

.footer-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--text-secondary);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.meta-item.time {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.71rem;
}

.card-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--wine-700);
  transition: color 0.15s ease, transform 0.15s ease;
}

.cuba-card:hover .card-action-btn {
  color: var(--wine-900);
  transform: translateX(2px);
}

/* Estado Vacío */
.empty-state {
  text-align: center;
  padding: 4rem 1.5rem;
  background-color: var(--bg-surface);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.empty-icon-box {
  width: 60px;
  height: 60px;
  border-radius: var(--radius-full);
  background-color: var(--bg-subtle);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.5rem;
}

.empty-state h3 {
  font-family: var(--font-serif);
  font-size: 1.4rem;
  color: var(--wine-900);
}

.empty-state p {
  font-size: 0.86rem;
  color: var(--text-muted);
  max-width: 360px;
}

.btn-reset-filters {
  margin-top: 0.75rem;
  padding: 0.45rem 1rem;
  background-color: var(--wine-700);
  color: #FFFFFF;
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.btn-reset-filters:hover {
  background-color: var(--wine-800);
}

/* Skeleton Loading Cards */
.skeleton-card {
  pointer-events: none;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  min-height: 280px;
}

.skeleton-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.skeleton-circle {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  flex-shrink: 0;
}

.skeleton-text-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.skeleton-bar {
  border-radius: var(--radius-sm);
}

.bar-title {
  width: 60%;
  height: 16px;
}

.bar-subtitle {
  width: 40%;
  height: 12px;
}

.skeleton-badge {
  width: 65px;
  height: 22px;
  border-radius: var(--radius-full);
}

.skeleton-subinfo {
  width: 75%;
  height: 14px;
  border-radius: var(--radius-sm);
}

.skeleton-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.skeleton-metric-box {
  height: 95px;
  border-radius: var(--radius-sm);
}

.skeleton-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-subtle);
}

.bar-footer {
  width: 45%;
  height: 14px;
}

.bar-action {
  width: 25%;
  height: 14px;
}

/* Animación Shimmer */
.shimmer {
  background: linear-gradient(
    90deg,
    var(--bg-subtle) 0%,
    var(--border-subtle) 50%,
    var(--bg-subtle) 100%
  );
  background-size: 200% 100%;
  animation: shimmer-pulse 1.5s infinite;
}

@keyframes shimmer-pulse {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* Responsividad */
@media (max-width: 768px) {
  .dashboard-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    justify-content: flex-start;
  }

  .toolbar-section {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input-wrapper {
    max-width: 100%;
  }

  .metrics-container {
    grid-template-columns: 1fr;
  }

  .error-state-card {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
