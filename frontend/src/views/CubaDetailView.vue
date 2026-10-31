<script setup>
/**
 * 📋 04. [FRONT - VUE] Pantalla de Detalle de Cuba
 * Módulo 2: Monitoreo en Vivo (Core)
 *
 * Enfoque realista para proyecto IoT:
 * - Sensores físicos reales:
 *   1. DS18B20: Temperatura del mosto (°C).
 *   2. MPU-6050: Ángulo de inclinación del flotador (°) convertido a Grados Brix (°Bx).
 * - Lógica simple y defendible (sin ML ni actuadores de frío ficticios):
 *   Reglas de umbrales: Detectar si la temperatura sube/baja de golpe o si el Brix se estanca.
 * - Gráficos claros con Chart.js registrados con registerables para máxima estabilidad.
 */
import { ref, computed, onMounted, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Cylinder,
  Thermometer,
  Activity,
  Compass,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Clock,
  ArrowLeft,
  ChevronDown,
  Info
} from 'lucide-vue-next'

import { Chart as ChartJS, registerables } from 'chart.js'
ChartJS.register(...registerables)

const route = useRoute()
const router = useRouter()

// ==========================================
// DATASETS MOCK DE CUBAS REALISTAS
// ==========================================
const cubasMock = [
  {
    id: '01',
    code: 'CB-01',
    name: 'Cuba 01 · Cabernet Sauvignon',
    variety: 'Cabernet Sauvignon',
    vintage: 'Vendimia 2026',
    status: 'optimal', // optimal | warning
    statusLabel: 'Normal · Fermentación Activa',
    dayOfFermentation: 5,
    totalEstimatedDays: 14,
    // Sensor 1: Temperatura DS18B20
    temperature: 24.6,
    tempChange2h: '+0.2°C',
    tempTrend: 'up',
    tempMinRule: 20.0,
    tempMaxRule: 28.0,
    // Sensor 2: MPU-6050 Inclinómetro
    tiltAngle: 42.5, // Grados de inclinación del flotador
    brix: 13.2,      // Grados Brix calculados
    brixDelta24h: '-2.0 °Bx en 24h',
    // Diagnóstico por reglas simples
    alertReason: null,
    history: {
      '24h': {
        labels: ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00', 'Ahora'],
        temp: [24.0, 24.2, 24.3, 24.5, 24.8, 25.0, 24.9, 24.7, 24.6],
        brix: [15.2, 14.9, 14.7, 14.4, 14.1, 13.8, 13.6, 13.4, 13.2]
      },
      '48h': {
        labels: ['Hace 48h', 'Hace 36h', 'Hace 24h', 'Hace 18h', 'Hace 12h', 'Hace 6h', 'Ahora'],
        temp: [23.5, 23.9, 24.2, 24.5, 24.8, 24.7, 24.6],
        brix: [17.5, 16.4, 15.2, 14.5, 14.0, 13.5, 13.2]
      },
      '7d': {
        labels: ['Día 1', 'Día 2', 'Día 3', 'Día 4', 'Día 5 (Hoy)'],
        temp: [20.5, 22.8, 24.0, 24.5, 24.6],
        brix: [24.0, 21.5, 18.2, 15.5, 13.2]
      }
    },
    alertsList: [
      { id: 1, time: 'Hoy 14:30', text: 'Lectura telemétrica estable: 24.6°C y 13.2 °Bx.', type: 'normal' },
      { id: 2, time: 'Ayer 20:10', text: 'Consumo de azúcar normal: descenso de 2.0 °Bx en las últimas 24 horas.', type: 'normal' }
    ]
  },
  {
    id: '02',
    code: 'CB-02',
    name: 'Cuba 02 · Carmenere',
    variety: 'Carmenere',
    vintage: 'Vendimia 2026',
    status: 'warning',
    statusLabel: 'Alerta · Caída Brusca de Temperatura',
    dayOfFermentation: 4,
    totalEstimatedDays: 12,
    temperature: 17.5,
    tempChange2h: '-3.2°C',
    tempTrend: 'down',
    tempMinRule: 20.0,
    tempMaxRule: 28.0,
    tiltAngle: 58.2,
    brix: 18.4,
    brixDelta24h: '0.0 °Bx (Sin descenso en 12h)',
    alertReason: 'Se detectó una caída térmica mayor a 2°C en 2 horas (-3.2°C). Los grados Brix no han descendido, lo que indica posible aletargamiento de levaduras.',
    history: {
      '24h': {
        labels: ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00', 'Ahora'],
        temp: [23.5, 23.2, 22.8, 22.0, 21.2, 19.5, 18.2, 17.8, 17.5],
        brix: [18.6, 18.5, 18.5, 18.4, 18.4, 18.4, 18.4, 18.4, 18.4]
      },
      '48h': {
        labels: ['Hace 48h', 'Hace 36h', 'Hace 24h', 'Hace 18h', 'Hace 12h', 'Hace 6h', 'Ahora'],
        temp: [24.0, 24.2, 23.8, 23.0, 21.0, 18.5, 17.5],
        brix: [21.8, 20.2, 18.6, 18.5, 18.4, 18.4, 18.4]
      },
      '7d': {
        labels: ['Día 1', 'Día 2', 'Día 3', 'Día 4 (Hoy)'],
        temp: [21.0, 23.5, 24.0, 17.5],
        brix: [24.5, 22.4, 19.8, 18.4]
      }
    },
    alertsList: [
      { id: 1, time: 'Hace 35 min', text: 'ALERTA REGLA TÉRMICA: Variación brusca negativa (-3.2°C en 2 horas).', type: 'warning' },
      { id: 2, time: 'Hace 2 horas', text: 'ALERTA REGLA BRIX: Curva de azúcar plana (18.4 °Bx sin cambio).', type: 'warning' }
    ]
  },
  {
    id: '03',
    code: 'CB-03',
    name: 'Cuba 03 · Sauvignon Blanc',
    variety: 'Sauvignon Blanc',
    vintage: 'Vendimia 2026',
    status: 'optimal',
    statusLabel: 'Normal · Fermentación en Frío',
    dayOfFermentation: 8,
    totalEstimatedDays: 15,
    temperature: 15.2,
    tempChange2h: '+0.1°C',
    tempTrend: 'up',
    tempMinRule: 13.0,
    tempMaxRule: 18.0,
    tiltAngle: 28.0,
    brix: 6.8,
    brixDelta24h: '-1.2 °Bx en 24h',
    alertReason: null,
    history: {
      '24h': {
        labels: ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00', 'Ahora'],
        temp: [15.0, 15.1, 15.0, 15.2, 15.3, 15.2, 15.1, 15.2, 15.2],
        brix: [8.0, 7.8, 7.6, 7.5, 7.3, 7.1, 7.0, 6.9, 6.8]
      },
      '48h': {
        labels: ['Hace 48h', 'Hace 36h', 'Hace 24h', 'Hace 18h', 'Hace 12h', 'Hace 6h', 'Ahora'],
        temp: [14.8, 15.0, 15.1, 15.0, 15.2, 15.1, 15.2],
        brix: [9.2, 8.6, 8.0, 7.6, 7.2, 6.9, 6.8]
      },
      '7d': {
        labels: ['Día 4', 'Día 5', 'Día 6', 'Día 7', 'Día 8 (Hoy)'],
        temp: [15.1, 15.0, 15.2, 15.1, 15.2],
        brix: [12.5, 10.8, 9.4, 8.1, 6.8]
      }
    },
    alertsList: [
      { id: 1, time: 'Hoy 10:00', text: 'Temperatura controlada en perfil de vino blanco (15.2°C).', type: 'normal' }
    ]
  }
]

