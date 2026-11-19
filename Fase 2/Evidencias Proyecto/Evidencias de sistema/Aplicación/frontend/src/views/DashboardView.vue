<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Cylinder,
  Thermometer,
  Droplets,
  AlertTriangle,
  Search,
  RefreshCw,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Layers,
  Sparkles
} from 'lucide-vue-next'
import cubaService from '../services/cubaService'


const router = useRouter()
const route = useRoute()

// Pestaña Activa del Dashboard
// 'overview' | 'health' | 'comparison' | 'grid'
const activeTab = ref('overview')

// Estado de Cubas y Telemetría
const cubas = ref([])
const loading = ref(true)
const error = ref(null)
const isRefreshing = ref(false)
const lastSyncTime = ref(null)
const updatedCubaIds = ref(new Set())
let pollInterval = null
let secondTicker = null
const currentSecondsTick = ref(Date.now())

// Filtros de Barra de Herramientas (Estilo Searchable)
const searchQuery = ref('')
const selectedVariety = ref('todas')
const selectedStatusFilter = ref('todos')
const onlyAlertsSwitch = ref(false)
const selectedSort = ref('id')

// Mapeo de DTO Backend a Modelo Frontend
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

  const tempMin = item.temp_min_perfil
  const tempMax = item.temp_max_perfil

  let estado = temp == null || tempMin == null || tempMax == null ? 'sin_datos' : 'normal'
  let alertaMsg = null

  if (temp !== null && tempMin != null && tempMax != null) {
    if (temp > tempMax + 1.5) {
      estado = 'critico'
      alertaMsg = `Alerta crítica: ${temp.toFixed(1)} °C > ${tempMax} °C`
    } else if (temp > tempMax) {
      estado = 'advertencia'
      alertaMsg = `Temperatura sobre límite: ${temp.toFixed(1)} °C > ${tempMax} °C`
    } else if (temp < tempMin - 1.5) {
      estado = 'critico'
      alertaMsg = `Alerta crítica de frío: ${temp.toFixed(1)} °C < ${tempMin} °C`
    } else if (temp < tempMin) {
      estado = 'advertencia'
      alertaMsg = `Temperatura bajo límite: ${temp.toFixed(1)} °C < ${tempMin} °C`
    }
  }

  return {
    id: item.id,
    codigo: item.codigo_cuba || `Cuba ${item.id}`,
    nombre: item.nombre || `Cuba ${item.codigo_cuba || item.id}`,
    variedad: item.variedad || '—',
    lote: item.lote || 'Sin lote',
    volumenActual: typeof item.volumen_actual_lts === 'number' ? item.volumen_actual_lts : 0,
    volumenTotal: typeof item.capacidad_lts === 'number' ? item.capacidad_lts : 10000,
    temperatura: temp,
    tempMin,
    tempMax,
    brix,
    fase,
    dia: item.dia_fermentacion || 1,
    estado_operativo: item.estado_operativo || 'disponible',
    estado,
    alertaMsg,
    tendenciaTemp,
    ultima_lectura_timestamp: item.ultima_lectura_timestamp,
    prediccion_ml: item.prediccion_ml || null,
    _haCambiado: haCambiado
  }
}

// Formateador de tiempo relativo
const formatTiempoLectura = (timestamp, estaEnUso) => {
  void currentSecondsTick.value
  if (!timestamp) return 'Sin lecturas'

  const lecturaDate = new Date(timestamp)
  const ahora = Date.now()
  const diffSec = Math.floor((ahora - lecturaDate.getTime()) / 1000)

  if (isNaN(diffSec) || diffSec < 5) return 'Hace instantes'
  if (diffSec < 60) return `Hace ${diffSec}s`
  if (diffSec < 3600) return `Hace ${Math.floor(diffSec / 60)}m`
  return `Hace ${Math.floor(diffSec / 3600)}h`
}

