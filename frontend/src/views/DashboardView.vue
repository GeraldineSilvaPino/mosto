<script setup>
/**
 * 🍇 MOSTO — Dashboard General Rediseñado
 * Inspirado en la interfaz SaaS moderna de Searchable
 *
 * Incluye:
 * 1. Pestañas secundarias de navegación (Visibilidad, Salud & IA, Comparativa, Cuadrícula IoT).
 * 2. Barra de filtros de precisión (Entidad, Rango temporal, Frecuencia, Switch alertas, Selector cepas).
 * 3. Tarjeta de Gráfico de Tendencia Térmica & Brix (Visibility Score style).
 * 4. Tarjeta de Tabla de Rankings de Cubas con estados y telemetría en vivo.
 * 5. Tarjeta de Índice de Salud de Fermentación con medidor circular (92/100) y diagnóstico asistido.
 * 6. Tarjeta de Cinética de Azúcares (Sentiment Score style) y Comparativa de Lotes Head-to-Head.
 * 7. Cuadrícula de Cubas IoT con detección de fluctuaciones en tiempo real y resplandor reactivo.
 * 8. Polling en vivo cada 5 segundos contra el backend de MOSTO.
 */

import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
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
  ChevronDown,
  TrendingUp,
  TrendingDown,
  Layers,
  Clock,
  Sparkles,
  Radio,
  Eye,
  ShieldCheck,
  Scale,
  LayoutGrid,
  Check,
  X,
  Sliders,
  ExternalLink
} from 'lucide-vue-next'
import { Chart as ChartJS, registerables } from 'chart.js'
import cubaService from '../services/cubaService'

ChartJS.register(...registerables)

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
const timeRange = ref('7d')
const telemetryFrequency = ref('5s')
const selectedSort = ref('id')

// Referencias a Gráficos Chart.js
const trendChartRef = ref(null)
let trendChartInstance = null