// ==========================================
// ESTADO REACTIVO
// ==========================================
const selectedCubaId = ref('01')
const activeTimeRange = ref('24h') // '24h' | '48h' | '7d'
const activeChartTab = ref('both') // 'both' | 'temp' | 'brix'

const chartCanvasRef = ref(null)
let chartInstance = null

function syncFromRoute() {
  const routeId = route.params.id || route.query.id
  if (routeId) {
    const found = cubasMock.find(c => c.id === String(routeId) || c.code.toLowerCase() === String(routeId).toLowerCase())
    if (found) {
      selectedCubaId.value = found.id
      return
    }
  }
  selectedCubaId.value = '01'
}

const currentCuba = computed(() => {
  return cubasMock.find(c => c.id === selectedCubaId.value) || cubasMock[0]
})

function onCubaChange(e) {
  selectedCubaId.value = e.target.value
  router.replace({ path: `/cubas/${selectedCubaId.value}` })
}

// ==========================================
// RENDERIZADO DEL GRÁFICO (Chart.js)
// ==========================================
async function renderChart() {
  await nextTick()
  if (!chartCanvasRef.value) return

  const dataset = currentCuba.value.history[activeTimeRange.value]
  if (!dataset) return

  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }

  const ctx = chartCanvasRef.value.getContext('2d')

  // Gradiente suave de temperatura
  const tempGrad = ctx.createLinearGradient(0, 0, 0, 260)
  tempGrad.addColorStop(0, 'rgba(118, 31, 51, 0.25)')
  tempGrad.addColorStop(1, 'rgba(118, 31, 51, 0.02)')

  // Gradiente suave de brix
  const brixGrad = ctx.createLinearGradient(0, 0, 0, 260)
  brixGrad.addColorStop(0, 'rgba(196, 127, 23, 0.25)')
  brixGrad.addColorStop(1, 'rgba(196, 127, 23, 0.02)')

  const datasets = []

  if (activeChartTab.value === 'both' || activeChartTab.value === 'temp') {
    datasets.push({
      label: 'Temperatura DS18B20 (°C)',
      data: dataset.temp,
      borderColor: '#761F33',
      backgroundColor: tempGrad,
      borderWidth: 2.5,
      tension: 0.3,
      pointRadius: 4,
      pointBackgroundColor: '#FFFFFF',
      pointBorderColor: '#761F33',
      pointBorderWidth: 2,
      fill: true,
      yAxisID: 'yTemp'
    })
  }

  if (activeChartTab.value === 'both' || activeChartTab.value === 'brix') {
    datasets.push({
      label: 'Grados Brix MPU-6050 (°Bx)',
      data: dataset.brix,
      borderColor: '#C47F17',
      backgroundColor: brixGrad,
      borderWidth: 2.5,
      borderDash: [5, 4],
      tension: 0.3,
      pointRadius: 4,
      pointBackgroundColor: '#FFFFFF',
      pointBorderColor: '#C47F17',
      pointBorderWidth: 2,
      fill: true,
      yAxisID: activeChartTab.value === 'both' ? 'yBrix' : 'yTemp'
    })
  }

  const scalesConfig = {
    x: {
      grid: { color: 'rgba(232, 224, 221, 0.6)' },
      ticks: {
        color: '#66525B',
        font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 }
      }
    },
    yTemp: {
      type: 'linear',
      position: 'left',
      title: {
        display: true,
        text: activeChartTab.value === 'brix' ? 'Grados Brix (°Bx)' : 'Temperatura (°C)',
        color: activeChartTab.value === 'brix' ? '#C47F17' : '#761F33',
        font: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: '600' }
      },
      grid: { color: 'rgba(232, 224, 221, 0.5)' },
      ticks: {
        color: activeChartTab.value === 'brix' ? '#C47F17' : '#761F33',
        font: { family: "'JetBrains Mono', monospace", size: 11 }
      }
    }
  }

  if (activeChartTab.value === 'both') {
    scalesConfig.yBrix = {
      type: 'linear',
      position: 'right',
      title: {
        display: true,
        text: 'Grados Brix (°Bx)',
        color: '#C47F17',
        font: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: '600' }
      },
      grid: { drawOnChartArea: false },
      ticks: {
        color: '#C47F17',
        font: { family: "'JetBrains Mono', monospace", size: 11 }
      }
    }
  }

  chartInstance = new ChartJS(ctx, {
    type: 'line',
    data: {
      labels: dataset.labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            boxWidth: 14,
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 12 }
          }
        },
        tooltip: {
          backgroundColor: '#300C15',
          padding: 10,
          titleFont: { size: 12, weight: 'bold' }
        }
      },
      scales: scalesConfig
    }
  })
}