// Carga de Cubas desde la API
const fetchCubas = async (isInitial = false) => {
  if (isRefreshing.value) return
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
      if (nueva._haCambiado) changedIds.add(item.id)
      nuevasCubas.push(nueva)
    }

    cubas.value = nuevasCubas

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
    console.error('[DashboardView] Error cargando telemetría:', err)
    error.value = err.message || 'Error al conectar con la telemetría de MOSTO'
  } finally {
    if (isInitial) loading.value = false
    isRefreshing.value = false
  }
}

// KPIs Globales Reactivos
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
  const avgTemp = cubasConTemp.length > 0 ? (sumTemp / cubasConTemp.length).toFixed(1) : '—'

  const evaluadas = normales + advertencias + criticos
  const pctOptimo = evaluadas ? Math.round(normales * 100 / evaluadas) : null

  return {
    total,
    enFermentacion,
    normales,
    advertencias,
    criticos,
    avgTemp,
    evaluadas,
    pctOptimo
  }
})

// Lista de Variedades Únicas para el filtro
const variedadesDisponibles = computed(() => {
  const set = new Set()
  cubas.value.forEach((c) => {
    if (c.variedad && c.variedad !== 'Disponible') set.add(c.variedad)
  })
  return Array.from(set)
})

// Cubas Filtradas y Ordenadas
const filteredCubas = computed(() => {
  return cubas.value
    .filter((c) => {
      // Switch "Solo en riesgo"
      if (onlyAlertsSwitch.value && !['critico', 'advertencia'].includes(c.estado)) return false

      // Filtro de Estado
      if (selectedStatusFilter.value !== 'todos' && c.estado !== selectedStatusFilter.value) {
        return false
      }

      // Filtro de Cepa
      if (selectedVariety.value !== 'todas' && c.variedad !== selectedVariety.value) {
        return false
      }

      // Buscador
      if (searchQuery.value.trim()) {
        const q = searchQuery.value.toLowerCase()
        return (
          (c.codigo && c.codigo.toLowerCase().includes(q)) ||
          (c.variedad && c.variedad.toLowerCase().includes(q)) ||
          (c.lote && c.lote.toLowerCase().includes(q))
        )
      }
      return true
    })
    .sort((a, b) => {
      if (selectedSort.value === 'temp-desc') return (b.temperatura ?? -999) - (a.temperatura ?? -999)
      if (selectedSort.value === 'temp-asc') return (a.temperatura ?? 999) - (b.temperatura ?? 999)
      if (selectedSort.value === 'brix-desc') return (b.brix ?? -999) - (a.brix ?? -999)
      if (selectedSort.value === 'brix-asc') return (a.brix ?? 999) - (b.brix ?? 999)
      if (selectedSort.value === 'alerta') {
        const order = { critico: 0, advertencia: 1, normal: 2 }
        return (order[a.estado] ?? 2) - (order[b.estado] ?? 2)
      }
      return a.id - b.id
    })
})

// Top Rankings de Cubas para la Tabla Resumen (Estilo Searchable)
const rankingCubas = computed(() => {
  return [...filteredCubas.value]
    .sort((a, b) => {
      const order = { critico: 0, advertencia: 1, normal: 2 }
      if (order[a.estado] !== order[b.estado]) return order[a.estado] - order[b.estado]
      return a.id - b.id
    })

})

const getStatusBadge = (cuba) => {
  switch (cuba.estado) {
    case 'sin_datos':
      return { label: 'Sin diagnóstico', class: '', dot: 'gray' }
    case 'critico':
      return { label: 'Crítico', class: 'danger', dot: 'red' }
    case 'advertencia':
      return { label: 'Advertencia', class: 'warn', dot: 'amber' }
    default:
      return { label: 'Normal', class: 'good', dot: 'green' }
  }
}