const brixChartRef = ref(null)
let brixChartInstance = null

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

  const tempMin = typeof item.temp_min_perfil === 'number' ? item.temp_min_perfil : 16.0
  const tempMax = typeof item.temp_max_perfil === 'number' ? item.temp_max_perfil : 26.0

  let estado = 'normal'
  let alertaMsg = null

  if (temp !== null) {
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
    variedad: item.variedad || (estaEnUso ? 'Cabernet Sauvignon' : 'Disponible'),
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

// Formateador de tiempo relativo
const formatTiempoLectura = (timestamp, estaEnUso) => {
  void currentSecondsTick.value
  if (!timestamp) return estaEnUso ? 'En línea' : 'Sin lecturas'

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

    // Actualizar gráficos si están montados
    updateCharts()
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
  const avgTemp = cubasConTemp.length > 0 ? (sumTemp / cubasConTemp.length).toFixed(1) : '21.4'

  // Score de Salud Global de la Bodega (0 a 100)
  let healthScore = 94
  if (total > 0) {
    const penaltyWarn = (advertencias / total) * 20
    const penaltyCrit = (criticos / total) * 50
    healthScore = Math.max(20, Math.min(100, Math.round(100 - penaltyWarn - penaltyCrit)))
  }

  // Porcentaje de Cubas en Estado Óptimo
  const pctOptimo = total > 0 ? Math.round((normales / total) * 100) : 85
  const pctAtencion = total > 0 ? Math.round((advertencias / total) * 100) : 10
  const pctCritico = total > 0 ? Math.round((criticos / total) * 100) : 5

  return {
    total,
    enFermentacion,
    normales,
    advertencias,
    criticos,
    avgTemp,
    healthScore,
    pctOptimo,
    pctAtencion,
    pctCritico
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
      if (onlyAlertsSwitch.value && c.estado === 'normal') return false

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
  return [...cubas.value]
    .sort((a, b) => {
      const order = { critico: 0, advertencia: 1, normal: 2 }
      if (order[a.estado] !== order[b.estado]) return order[a.estado] - order[b.estado]
      return b.id - a.id
    })
    .slice(0, 6)
})

const getStatusBadge = (estado) => {
  switch (estado) {
    case 'critico':
      return { label: 'Crítico', class: 'danger', dot: 'red' }
    case 'advertencia':
      return { label: 'Advertencia', class: 'warn', dot: 'amber' }
    default:
      return { label: 'Normal', class: 'good', dot: 'green' }
  }
}

const getBrixProgress = (cuba) => {
  if (cuba.brix === null || cuba.brix === undefined) return 0
  const brixInicial = cuba.brixInicial || 24.5
  const consumed = Math.max(0, brixInicial - cuba.brix)
  return Math.min(100, Math.max(0, Math.round((consumed / brixInicial) * 100)))
}

const goToDetail = (cubaId) => {
  router.push(`/cubas/${cubaId}`)
}

// Inicialización de Gráficos Chart.js
const initTrendChart = () => {
  if (!trendChartRef.value) return
  if (trendChartInstance) {
    trendChartInstance.destroy()
    trendChartInstance = null
  }

  const ctx = trendChartRef.value.getContext('2d')
  const gradient = ctx.createLinearGradient(0, 0, 0, 240)
  gradient.addColorStop(0, 'rgba(16, 185, 129, 0.18)')
  gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)')

  const labels = ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00', 'Ahora']
  const dataPoints = [20.2, 20.8, 21.1, 21.4, 21.9, 21.6, 21.5, 21.8, Number(stats.value.avgTemp) || 21.8]

  trendChartInstance = new ChartJS(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Temperatura Promedio (°C)',
          data: dataPoints,
          borderColor: '#10B981',
          borderWidth: 2.2,
          backgroundColor: gradient,
          fill: true,
          tension: 0.38,
          pointRadius: 3,
          pointBackgroundColor: '#FFFFFF',
          pointBorderColor: '#10B981',
          pointBorderWidth: 2,
          pointHoverRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0F172A',
          titleFont: { size: 12, family: 'Plus Jakarta Sans' },
          bodyFont: { size: 12, family: 'JetBrains Mono' },
          padding: 10,
          cornerRadius: 6,
          displayColors: false,
          callbacks: {
            label: (context) => ` ${context.parsed.y.toFixed(1)} °C`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#94A3B8', font: { size: 11, family: 'Plus Jakarta Sans' } },
          border: { color: '#E2E8F0' }
        },
        y: {
          min: 16,
          max: 28,
          grid: { color: '#F1F5F9' },
          ticks: {
            color: '#94A3B8',
            font: { size: 11, family: 'JetBrains Mono' },
            stepSize: 4,
            callback: (v) => `${v}°`
          },
          border: { display: false }
        }
      }
    }
  })
}

const initBrixChart = () => {
  if (!brixChartRef.value) return
  if (brixChartInstance) {
    brixChartInstance.destroy()
    brixChartInstance = null
  }

  const ctx = brixChartRef.value.getContext('2d')
  const labels = ['Día 1', 'Día 2', 'Día 3', 'Día 4', 'Día 5', 'Día 6', 'Día 7']
  const brixConsumedBars = [2.1, 2.4, 2.8, 3.1, 2.5, 2.0, 1.8]
  const trendLine = [24.5, 22.4, 20.0, 17.2, 14.1, 11.6, 9.6]

  brixChartInstance = new ChartJS(ctx, {
    data: {
      labels,
      datasets: [
        {
          type: 'line',
          label: 'Evolución Brix (°Bx)',
          data: trendLine,
          borderColor: '#0F172A',
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: '#0F172A',
          tension: 0.35,
          yAxisID: 'y1'
        },
        {
          type: 'bar',
          label: 'Azúcar Convertida/Día',
          data: brixConsumedBars,
          backgroundColor: '#A7F3D0',
          borderRadius: 4,
          yAxisID: 'y'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0F172A',
          padding: 8,
          cornerRadius: 6
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#94A3B8', font: { size: 10 } },
          border: { color: '#E2E8F0' }
        },
        y: {
          position: 'left',
          grid: { color: '#F1F5F9' },
          ticks: { color: '#94A3B8', font: { size: 10 } }
        },
        y1: {
          position: 'right',
          grid: { display: false },
          ticks: { color: '#94A3B8', font: { size: 10 }, callback: (v) => `${v}°Bx` }
        }
      }
    }
  })
}