onMounted(() => {
  syncFromRoute()
  renderChart()
})

watch(
  () => route.params.id,
  () => {
    syncFromRoute()
    renderChart()
  }
)

watch([selectedCubaId, activeTimeRange, activeChartTab], () => {
  renderChart()
})

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.destroy()
  }
})
</script>

<template>
  <div class="view-container cuba-detail-view">
    <!-- Encabezado con selector de cuba -->
    <header class="detail-header">
      <div class="header-left">
        <router-link to="/" class="back-link">
          <ArrowLeft :size="16" />
          <span>Volver al Dashboard</span>
        </router-link>

        <div class="title-selector-row">
          <div class="cuba-icon-box">
            <Cylinder :size="24" :stroke-width="1.8" />
          </div>
          <div>
            <div class="selector-wrapper">
              <select
                :value="selectedCubaId"
                @change="onCubaChange"
                class="cuba-select"
              >
                <option v-for="c in cubasMock" :key="c.id" :value="c.id">
                  {{ c.name }}
                </option>
              </select>
              <ChevronDown :size="18" class="select-chevron" />
            </div>
            <p class="cuba-subtitle">
              {{ currentCuba.variety }} · {{ currentCuba.vintage }} · Monitoreo de Fermentación
            </p>
          </div>
        </div>
      </div>

      <!-- Estado en base a reglas -->
      <div class="header-right">
        <div
          class="status-pill"
          :class="currentCuba.status === 'optimal' ? 'status-pill--optimal' : 'status-pill--warning'"
        >
          <span class="status-dot"></span>
          <span>{{ currentCuba.statusLabel }}</span>
        </div>

        <div class="days-tracker">
          <span>Día {{ currentCuba.dayOfFermentation }} de aprox. {{ currentCuba.totalEstimatedDays }}</span>
        </div>
      </div>
    </header>

    <!-- Alerta destacada si se rompen las reglas (sin ML, solo umbrales) -->
    <div v-if="currentCuba.alertReason" class="alert-box">
      <div class="alert-box-icon">
        <AlertTriangle :size="22" />
      </div>
      <div class="alert-box-content">
        <h4>Alerta por Regla Térmica y Brix</h4>
        <p>{{ currentCuba.alertReason }}</p>
      </div>
    </div>

    <!-- Paneles de las dos métricas que realmente miden los sensores -->
    <section class="metrics-grid">
      <!-- 1. Sensor DS18B20: Temperatura -->
      <div class="metric-card">
        <div class="metric-card-top">
          <div>
            <span class="sensor-tag">Sensor DS18B20</span>
            <h3 class="metric-title">Temperatura del Mosto</h3>
          </div>
          <div class="metric-icon metric-icon-temp">
            <Thermometer :size="22" />
          </div>
        </div>

        <div class="metric-val-group">
          <span class="metric-number">{{ currentCuba.temperature.toFixed(1) }}</span>
          <span class="metric-unit">°C</span>
        </div>

        <div class="metric-details">
          <div
            class="trend-tag"
            :class="currentCuba.tempTrend === 'up' ? 'trend-up' : 'trend-down'"
          >
            <component :is="currentCuba.tempTrend === 'up' ? TrendingUp : TrendingDown" :size="14" />
            <span>{{ currentCuba.tempChange2h }} en las últimas 2 horas</span>
          </div>
          <span class="metric-subtext">Rango de referencia: {{ currentCuba.tempMinRule }}°C a {{ currentCuba.tempMaxRule }}°C</span>
        </div>
      </div>

      <!-- 2. Sensor MPU-6050: Inclinación y Brix -->
      <div class="metric-card">
        <div class="metric-card-top">
          <div>
            <span class="sensor-tag">Sensor MPU-6050</span>
            <h3 class="metric-title">Azúcar y Densidad (Brix)</h3>
          </div>
          <div class="metric-icon metric-icon-brix">
            <Compass :size="22" />
          </div>
        </div>

        <div class="metric-val-group">
          <span class="metric-number">{{ currentCuba.brix.toFixed(1) }}</span>
          <span class="metric-unit">°Bx</span>
        </div>

        <div class="metric-details">
          <div class="tilt-info">
            <span>Inclinación medida del flotador:</span>
            <strong>{{ currentCuba.tiltAngle }}°</strong>
          </div>
          <span class="metric-subtext">Ritmo: {{ currentCuba.brixDelta24h }}</span>
        </div>
      </div>

      <!-- 3. Estado del Proceso (Diagnóstico Simple) -->
      <div class="metric-card">
        <div class="metric-card-top">
          <div>
            <span class="sensor-tag">Diagnóstico de Reglas</span>
            <h3 class="metric-title">Estado del Proceso</h3>
          </div>
          <div
            class="metric-icon"
            :class="currentCuba.status === 'optimal' ? 'metric-icon-good' : 'metric-icon-warn'"
          >
            <Activity :size="22" />
          </div>
        </div>

        <div class="metric-val-group">
          <span class="status-summary-text" :class="'summary-' + currentCuba.status">
            {{ currentCuba.status === 'optimal' ? 'Fermentación Normal' : 'Riesgo / Anomalía' }}
          </span>
        </div>

        <div class="metric-details">
          <p class="rule-explanation">
            {{ currentCuba.status === 'optimal'
              ? 'El consumo de azúcar es continuo y la temperatura se mantiene estable.'
              : 'Se detectó subida o bajada brusca de temperatura o estancamiento del Brix.' }}
          </p>
        </div>
      </div>
    </section>

    <!-- Gráficos de Telemetría -->
    <section class="chart-section">
      <div class="chart-header">
        <div>
          <h2 class="chart-main-title">Evolución Temporal de la Cuba</h2>
          <p class="chart-main-subtitle">
            Curva de temperatura (DS18B20) y descenso de azúcar (MPU-6050)
          </p>
        </div>

        <div class="chart-controls">
          <!-- Filtro de series -->
          <div class="btn-group">
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'both' }"
              @click="activeChartTab = 'both'"
            >
              Ambos Sensores
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'temp' }"
              @click="activeChartTab = 'temp'"
            >
              Solo Temperatura
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'brix' }"
              @click="activeChartTab = 'brix'"
            >
              Solo Brix
            </button>
          </div>

          <!-- Filtro de tiempo -->
          <div class="btn-group">
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '24h' }"
              @click="activeTimeRange = '24h'"
            >
              24 Horas
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '48h' }"
              @click="activeTimeRange = '48h'"
            >
              48 Horas
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '7d' }"
              @click="activeTimeRange = '7d'"
            >
              7 Días
            </button>
          </div>
        </div>
      </div>

      <!-- Canvas de Chart.js -->
      <div class="chart-wrapper">
        <canvas ref="chartCanvasRef"></canvas>
      </div>

      <div class="chart-legend-box">
        <div class="legend-item">
          <span class="legend-color legend-temp"></span>
          <span><strong>Temperatura (°C):</strong> Curva del sensor sumergible DS18B20.</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-brix"></span>
          <span><strong>Azúcar (°Bx):</strong> Grados Brix calculados por el ángulo de inclinación del MPU-6050.</span>
        </div>
      </div>
    </section>

    <!-- Historial de Alertas y Eventos Recientes -->
    <section class="events-section">
      <div class="events-header">
        <div class="events-title">
          <Clock :size="18" />
          <h3>Historial de Lecturas y Alertas de esta Cuba</h3>
        </div>
        <span class="events-count">{{ currentCuba.alertsList.length }} registros</span>
      </div>

      <div class="events-list">
        <div
          v-for="item in currentCuba.alertsList"
          :key="item.id"
          class="event-row"
          :class="'event-row--' + item.type"
        >
          <div class="event-dot"></div>
          <div class="event-content">
            <span class="event-timestamp">{{ item.time }}</span>
            <p class="event-message">{{ item.text }}</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.cuba-detail-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding-bottom: 2.5rem;
}