const getIABadge = (pred) => {
  if (!pred || !pred.estado_ia) return null
  const estado = pred.estado_ia
  const pct = typeof pred.riesgo_pct === 'number' ? pred.riesgo_pct.toFixed(0) : '0'
  switch (estado) {
    case 'CRITICO':
      return { label: `IA: ${pct}% Parada`, class: 'badge-ia-critico', isCritico: true }
    case 'ADVERTENCIA':
      return { label: `IA: ${pct}% Riesgo`, class: 'badge-ia-advertencia', isCritico: false }
    case 'NORMAL':
      return { label: `Riesgo estimado: ${pct}%`, class: 'badge-ia-normal', isCritico: false }
    case 'NO_VALIDADO':
      return { label: 'IA: Sin modelo validado', class: 'badge-ia-calibrando', isCritico: false }
    case 'FINALIZADA':
      return { label: 'Brix en tramo final', class: 'badge-ia-finalizada', isCritico: false }
    default:
      return { label: 'IA: Calibrando', class: 'badge-ia-calibrando', isCritico: false }
  }
}

const temperatureScale = computed(() => Math.max(30, ...filteredCubas.value.map(c => c.temperatura ?? 0)))
const brixScale = computed(() => Math.max(25, ...filteredCubas.value.map(c => c.brix ?? 0)))
const barWidth = (value, scale) => `${Math.max(0, value ?? 0) * 100 / scale}%`

const goToDetail = (cubaId) => {
  router.push(`/cubas/${cubaId}`)
}

// El buscador global comparte la consulta con la cuadrícula de cubas.
watch(() => route.query.q, query => {
  searchQuery.value = String(query || '')
  if (searchQuery.value) activeTab.value = 'grid'
}, { immediate: true })

onMounted(() => {
  fetchCubas(true)
  pollInterval = setInterval(() => fetchCubas(false), 5000)
  secondTicker = setInterval(() => {
    currentSecondsTick.value = Date.now()
  }, 1000)


})

onBeforeUnmount(() => {
  if (pollInterval) clearInterval(pollInterval)
  if (secondTicker) clearInterval(secondTicker)
})
</script>