const updateCharts = () => {
  if (trendChartInstance && stats.value.avgTemp !== '--') {
    const currentData = trendChartInstance.data.datasets[0].data
    currentData[currentData.length - 1] = Number(stats.value.avgTemp)
    trendChartInstance.update('none')
  }
}

watch(activeTab, async () => {
  await nextTick()
  initTrendChart()
  initBrixChart()
})

onMounted(() => {
  fetchCubas(true)
  pollInterval = setInterval(() => fetchCubas(false), 5000)
  secondTicker = setInterval(() => {
    currentSecondsTick.value = Date.now()
  }, 1000)

  // Iniciar gráficos una vez montado el DOM
  nextTick(() => {
    initTrendChart()
    initBrixChart()
  })

  // Sincronizar parámetro de búsqueda de la URL si viene del topbar
  if (route.query.q) {
    searchQuery.value = String(route.query.q)
  }
})

onBeforeUnmount(() => {
  if (pollInterval) clearInterval(pollInterval)
  if (secondTicker) clearInterval(secondTicker)
  if (trendChartInstance) trendChartInstance.destroy()
  if (brixChartInstance) brixChartInstance.destroy()
})
</script>

<template>
  <div class="dashboard-container">
    <!-- 1. Pestañas Secundarias de Navegación (Estilo Searchable) -->
    <nav class="saas-tabs-nav">
      <button
        type="button"
        class="saas-tab-item"
        :class="{ active: activeTab === 'overview' }"
        @click="activeTab = 'overview'"
      >
        Visibilidad & Telemetría
      </button>
      <button
        type="button"
        class="saas-tab-item"
        :class="{ active: activeTab === 'health' }"
        @click="activeTab = 'health'"
      >
        Salud & Diagnóstico IA
      </button>
      <button
        type="button"
        class="saas-tab-item"
        :class="{ active: activeTab === 'comparison' }"
        @click="activeTab = 'comparison'"
      >
        Comparativa de Lotes
      </button>
      <button
        type="button"
        class="saas-tab-item"
        :class="{ active: activeTab === 'grid' }"
        @click="activeTab = 'grid'"
      >
        Cuadrícula de Cubas IoT ({{ filteredCubas.length }})
      </button>
    </nav>

    <!-- 2. Barra de Filtros de Alta Precisión (Estilo Searchable) -->
    <section class="saas-filter-bar">
      <!-- Selector de Entidad / Viña -->
      <div class="saas-filter-pill-entity">
        <span class="entity-dot"></span>
        <span>vina-santaemiliana.cl</span>
        <ChevronDown :size="13" style="color: var(--text-muted);" />
      </div>

      <!-- Selector de Rango Temporal -->
      <div class="saas-filter-select">
        <span>Últimas 24 horas</span>
        <ChevronDown :size="13" style="color: var(--text-muted);" />
      </div>

      <!-- Frecuencia de Telemetría -->
      <div class="saas-filter-select">
        <span>Tiempo Real (5s)</span>
        <ChevronDown :size="13" style="color: var(--text-muted);" />
      </div>

      <!-- Switch Toggle "Solo en Riesgo" -->
      <div class="saas-switch-wrapper" @click="onlyAlertsSwitch = !onlyAlertsSwitch">
        <div class="saas-switch-track" :class="{ active: onlyAlertsSwitch }">
          <div class="saas-switch-thumb"></div>
        </div>
        <span>Solo en Riesgo</span>
      </div>

      <!-- Selector de Cepa / Variedad -->
      <select v-model="selectedVariety" class="saas-filter-select">
        <option value="todas">Todas las Cepas</option>
        <option v-for="varName in variedadesDisponibles" :key="varName" :value="varName">
          {{ varName }}
        </option>
      </select>

      <!-- Selector de Estado de Cubas -->
      <select v-model="selectedStatusFilter" class="saas-filter-select">
        <option value="todos">Todos los Estados</option>
        <option value="normal">Normales</option>
        <option value="advertencia">Advertencias</option>
        <option value="critico">Riesgo Crítico</option>
      </select>

      <!-- Ubicación / Bodega -->
      <div class="saas-filter-select">
        <span>Planta Central</span>
        <ChevronDown :size="13" style="color: var(--text-muted);" />
      </div>

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

    <!-- VISTA 1: OVERVIEW (Visibilidad & Telemetría - Replica Imagen 1) -->
    <div v-show="activeTab === 'overview' || activeTab === 'all'" class="tab-pane-content">
      <!-- Fila 1: Gráfico de Tendencia (Izquierda) + Tabla de Rankings (Derecha) -->
      <div class="overview-grid-row">
        <!-- Tarjeta Izquierda: Tendencia Térmica & Brix (Visibility Score) -->
        <article class="saas-card metric-chart-card">
          <header class="card-header-clean">
            <div class="card-title-group">
              <span class="card-category-label">
                <Eye :size="14" />
                <span>Estabilidad Térmica</span>
              </span>
              <span class="card-subtitle-sub">Tendencia promedio de fermentación en tiempo real</span>
            </div>
            <div class="card-action-mini">
              <span class="live-tag-pill">En Vivo</span>
            </div>
          </header>

          <div class="score-callout-row">
            <div class="big-score-digits">
              {{ stats.avgTemp }}<small>°C</small>
            </div>
            <div class="delta-tag positive">
              <TrendingUp :size="14" />
              <span>+0.4 °C</span>
            </div>
          </div>

          <!-- Canvas del Gráfico Lineal Suave Chart.js -->
          <div class="chart-canvas-container">
            <canvas ref="trendChartRef"></canvas>
          </div>

          <footer class="card-footer-sub">
            <span>Mostrando telemetría de las últimas 24 horas</span>
            <span class="positive-text">● +1.2% consistencia térmica</span>
          </footer>
        </article>

        <!-- Tarjeta Derecha: Tabla de Rankings de Cubas (Rankings Table) -->
        <article class="saas-card rankings-table-card">
          <header class="card-header-clean">
            <div class="card-title-group">
              <span class="card-category-label">
                <Layers :size="14" />
                <span>Ranking & Monitoreo</span>
              </span>
              <span class="card-subtitle-sub">Haga clic en una cuba para ver telemetría completa</span>
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
                    <span class="badge-status" :class="getStatusBadge(cuba.estado).class">
                      {{ getStatusBadge(cuba.estado).label }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </div>

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
            <span class="delta-tag positive">-0.3 °C</span>
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
            <span class="delta-tag positive">+2 cubas</span>
          </div>
        </div>

        <!-- KPI 3: Desvíos y Advertencias -->
        <div class="saas-card kpi-subcard">
          <div class="kpi-subcard-header">
            <span class="kpi-subcard-title">Alertas e Incidencias</span>
            <span class="kpi-subcard-sub">Fuera de perfil</span>
          </div>
          <div class="kpi-subcard-value">
            <span :class="{ 'text-danger': stats.criticos > 0 }">
              {{ stats.advertencias + stats.criticos }} alertas
            </span>
            <span v-if="stats.criticos === 0" class="delta-tag positive">Normalizado</span>
            <span v-else class="delta-tag negative">{{ stats.criticos }} críticas</span>
          </div>
        </div>

        <!-- KPI 4: Índice Global de Calidad -->
        <div class="saas-card kpi-subcard">
          <div class="kpi-subcard-header">
            <span class="kpi-subcard-title">Índice Enológico Global</span>
            <span class="kpi-subcard-sub">Salud de cosecha</span>
          </div>
          <div class="kpi-subcard-value">
            <span>{{ stats.healthScore }}%</span>
            <span class="delta-tag positive">+1.8%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- VISTA 2: HEALTH & DIAGNÓSTICO IA (Replica Imagen 2 Superior) -->
    <div v-show="activeTab === 'health' || activeTab === 'all'" class="tab-pane-content" style="margin-top: 1.5rem;">
      <!-- Tarjeta Principal: Salud de Fermentación & Diagnóstico Predictivo -->
      <article class="saas-card health-perception-card">
        <header class="card-header-clean">
          <div class="card-title-group">
            <span class="card-category-label">
              <ShieldCheck :size="15" />
              <span>Diagnóstico Enológico Predictivo</span>
            </span>
            <span class="card-subtitle-sub">Análisis continuo de telemetría y reglas de fermentación</span>
          </div>
          <div class="saas-filter-select" style="font-size: 0.75rem;">
            <span>Modelo Enológico GPT-IoT</span>
            <ChevronDown :size="12" />
          </div>
        </header>

        <div class="health-card-body">
          <!-- Columna Izquierda: Medidor Circular (Score 90 / 100) -->
          <div class="circular-score-column">
            <div class="circular-ring-wrapper">
              <svg class="circular-ring-svg" viewBox="0 0 120 120">
                <circle
                  cx="60"
                  cy="60"
                  r="52"
                  fill="none"
                  stroke="#E2E8F0"
                  stroke-width="9"
                />
                <circle
                  cx="60"
                  cy="60"
                  r="52"
                  fill="none"
                  stroke="#10B981"
                  stroke-width="9"
                  stroke-dasharray="326.7"
                  :stroke-dashoffset="326.7 * (1 - stats.healthScore / 100)"
                  stroke-linecap="round"
                  transform="rotate(-90 60 60)"
                />
              </svg>
              <div class="score-center-text">
                <span class="score-big">{{ stats.healthScore }}</span>
                <span class="score-max">/ 100</span>
              </div>
            </div>

            <!-- Distribución de Porcentajes con viñetas de colores -->
            <div class="score-bullets-row">
              <span class="bullet-item green">● {{ stats.pctOptimo }}% óptimo</span>
              <span class="bullet-item amber">● {{ stats.pctAtencion }}% atención</span>
              <span class="bullet-item red">● {{ stats.pctCritico }}% riesgo</span>
            </div>

            <span class="score-subtext">Basado en {{ stats.total }} sensores IoT en línea</span>
          </div>

          <!-- Columna Derecha: Diagnóstico Asistido con Tags Resaltados -->
          <div class="insights-narrative-column">
            <div class="insight-item-box">
              <div class="insight-icon-shield">
                <CheckCircle2 :size="18" style="color: #10B981;" />
              </div>
              <div class="insight-text-content">
                <p>
                  El proceso de fermentación muestra un comportamiento altamente favorable para
                  <span class="hl-tag green">estabilidad térmica</span>, con el sistema de refrigeración
                  regulando eficientemente las cubas de
                  <span class="hl-tag blue">Cabernet Sauvignon</span>,
                  <span class="hl-tag blue">Carmenere</span> y
                  <span class="hl-tag blue">Chardonnay</span>.
                  La cinética de consumo de azúcares se encuentra dentro de las curvas previstas.
                </p>
                <p class="mt-2 text-secondary">
                  Puntos de atención detectados:
                  <span class="hl-tag amber">Cuba CB-04</span> registra un leve incremento térmico
                  (+1.2 °C sobre umbral ideal), y se recomienda revisar la válvula solenoide para
                  prevenir desvíos organolépticos.
                </p>
              </div>
            </div>
          </div>
        </div>
      </article>
    </div>

    <!-- VISTA 3: COMPARATIVA HEAD-TO-HEAD & CINÉTICA (Replica Imagen 2 Inferior) -->
    <div v-show="activeTab === 'comparison' || activeTab === 'all'" class="tab-pane-content" style="margin-top: 1.5rem;">
      <div class="comparison-grid-row">
        <!-- Tarjeta Izquierda: Cinética de Azúcares (Sentiment Score style) -->
        <article class="saas-card brix-dynamics-card">
          <header class="card-header-clean">
            <div class="card-title-group">
              <span class="card-category-label">
                <Droplets :size="14" />
                <span>Dinámica de Azúcares (Brix)</span>
              </span>
              <span class="card-subtitle-sub">Tasa de consumo y curva de densidad en 7 días</span>
            </div>
          </header>

          <div class="score-callout-row">
            <div class="big-score-digits">94<small style="font-size: 1rem; color: #64748B;"> pts</small></div>
            <div class="delta-tag positive">
              <TrendingUp :size="14" />
              <span>+4.0</span>
            </div>
          </div>

          <div class="chart-canvas-container" style="height: 180px;">
            <canvas ref="brixChartRef"></canvas>
          </div>
        </article>

        <!-- Tarjeta Derecha: Comparativa Head-to-Head (Lote vs Lote) -->
        <article class="saas-card head-to-head-card">
          <header class="card-header-clean">
            <div class="card-title-group">
              <span class="card-category-label">
                <Scale :size="14" />
                <span>Comparativa Head-to-Head</span>
              </span>
              <span class="card-subtitle-sub">Desempeño relativo entre lotes activos</span>
            </div>
            <div class="saas-filter-select" style="font-size: 0.75rem;">
              <span>CB-02 (Carmenere)</span>
              <ChevronDown :size="12" />
            </div>
          </header>

          <!-- Barra Dividida de Comparación -->
          <div class="h2h-split-bar-section">
            <div class="h2h-labels-row">
              <span class="h2h-entity-name red">● CB-01 (Cabernet)</span>
              <span class="h2h-entity-name dark">CB-02 (Carmenere) ●</span>
            </div>

            <div class="h2h-numbers-row">
              <span class="h2h-big-percent red">52%</span>
              <span class="h2h-big-percent dark">48%</span>
            </div>

            <div class="h2h-progress-split-bar">
              <div class="h2h-bar-left" style="width: 52%;"></div>
              <div class="h2h-bar-right" style="width: 48%;"></div>
            </div>
          </div>

          <!-- Columnas de Checklist de Parámetros -->
          <div class="h2h-features-columns">
            <!-- Columna Lote 1 -->
            <div class="h2h-col">
              <span class="h2h-col-title">Parámetros CB-01</span>
              <ul class="h2h-list">
                <li class="h2h-item good"><Check :size="13" /> Control térmico estable</li>
                <li class="h2h-item good"><Check :size="13" /> Cinética de azúcares óptima</li>
                <li class="h2h-item good"><Check :size="13" /> Válvula de frío al 45%</li>
                <li class="h2h-item warn"><X :size="13" /> Leve varianza nocturna</li>
              </ul>
            </div>

            <!-- Columna Lote 2 -->
            <div class="h2h-col">
              <span class="h2h-col-title">Parámetros CB-02</span>
              <ul class="h2h-list">
                <li class="h2h-item good"><Check :size="13" /> Densímetro calibrado</li>
                <li class="h2h-item good"><Check :size="13" /> Micro-oxigenación regulada</li>
                <li class="h2h-item good"><Check :size="13" /> Respuesta de camisa rápida</li>
                <li class="h2h-item warn"><X :size="13" /> Consumo Brix más lento</li>
              </ul>
            </div>
          </div>
        </article>
      </div>
    </div>

    <!-- VISTA 4: CUADRÍCULA DE CUBAS IOT (Tarjetas Interactivas en Vivo) -->
    <div v-show="activeTab === 'grid' || activeTab === 'all'" class="tab-pane-content" style="margin-top: 1.5rem;">
      <div class="section-title-row">
        <div>
          <h2 class="section-main-title">Supervisión en Tiempo Real de Cubas</h2>
          <p class="section-main-sub">
            Telemetría de temperatura, grados Brix y volumen en tiempo real sincronizada cada 5 segundos.
          </p>
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

            <span class="badge-status" :class="getStatusBadge(cuba.estado).class">
              {{ getStatusBadge(cuba.estado).label }}
            </span>
          </header>

          <!-- Lote y Días -->
          <div class="cuba-saas-submeta">
            <span>{{ cuba.lote }}</span>
            <span class="submeta-divider">·</span>
            <span>{{ cuba.fase }} (Día {{ cuba.dia }})</span>
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
                <span class="metric-range">{{ cuba.tempMin }}°-{{ cuba.tempMax }}°C</span>
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
                <span class="metric-range">{{ getBrixProgress(cuba) }}% conv.</span>
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
  grid-template-columns: 1.35fr 1fr;
  gap: 1.25rem;
}