/* Header */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--text-muted);
  font-size: 0.82rem;
  margin-bottom: 0.6rem;
  font-weight: 500;
}

.back-link:hover {
  color: var(--wine-700);
}

.title-selector-row {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.cuba-icon-box {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background-color: var(--wine-100);
  border: 1px solid var(--border-color);
  color: var(--wine-700);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.selector-wrapper {
  position: relative;
  display: inline-block;
}

.cuba-select {
  appearance: none;
  background-color: transparent;
  border: none;
  font-family: var(--font-serif);
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--wine-900);
  padding-right: 1.6rem;
  cursor: pointer;
  outline: none;
}

.cuba-select:focus {
  border-bottom: 2px solid var(--wine-700);
}

.select-chevron {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  color: var(--wine-700);
  pointer-events: none;
}

.cuba-subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.header-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.5rem;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.78rem;
  font-weight: 600;
  padding: 0.35rem 0.8rem;
  border-radius: var(--radius-full);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.status-pill--optimal {
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border: 1px solid var(--status-good-border);
}
.status-pill--optimal .status-dot {
  background-color: var(--status-good);
}

.status-pill--warning {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
  border: 1px solid var(--status-warn-border);
}
.status-pill--warning .status-dot {
  background-color: var(--status-warn);
}

.days-tracker {
  font-size: 0.78rem;
  color: var(--text-secondary);
  font-weight: 500;
}

/* Alerta de reglas */
.alert-box {
  background-color: var(--status-warn-bg);
  border: 1px solid var(--status-warn-border);
  border-radius: var(--radius-md);
  padding: 1rem 1.25rem;
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
}

.alert-box-icon {
  color: var(--status-warn);
  flex-shrink: 0;
  margin-top: 0.15rem;
}

.alert-box-content h4 {
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--status-warn);
  margin-bottom: 0.25rem;
}