<template>
  <div class="dashboard-container">
    <h1 class="dashboard-title">Dashboard general</h1>
    <!-- 1. Pestañas Secundarias de Navegación (Estilo Searchable) -->
    <nav class="saas-tabs-nav">
      <button
        type="button"
        class="saas-tab-item"
        :class="{ active: activeTab === 'overview' }"
        @click="activeTab = 'overview'"
      >
        Resumen
      </button>
      <button
        type="button"
        class="saas-tab-item"
        :class="{ active: activeTab === 'health' }"
        @click="activeTab = 'health'"
      >
        Estado térmico
      </button>
      <button
        type="button"
        class="saas-tab-item"
        :class="{ active: activeTab === 'comparison' }"
        @click="activeTab = 'comparison'"
      >
        Comparar lotes
      </button>
      <button
        type="button"
        class="saas-tab-item"
        :class="{ active: activeTab === 'grid' }"
        @click="activeTab = 'grid'"
      >
        Cubas ({{ filteredCubas.length }})
      </button>
    </nav>

    <!-- 2. Barra de Filtros de Alta Precisión (Estilo Searchable) -->
    <section class="saas-filter-bar">
      <!-- Switch Toggle "Solo en Riesgo" -->
      <button type="button" role="switch" :aria-checked="onlyAlertsSwitch" class="saas-switch-wrapper" @click="onlyAlertsSwitch = !onlyAlertsSwitch">
        <div class="saas-switch-track" :class="{ active: onlyAlertsSwitch }">
          <div class="saas-switch-thumb"></div>
        </div>
        <span>Solo en riesgo</span>
      </button>

      <!-- Selector de Cepa / Variedad -->
      <select aria-label="Cepa" v-model="selectedVariety" class="saas-filter-select">
        <option value="todas">Todas las Cepas</option>
        <option v-for="varName in variedadesDisponibles" :key="varName" :value="varName">
          {{ varName }}
        </option>
      </select>

      <!-- Selector de Estado de Cubas -->
      <select aria-label="Estado" v-model="selectedStatusFilter" class="saas-filter-select">
        <option value="todos">Todos los Estados</option>
        <option value="normal">Normales</option>
        <option value="advertencia">Advertencias</option>
        <option value="critico">Riesgo Crítico</option>
      </select>

      <!-- Botón de Sincronización Manual a la Derecha -->
      <button
        type="button"
        class="saas-filter-btn"
        :class="{ 'is-spinning': isRefreshing }"
        :disabled="isRefreshing"
        title="Actualizar telemetría de sensores IoT"
        style="margin-left: auto;"
        @click="fetchCubas(false)"
      >
        <RefreshCw :size="14" />
        <span>{{ isRefreshing ? 'Leyendo...' : 'Sincronizar' }}</span>
      </button>
    </section>

    <!-- Banner de Alerta si la conexión falla -->
    <div v-if="error" class="saas-error-banner">
      <AlertTriangle :size="16" class="error-banner-icon" />
      <div class="error-banner-text">
        <strong>Conexión con sensores:</strong> {{ error }}. Mostrando última telemetría en caché.
      </div>
      <button type="button" class="error-banner-retry" @click="fetchCubas(true)">
        Reintentar
      </button>
    </div>

    <!-- ====================================================================
         CONTENIDO PRINCIPAL (Paneles según Pestaña Activa o Vista Unificada)
         ==================================================================== -->

    <!-- VISTA 1: OVERVIEW (Resumen - Replica Imagen 1) -->
    <div v-show="activeTab === 'overview' || activeTab === 'all'" class="tab-pane-content">
      <!-- Fila 2 Inferior: Tarjetas KPI de Resumen Rápido -->
      <div class="kpi-metrics-row">
        <!-- KPI 1: Temperatura Promedio Bodega -->
        <div class="saas-card kpi-subcard">
          <div class="kpi-subcard-header">
            <span class="kpi-subcard-title">Temp. Promedio Bodega</span>
            <span class="kpi-subcard-sub">Sensores activos</span>
          </div>
          <div class="kpi-subcard-value">
            <span>{{ stats.avgTemp }} °C</span>
          </div>
        </div>

        <!-- KPI 2: Cubas en Fermentación Activa -->
        <div class="saas-card kpi-subcard">
          <div class="kpi-subcard-header">
            <span class="kpi-subcard-title">Cubas en Fermentación</span>
            <span class="kpi-subcard-sub">Capacidad en proceso</span>
          </div>
          <div class="kpi-subcard-value">
            <span>{{ stats.enFermentacion }} / {{ stats.total }}</span>
          </div>
        </div>

        <!-- KPI 3: Desvíos y Advertencias -->
        <div class="saas-card kpi-subcard">
          <div class="kpi-subcard-header">
            <span class="kpi-subcard-title">Desvíos térmicos</span>
            <span class="kpi-subcard-sub">Fuera de perfil</span>
          </div>
          <div class="kpi-subcard-value">
            <span :class="{ 'text-danger': stats.criticos > 0 }">
              {{ stats.advertencias + stats.criticos }} cubas
            </span>
            <span v-if="stats.criticos === 0 && stats.advertencias === 0 && stats.evaluadas > 0" class="delta-tag positive">Normalizado</span>
            <span v-if="stats.criticos > 0" class="delta-tag negative">{{ stats.criticos }} críticas</span>
          </div>
        </div>

        <!-- KPI 4: Índice Global de Calidad -->
        <div class="saas-card kpi-subcard">
          <div class="kpi-subcard-header">
            <span class="kpi-subcard-title">Dentro del rango</span>
            <span class="kpi-subcard-sub">Cubas con perfil evaluado</span>
          </div>
          <div class="kpi-subcard-value">
            <span>{{ stats.pctOptimo ?? '—' }}%</span>
          </div>
        </div>
      </div>
      <!-- Fila 1: Gráfico de Tendencia (Izquierda) + Tabla de Rankings (Derecha) -->
      <div class="overview-grid-row">
        <!-- Tarjeta Izquierda: Tendencia Térmica & Brix (Visibility Score) -->
        <article class="saas-card metric-chart-card">
          <header class="card-header-clean">
            <h2 class="panel-heading">Temperatura por cuba</h2>
            <span class="chart-unit">°C</span>
          </header>
          <p v-if="!filteredCubas.length" class="empty-message">Sin cubas para los filtros seleccionados.</p>
          <button v-for="c in filteredCubas" :key="c.id" class="reading-row" @click="goToDetail(c.id)">
            <span>{{ c.codigo }}</span>
            <span class="reading-track"><span :style="{ width: barWidth(c.temperatura, temperatureScale) }"></span></span>
            <strong>{{ c.temperatura?.toFixed(1) ?? '—' }}</strong>
          </button>
        </article>

        <!-- Tarjeta Derecha: Tabla de Rankings de Cubas (Rankings Table) -->
        <article class="saas-card rankings-table-card">
          <header class="card-header-clean">
            <div class="card-title-group">
              <span class="card-category-label">
                <Layers :size="14" />
                <span>Estado de las cubas</span>
              </span>

            </div>
          </header>

          <div class="table-scroll-container">
            <table class="saas-table">
              <thead>
                <tr>
                  <th style="width: 38px;">#</th>
                  <th>Cuba</th>
                  <th>Variedad</th>
                  <th>Temp</th>
                  <th>Brix</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(cuba, idx) in rankingCubas"
                  :key="cuba.id"
                  class="table-row-clickable"
                  @click="goToDetail(cuba.id)"
                >
                  <td class="text-muted">{{ idx + 1 }}</td>
                  <td class="fw-semibold">
                    <div class="cuba-code-row">
                      <div class="cuba-mini-avatar">
                        <Cylinder :size="12" />
                      </div>
                      <span>{{ cuba.codigo }}</span>
                    </div>
                  </td>
                  <td class="text-secondary">{{ cuba.variedad }}</td>
                  <td class="font-mono">
                    {{ cuba.temperatura !== null ? cuba.temperatura.toFixed(1) + '°C' : '--' }}
                  </td>
                  <td class="font-mono">
                    {{ cuba.brix !== null ? cuba.brix.toFixed(1) + '°Bx' : '--' }}
                  </td>
                  <td>
                    <div style="display: flex; align-items: center; gap: 0.4rem;">
                      <span class="badge-status" :class="getStatusBadge(cuba).class">
                        {{ getStatusBadge(cuba).label }}
                      </span>
                      <span
                        v-if="cuba.prediccion_ml?.riesgo_pct != null"
                        class="badge-ia"
                        :class="getIABadge(cuba.prediccion_ml).class"
                        :title="cuba.prediccion_ml.mensaje"
                      >
                        <Sparkles :size="10" />
                        <span>{{ cuba.prediccion_ml.riesgo_pct == null ? 'Pendiente' : `Riesgo exp. ${cuba.prediccion_ml.riesgo_pct}%` }}</span>
                      </span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </div>

    </div>

    <!-- VISTA 2: HEALTH & DIAGNÓSTICO IA (Replica Imagen 2 Superior) -->
    <div v-show="activeTab === 'health' || activeTab === 'all'" class="tab-pane-content" style="margin-top: 1.5rem;">
      <article class="saas-card metric-chart-card">
        <h2 class="panel-heading">Estado térmico por cuba</h2>
        <p v-if="!filteredCubas.length" class="empty-message">Sin cubas para los filtros seleccionados.</p>
        <button v-for="c in filteredCubas" :key="c.id" class="status-row" @click="goToDetail(c.id)">
          <strong>{{ c.codigo }}</strong>
          <span>{{ c.alertaMsg || (c.estado === 'normal' ? 'Temperatura dentro del perfil' : 'Pendiente de lectura o perfil') }}</span>
          <ChevronRight :size="15" />
        </button>
      </article>
    </div>

    <div v-show="activeTab === 'comparison'" class="tab-pane-content">
      <article class="saas-card metric-chart-card">
        <header class="card-header-clean">
          <h2 class="panel-heading">Brix aparente por lote</h2>
          <span class="chart-unit">°Bx</span>
        </header>
        <p v-if="!filteredCubas.length" class="empty-message">Sin cubas para los filtros seleccionados.</p>
        <button v-for="c in filteredCubas" :key="c.id" class="reading-row" @click="goToDetail(c.id)">
          <span>{{ c.codigo }}</span>
          <span class="reading-track brix-track"><span :style="{ width: barWidth(c.brix, brixScale) }"></span></span>
          <strong>{{ c.brix?.toFixed(2) ?? '—' }}</strong>
        </button>
        <RouterLink class="history-link" to="/procesos">Comparar curvas históricas →</RouterLink>
      </article>
    </div>

    <!-- VISTA 4: CUADRÍCULA DE CUBAS IOT (Tarjetas Interactivas en Vivo) -->
    <div v-show="activeTab === 'grid' || activeTab === 'all'" class="tab-pane-content" style="margin-top: 1.5rem;">
      <div class="section-title-row">
        <div>
          <h2 class="section-main-title">Supervisión en Tiempo Real de Cubas</h2>

        </div>
      </div>

      <!-- Cuadrícula Responsive de Tarjetas -->
      <div v-if="filteredCubas.length > 0" class="cubas-saas-grid">
        <article
          v-for="cuba in filteredCubas"
          :key="cuba.id"
          class="saas-card cuba-saas-card"
          :class="{ 'card-pulse-updated': updatedCubaIds.has(cuba.id) }"
          @click="goToDetail(cuba.id)"
        >
          <!-- Cabecera de la Tarjeta -->
          <header class="cuba-saas-header">
            <div class="cuba-saas-ident">
              <div class="cuba-saas-icon">
                <Cylinder :size="16" />
              </div>
              <div>
                <h3 class="cuba-saas-code">{{ cuba.codigo }}</h3>
                <span class="cuba-saas-variety">{{ cuba.variedad }}</span>
              </div>
            </div>

            <span class="badge-status" :class="getStatusBadge(cuba).class">
              {{ getStatusBadge(cuba).label }}
            </span>
          </header>

          <!-- Lote y Días -->
          <div class="cuba-saas-submeta">
            <span>{{ cuba.lote }}</span>
            <span class="submeta-divider">·</span>
            <span>{{ cuba.fase }} (Día {{ cuba.dia }})</span>
          </div>

          <!-- Badge Resumen Predicción IA -->
          <div v-if="getIABadge(cuba.prediccion_ml)" class="cuba-saas-ia-row">
            <span
              class="badge-ia"
              :class="getIABadge(cuba.prediccion_ml).class"
              :title="cuba.prediccion_ml.mensaje"
            >
              <Sparkles :size="11" />
              <span>{{ getIABadge(cuba.prediccion_ml).label }}</span>
            </span>
          </div>

          <!-- Alerta si aplica -->
          <div v-if="cuba.alertaMsg" class="cuba-saas-alert">
            <AlertTriangle :size="13" />
            <span>{{ cuba.alertaMsg }}</span>
          </div>

          <!-- Métricas Principales -->
          <div class="cuba-saas-metrics-grid">
            <!-- Métrica: Temperatura -->
            <div class="cuba-metric-box">
              <div class="metric-top">
                <span class="metric-lbl"><Thermometer :size="13" /> Temp</span>
                <span v-if="cuba.tempMin != null && cuba.tempMax != null" class="metric-range">{{ cuba.tempMin }}°-{{ cuba.tempMax }}°C</span>
              </div>
              <div class="metric-val-row">
                <span class="metric-val-num">
                  {{ cuba.temperatura !== null ? cuba.temperatura.toFixed(1) : '--' }}
                </span>
                <span class="metric-val-unit">°C</span>
                <TrendingUp v-if="cuba.tendenciaTemp === 'alza'" :size="14" class="trend-icon red" />
                <TrendingDown v-else-if="cuba.tendenciaTemp === 'baja'" :size="14" class="trend-icon green" />
              </div>
            </div>

            <!-- Métrica: Brix -->
            <div class="cuba-metric-box">
              <div class="metric-top">
                <span class="metric-lbl"><Droplets :size="13" /> Brix</span>
                <span class="metric-range">Aparente</span>
              </div>
              <div class="metric-val-row">
                <span class="metric-val-num">
                  {{ cuba.brix !== null ? cuba.brix.toFixed(1) : '--' }}
                </span>
                <span class="metric-val-unit">°Bx</span>
              </div>
            </div>
          </div>

          <!-- Pie de Tarjeta -->
          <footer class="cuba-saas-footer">
            <div class="footer-vol">
              <Layers :size="12" />
              <span>{{ cuba.volumenActual.toLocaleString() }} L</span>
            </div>
            <div class="footer-action">
              <span>Ver Telemetría</span>
              <ChevronRight :size="14" />
            </div>
          </footer>
        </article>
      </div>

      <!-- Estado Vacío -->
      <div v-else class="saas-card empty-search-card">
        <Search :size="32" style="color: var(--text-muted); margin-bottom: 0.5rem;" />
        <h4>No se encontraron cubas</h4>
        <p>No hay cubas que coincidan con los filtros seleccionados.</p>
        <button
          type="button"
          class="btn-secondary"
          style="margin-top: 1rem;"
          @click="searchQuery = ''; selectedVariety = 'todas'; selectedStatusFilter = 'todos'; onlyAlertsSwitch = false"
        >
          Limpiar Filtros
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
}