@media (max-width: 1024px) {
  .overview-grid-row {
    grid-template-columns: 1fr;
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

.card-subtitle-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.live-tag-pill {
  font-size: 0.6875rem;
  font-weight: 600;
  color: #10B981;
  background-color: #ECFDF5;
  border: 1px solid #A7F3D0;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-full);
}

.score-callout-row {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.big-score-digits {
  font-size: 2.25rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--text-primary);
  line-height: 1;
}

.big-score-digits small {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--text-muted);
}

.chart-canvas-container {
  height: 210px;
  position: relative;
  width: 100%;
}

.card-footer-sub {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.85rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-subtle);
  font-size: 0.75rem;
  color: var(--text-muted);
}

.positive-text {
  color: #10B981;
  font-weight: 600;
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
  margin-top: 1.25rem;
}

@media (max-width: 900px) {
  .kpi-metrics-row {
    grid-template-columns: repeat(2, 1fr);
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

/* Tarjeta Health / Brand Perception (Imagen 2) */
.health-perception-card {
  padding: 1.25rem 1.5rem;
}

.health-card-body {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 2rem;
  align-items: center;
  margin-top: 0.75rem;
}

@media (max-width: 860px) {
  .health-card-body {
    grid-template-columns: 1fr;
  }
}

.circular-score-column {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.circular-ring-wrapper {
  position: relative;
  width: 120px;
  height: 120px;
}

.circular-ring-svg {
  width: 100%;
  height: 100%;
}

.score-center-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1;
}

.score-big {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.03em;
}

.score-max {
  font-size: 0.6875rem;
  color: var(--text-muted);
  font-weight: 500;
  margin-top: 2px;
}

.score-bullets-row {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  font-size: 0.6875rem;
  font-weight: 600;
  margin-top: 0.75rem;
}

.bullet-item.green { color: #10B981; }
.bullet-item.amber { color: #F59E0B; }
.bullet-item.red { color: #EF4444; }

.score-subtext {
  font-size: 0.6875rem;
  color: var(--text-muted);
  margin-top: 0.35rem;
}

/* Columna Narrativa de Insights */
.insights-narrative-column {
  display: flex;
  flex-direction: column;
}

.insight-item-box {
  display: flex;
  gap: 1rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  padding: 1.15rem 1.25rem;
  border-radius: var(--radius-md);
}

.insight-icon-shield {
  flex-shrink: 0;
  margin-top: 2px;
}

.insight-text-content p {
  font-size: 0.8125rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

.hl-tag {
  display: inline-block;
  padding: 0.05rem 0.4rem;
  border-radius: var(--radius-xs);
  font-weight: 600;
  font-size: 0.75rem;
}

.hl-tag.green {
  background-color: #ECFDF5;
  color: #065F46;
}

.hl-tag.blue {
  background-color: #EFF6FF;
  color: #1D4ED8;
}

.hl-tag.amber {
  background-color: #FFFBEB;
  color: #B45309;
}

.hl-tag.red {
  background-color: #FEF2F2;
  color: #B91C1C;
}

/* Comparativa y Gráfico Dinámico */
.comparison-grid-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
}

@media (max-width: 900px) {
  .comparison-grid-row {
    grid-template-columns: 1fr;
  }
}

.brix-dynamics-card,
.head-to-head-card {
  padding: 1.25rem 1.35rem;
  display: flex;
  flex-direction: column;
}

.h2h-split-bar-section {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin: 0.5rem 0 1rem;
}

.h2h-labels-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  font-weight: 600;
}

.h2h-entity-name.red { color: #E11D48; }
.h2h-entity-name.dark { color: #0F172A; }

.h2h-numbers-row {
  display: flex;
  justify-content: space-between;
  font-size: 1.65rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.h2h-big-percent.red { color: #E11D48; }
.h2h-big-percent.dark { color: #0F172A; }

.h2h-progress-split-bar {
  display: flex;
  height: 12px;
  border-radius: var(--radius-full);
  overflow: hidden;
  background-color: #E2E8F0;
}

.h2h-bar-left {
  background-color: #E11D48;
}

.h2h-bar-right {
  background-color: #0F172A;
}

.h2h-features-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-subtle);
}

.h2h-col-title {
  font-size: 0.6875rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  display: block;
  margin-bottom: 0.4rem;
}

.h2h-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.h2h-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.h2h-item.good { color: #059669; }
.h2h-item.warn { color: #DC2626; }

/* Cuadrícula de Cubas IoT */
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
</style>