.alert-box-content p {
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

/* Métricas Numéricas */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1.2rem;
}

.metric-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.25rem;
  box-shadow: var(--shadow-subtle);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.metric-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.sensor-tag {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.metric-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 0.15rem;
}

.metric-icon {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

.metric-icon-temp {
  background-color: var(--wine-100);
  color: var(--wine-700);
}

.metric-icon-brix {
  background-color: #FEF8EF;
  color: #C47F17;
}

.metric-icon-good {
  background-color: var(--status-good-bg);
  color: var(--status-good);
}

.metric-icon-warn {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
}

.metric-val-group {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  margin-bottom: 0.75rem;
}

.metric-number {
  font-family: var(--font-mono);
  font-size: 2.2rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1;
}

.metric-unit {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.status-summary-text {
  font-size: 1.2rem;
  font-weight: 700;
}

.summary-optimal {
  color: var(--status-good);
}

.summary-warning {
  color: var(--status-warn);
}

.metric-details {
  border-top: 1px solid var(--border-subtle);
  padding-top: 0.65rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.trend-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.trend-up {
  color: var(--wine-700);
}

.trend-down {
  color: #1565C0;
}

.tilt-info {
  font-size: 0.75rem;
  color: var(--text-secondary);
  display: flex;
  justify-content: space-between;
}

.tilt-info strong {
  font-family: var(--font-mono);
  color: var(--wine-800);
}

.metric-subtext {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.rule-explanation {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.35;
}

/* Gráfico */
.chart-section {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  box-shadow: var(--shadow-subtle);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.chart-main-title {
  font-family: var(--font-serif);
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--wine-900);
}

.chart-main-subtitle {
  font-size: 0.82rem;
  color: var(--text-muted);
}

.chart-controls {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.btn-group {
  display: flex;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 0.2rem;
  gap: 0.2rem;
}

.btn-filter {
  padding: 0.3rem 0.65rem;
  font-size: 0.74rem;
  font-weight: 600;
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.btn-filter.active {
  background-color: var(--bg-surface);
  color: var(--wine-800);
  box-shadow: 0 1px 3px rgba(35, 22, 28, 0.08);
}

.chart-wrapper {
  position: relative;
  height: 320px;
  width: 100%;
}

.chart-legend-box {
  margin-top: 1rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.legend-color {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.legend-temp {
  background-color: #761F33;
}

.legend-brix {
  background-color: #C47F17;
}

/* Eventos / Historial */
.events-section {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.25rem 1.5rem;
}

.events-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 0.65rem;
  margin-bottom: 1rem;
}

.events-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--wine-800);
}

.events-title h3 {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wine-900);
}

.events-count {
  font-size: 0.72rem;
  color: var(--text-muted);
  background-color: var(--bg-subtle);
  padding: 0.2rem 0.5rem;
  border-radius: var(--radius-full);
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.event-row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.event-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 0.35rem;
  background-color: var(--status-good);
  flex-shrink: 0;
}

.event-row--warning .event-dot {
  background-color: var(--status-warn);
}

.event-content {
  display: flex;
  flex-direction: column;
}

.event-timestamp {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-weight: 600;
}

.event-message {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.35;
}
</style>