/* Fila de Gráficos Overview */
.overview-grid-row {
  display: grid;
  grid-template-columns: minmax(0, .85fr) minmax(0, 1.4fr);
  gap: 1.25rem;
}

@media (max-width: 1180px) {
  .overview-grid-row {
    grid-template-columns: minmax(0, 1fr);
  }
}

/* Tarjeta de Gráfico Principal */
.metric-chart-card,
.rankings-table-card {
  padding: 1.25rem 1.35rem;
  display: flex;
  flex-direction: column;
}

.card-header-clean {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 0.85rem;
}

.card-title-group {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.card-category-label {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

/* Tabla de Rankings */
.table-scroll-container {
  overflow-x: auto;
  flex: 1;
}

.table-row-clickable {
  cursor: pointer;
  transition: background-color 0.12s ease;
}

.table-row-clickable:hover td {
  background-color: #F8FAFC;
}

.cuba-code-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.cuba-mini-avatar {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-xs);
  background-color: var(--bg-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

/* Fila de KPIs Inferiores */
.kpi-metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.25rem;
  margin-bottom: 1.25rem;
}

@media (max-width: 900px) {
  .kpi-metrics-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.kpi-subcard {
  padding: 1rem 1.15rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.kpi-subcard-header {
  display: flex;
  flex-direction: column;
}

.kpi-subcard-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.kpi-subcard-sub {
  font-size: 0.6875rem;
  color: var(--text-muted);
}

.kpi-subcard-value {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

/* Cubas */
.section-title-row {
  margin-bottom: 1rem;
}

.section-main-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.section-main-sub {
  font-size: 0.8125rem;
  color: var(--text-muted);
}

.cubas-saas-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.25rem;
}

.cuba-saas-card {
  padding: 1.15rem 1.25rem;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: all 0.15s ease;
}

.cuba-saas-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
  border-color: var(--border-strong);
}

.card-pulse-updated {
  animation: glow-pulse 1.2s ease-out;
}

@keyframes glow-pulse {
  0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); border-color: #10B981; }
  70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); border-color: #10B981; }
  100% { box-shadow: none; }
}

.cuba-saas-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cuba-saas-ident {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.cuba-saas-icon {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  background-color: var(--bg-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-primary);
}

.cuba-saas-code {
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--text-primary);
}

.cuba-saas-variety {
  font-size: 0.75rem;
  color: var(--text-muted);
  display: block;
}

.cuba-saas-submeta {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.45rem;
}

.submeta-divider {
  color: var(--border-color);
}

.cuba-saas-alert {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.65rem;
  padding: 0.4rem 0.65rem;
  border-radius: var(--radius-sm);
  background-color: #FEF2F2;
  border: 1px solid #FECACA;
  color: #991B1B;
  font-size: 0.75rem;
  font-weight: 500;
}

.cuba-saas-metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem;
  margin-top: 0.85rem;
  padding: 0.75rem;
  background-color: var(--bg-canvas);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
}

.cuba-metric-box {
  display: flex;
  flex-direction: column;
}

.metric-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.6875rem;
  color: var(--text-muted);
}

.metric-lbl {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.metric-val-row {
  display: flex;
  align-items: baseline;
  gap: 0.2rem;
  margin-top: 0.2rem;
}

.metric-val-num {
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.metric-val-unit {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.trend-icon.red { color: #EF4444; }
.trend-icon.green { color: #10B981; }

.cuba-saas-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.85rem;
  padding-top: 0.65rem;
  border-top: 1px solid var(--border-subtle);
  font-size: 0.75rem;
  color: var(--text-muted);
}

.footer-vol {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.footer-action {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-search-card {
  padding: 3rem 2rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.saas-error-banner {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.65rem 1rem;
  background-color: #FEF2F2;
  border: 1px solid #FECACA;
  border-radius: var(--radius-md);
  color: #991B1B;
  font-size: 0.8125rem;
  margin-bottom: 1.25rem;
}

.error-banner-retry {
  margin-left: auto;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
  color: #991B1B;
}

.font-mono {
  font-family: var(--font-mono);
}

.text-danger {
  color: var(--status-danger) !important;
}

/* ======================================================= */
/* BADGES DE PREDICCIÓN IA (MACHINE LEARNING)             */
/* ======================================================= */
.cuba-saas-ia-row {
  display: flex;
  align-items: center;
  margin-top: 0.35rem;
  margin-bottom: 0.25rem;
}

.badge-ia {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.55rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  line-height: 1;
}

.badge-ia-critico {
  background: rgba(239, 68, 68, 0.16);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.4);
  animation: pulseIABadge 2s infinite ease-in-out;
}

@keyframes pulseIABadge {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
  }
  50% {
    box-shadow: 0 0 10px 2px rgba(239, 68, 68, 0.3);
  }
}

.badge-ia-advertencia {
  background: rgba(245, 158, 11, 0.16);
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.4);
}

.badge-ia-normal {
  background: rgba(16, 185, 129, 0.16);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.4);
}

.badge-ia-finalizada,
.badge-ia-calibrando {
  background: rgba(107, 114, 128, 0.16);
  color: #9ca3af;
  border: 1px solid rgba(107, 114, 128, 0.3);
}

.dashboard-title { font-size: clamp(1.45rem, 2vw, 1.85rem); letter-spacing: -.035em; margin-bottom: .8rem; }
.panel-heading { font-size: 1rem; font-weight: 650; }
.chart-unit, .empty-message { font-size: .82rem; color: var(--text-secondary); }
.reading-row, .status-row { display: grid; align-items: center; gap: 1rem; text-align: left; min-height: 42px; font-size: .82rem; color: var(--text-primary); }
.reading-row { grid-template-columns: auto 1fr 3.2rem; }
.reading-row strong { text-align: right; font-variant-numeric: tabular-nums; }
.reading-track { display: block; height: 7px; background: var(--bg-subtle); border-radius: 6px; overflow: hidden; }
.reading-track > span { display: block; height: 100%; background: #93405b; border-radius: inherit; }
.brix-track > span { background: #bb781e; }
.status-row { grid-template-columns: auto 1fr auto; border-bottom: 1px solid var(--border-subtle); }
.status-row:hover, .reading-row:hover { background: var(--bg-hover); }
.history-link { align-self: flex-start; margin-top: 1rem; font-weight: 600; font-size: .82rem; text-decoration: underline; }
@media (max-width: 500px) { .kpi-metrics-row { gap: .5rem; } .kpi-subcard { padding: .75rem; } }
</style>
