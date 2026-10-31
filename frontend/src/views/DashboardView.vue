<script setup>
/**
 * 📋 03. [FRONT - VUE] Pantalla de Dashboard General (Dash)
 * Módulo 2: Monitoreo en Vivo (Core)
 *
 * Características implementadas:
 * 1. Cuadrícula (grid) responsive y moderna de tarjetas de cubas con datos mock locales.
 * 2. Indicadores visuales en tiempo real: Temperatura (°C), Grados Brix (°Bx) y Semáforos de Estado (Normal, Advertencia, Crítico).
 * 3. Barra de métricas resumen (KPIs) con filtrado interactivo por clic.
 * 4. Barra de herramientas con buscador por cepa/cuba y filtros de estado.
 * 5. Simulación de telemetría en vivo (actualización reactiva de lecturas con fluctuaciones reales).
 * 6. Enlaces interactivos al detalle de cuba.
 * 7. 100% Frontend autónomo (sin requerir backend).
 */

import { ref, computed } from 'vue'
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
  Sparkles
} from 'lucide-vue-next'

const router = useRouter()

// Datos mock iniciales de las cubas de la bodega
const cubas = ref([
  {
    id: 1,
    codigo: 'Cuba 01',
    variedad: 'Cabernet Sauvignon',
    lote: 'Lote CS-2024-A',
    fase: 'Fermentación Alcohólica',
    dia: 6,
    volumenActual: 13500,
    volumenTotal: 15000,
    temperatura: 23.4,
    tempMin: 22.0,
    tempMax: 26.0,
    brix: 14.2,
    brixInicial: 24.5,
    estado: 'normal', // 'normal' | 'advertencia' | 'critico'
    tendenciaTemp: 'estable',
    ultimaLectura: 'Hace 1 min'
  },
  {
    id: 2,
    codigo: 'Cuba 02',
    variedad: 'Carménère',
    lote: 'Lote CM-2024-B',
    fase: 'Fermentación Alcohólica',
    dia: 3,
    volumenActual: 11800,
    volumenTotal: 12000,
    temperatura: 27.6,
    tempMin: 23.0,
    tempMax: 27.0,
    brix: 18.5,
    brixInicial: 25.0,
    estado: 'advertencia',
    tendenciaTemp: 'alza',
    ultimaLectura: 'Hace 30 seg',
    alertaMsg: 'Temperatura cerca del límite superior (+0.6 °C)'
  },
  {
    id: 3,
    codigo: 'Cuba 03',
    variedad: 'Sauvignon Blanc',
    lote: 'Lote SB-2024-F',
    fase: 'Fermentación en Frío',
    dia: 9,
    volumenActual: 9500,
    volumenTotal: 10000,
    temperatura: 15.2,
    tempMin: 14.0,
    tempMax: 17.0,
    brix: 8.1,
    brixInicial: 22.0,
    estado: 'normal',
    tendenciaTemp: 'baja',
    ultimaLectura: 'Hace 2 min'
  },
  {
    id: 4,
    codigo: 'Cuba 04',
    variedad: 'Syrah',
    lote: 'Lote SY-2024-C',
    fase: 'Pico de Fermentación',
    dia: 4,
    volumenActual: 17200,
    volumenTotal: 18000,
    temperatura: 30.1,
    tempMin: 24.0,
    tempMax: 28.0,
    brix: 11.4,
    brixInicial: 25.5,
    estado: 'critico',
    tendenciaTemp: 'alza',
    ultimaLectura: 'Hace 15 seg',
    alertaMsg: 'Alerta de sobrecalentamiento. Riesgo de parada de levadura.'
  },
  {
    id: 5,
    codigo: 'Cuba 05',
    variedad: 'Merlot',
    lote: 'Lote ME-2024-A',
    fase: 'Fin de Fermentación',
    dia: 11,
    volumenActual: 14200,
    volumenTotal: 15000,
    temperatura: 21.8,
    tempMin: 20.0,
    tempMax: 25.0,
    brix: 3.4,
    brixInicial: 24.0,
    estado: 'normal',
    tendenciaTemp: 'estable',
    ultimaLectura: 'Hace 3 min'
  },
  {
    id: 6,
    codigo: 'Cuba 06',
    variedad: 'Pinot Noir',
    lote: 'Lote PN-2024-D',
    fase: 'Maceración Prefermentativa',
    dia: 2,
    volumenActual: 7800,
    volumenTotal: 8000,
    temperatura: 12.5,
    tempMin: 10.0,
    tempMax: 14.0,
    brix: 23.2,
    brixInicial: 23.5,
    estado: 'normal',
    tendenciaTemp: 'estable',
    ultimaLectura: 'Hace 1 min'
  },
  {
    id: 7,
    codigo: 'Cuba 07',
    variedad: 'Chardonnay',
    lote: 'Lote CH-2024-E',
    fase: 'Estabilización y Borras',
    dia: 14,
    volumenActual: 11900,
    volumenTotal: 12000,
    temperatura: 13.9,
    tempMin: 12.0,
    tempMax: 16.0,
    brix: 1.8,
    brixInicial: 22.8,
    estado: 'normal',
    tendenciaTemp: 'estable',
    ultimaLectura: 'Hace 5 min'
  },
  {
    id: 8,
    codigo: 'Cuba 08',
    variedad: 'Malbec',
    lote: 'Lote MB-2024-B',
    fase: 'Fase Inicial',
    dia: 2,
    volumenActual: 15400,
    volumenTotal: 16000,
    temperatura: 26.8,
    tempMin: 22.0,
    tempMax: 26.0,
    brix: 20.4,
    brixInicial: 25.0,
    estado: 'advertencia',
    tendenciaTemp: 'alza',
    ultimaLectura: 'Hace 45 seg',
    alertaMsg: 'Tendencia rápida al alza (+1.2 °C en 2h)'
  },
  {
    id: 9,
    codigo: 'Cuba 09',
    variedad: 'Cabernet Franc',
    lote: 'Lote CF-2024-A',
    fase: 'Fermentación Media',
    dia: 7,
    volumenActual: 10800,
    volumenTotal: 11000,
    temperatura: 24.2,
    tempMin: 22.0,
    tempMax: 26.0,
    brix: 9.8,
    brixInicial: 24.8,
    estado: 'normal',
    tendenciaTemp: 'estable',
    ultimaLectura: 'Hace 2 min'
  }
])

// Filtros y Búsqueda
const searchQuery = ref('')
const selectedFilter = ref('todos') // 'todos' | 'normal' | 'advertencia' | 'critico'
const sortBy = ref('id') // 'id' | 'temp-desc' | 'brix-asc' | 'alerta'
const isRefreshing = ref(false)

// Métricas Globales (KPIs)
const stats = computed(() => {
  const total = cubas.value.length
  const normales = cubas.value.filter(c => c.estado === 'normal').length
  const advertencias = cubas.value.filter(c => c.estado === 'advertencia').length
  const criticos = cubas.value.filter(c => c.estado === 'critico').length

  const sumTemp = cubas.value.reduce((acc, c) => acc + c.temperatura, 0)
  const avgTemp = (sumTemp / total).toFixed(1)

  return { total, normales, advertencias, criticos, avgTemp }
})

// Lista filtrada y ordenada
const filteredCubas = computed(() => {
  return cubas.value
    .filter(c => {
      // Filtro por estado
      if (selectedFilter.value !== 'todos' && c.estado !== selectedFilter.value) {
        return false
      }
      // Búsqueda por texto (código o cepa o lote)
      if (searchQuery.value.trim()) {
        const q = searchQuery.value.toLowerCase()
        return (
          c.codigo.toLowerCase().includes(q) ||
          c.variedad.toLowerCase().includes(q) ||
          c.lote.toLowerCase().includes(q) ||
          c.fase.toLowerCase().includes(q)
        )
      }
      return true
    })
    .sort((a, b) => {
      if (sortBy.value === 'temp-desc') return b.temperatura - a.temperatura
      if (sortBy.value === 'temp-asc') return a.temperatura - b.temperatura
      if (sortBy.value === 'brix-asc') return a.brix - b.brix
      if (sortBy.value === 'brix-desc') return b.brix - a.brix
      if (sortBy.value === 'alerta') {
        const order = { critico: 0, advertencia: 1, normal: 2 }
        return order[a.estado] - order[b.estado]
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
  const consumed = Math.max(0, cuba.brixInicial - cuba.brix)
  const percentage = (consumed / cuba.brixInicial) * 100
  return Math.min(100, Math.max(0, Math.round(percentage)))
}

// Simulación de actualización de telemetría (Reactividad en vivo)
const simulateTelemetryRefresh = () => {
  isRefreshing.value = true

  setTimeout(() => {
    cubas.value = cubas.value.map(c => {
      // Fluctuación aleatoria leve (-0.3 a +0.3 °C)
      const deltaTemp = (Math.random() * 0.6 - 0.3)
      const newTemp = Math.round((c.temperatura + deltaTemp) * 10) / 10

      // Consumo leve de brix si está fermentando
      let newBrix = c.brix
      if (c.brix > 1 && Math.random() > 0.6) {
        newBrix = Math.round((c.brix - 0.1) * 10) / 10
      }

      // Evaluar estado térmico según umbrales de la cuba
      let newEstado = c.estado
      if (newTemp > c.tempMax + 1.5) {
        newEstado = 'critico'
      } else if (newTemp > c.tempMax || newTemp < c.tempMin) {
        newEstado = 'advertencia'
      } else {
        newEstado = 'normal'
      }

      return {
        ...c,
        temperatura: newTemp,
        brix: newBrix,
        estado: newEstado,
        ultimaLectura: 'Hace instantes'
      }
    })
    isRefreshing.value = false
  }, 600)
}

// Navegación hacia detalle de cuba
const goToDetail = (cubaId) => {
  router.push(`/cuba-detalle?id=${cubaId}`)
}
</script>

<template>
  <div class="dashboard-page">
    <!-- Encabezado de la Vista -->
    <header class="dashboard-header">
      <div>
        <div class="header-pretitle">
          <span>Monitoreo en Tiempo Real</span>
          <span class="live-dot"></span>
        </div>
        <h1 class="header-title">Vista General de Cubas</h1>
        <p class="header-description">
          Supervisión termométrica y enológica de las cubas activas en la bodega central.
        </p>
      </div>

      <!-- Botón de actualización simulada -->
      <div class="header-actions">
        <button
          type="button"
          class="btn-refresh"
          :class="{ 'is-spinning': isRefreshing }"
          :disabled="isRefreshing"
          title="Simular nueva lectura de telemetría IoT"
          @click="simulateTelemetryRefresh"
        >
          <RefreshCw :size="15" />
          <span>{{ isRefreshing ? 'Leyendo Sensores...' : 'Actualizar Telemetría' }}</span>
        </button>
      </div>
    </header>

    <!-- Barra de Métricas y Semáforos Resumen (KPIs) -->
    <section class="kpi-grid">
      <!-- Total Cubas -->
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
          <span class="kpi-label">Cubas en Monitoreo</span>
        </div>
      </div>

      <!-- Cubas Normales -->
      <div
        class="kpi-card good"
        :class="{ active: selectedFilter === 'normal' }"
        @click="selectedFilter = 'normal'"
      >
        <div class="kpi-icon-box good">
          <CheckCircle2 :size="20" />
        </div>
        <div class="kpi-data">
          <div class="kpi-number-row">
            <span class="kpi-number">{{ stats.normales }}</span>
            <span class="kpi-indicator green"></span>
          </div>
          <span class="kpi-label">En Rango Óptimo</span>
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
          <span class="kpi-label">En Advertencia</span>
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
          <span class="kpi-number">{{ stats.avgTemp }}<small>°C</small></span>
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
          placeholder="Buscar por cuba, cepa (ej. Cabernet, Cuba 02)..."
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

    <!-- Cuadrícula Responsive de Tarjetas de Cubas -->
    <main class="cubas-grid" role="region" aria-label="Cuadrícula de cubas">
      <article
        v-for="cuba in filteredCubas"
        :key="cuba.id"
        class="cuba-card"
        :class="[`card-status-${cuba.estado}`]"
        @click="goToDetail(cuba.id)"
      >
        <!-- Encabezado de la Tarjeta -->
        <header class="cuba-card-header">
          <div class="cuba-ident">
            <div class="cuba-icon-avatar">
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
          <span class="cuba-phase">{{ cuba.fase }} · Día {{ cuba.dia }}</span>
        </div>

        <!-- Banner de Alerta si aplica -->
        <div v-if="cuba.alertaMsg" class="cuba-alert-banner">
          <AlertTriangle :size="14" class="alert-banner-icon" />
          <span>{{ cuba.alertaMsg }}</span>
        </div>

        <!-- Medidores Principales: Temperatura y Brix -->
        <div class="metrics-container">
          <!-- Métrica: Temperatura -->
          <div class="metric-box temp-box" :class="[`temp-${cuba.estado}`]">
            <div class="metric-header">
              <span class="metric-label">
                <Thermometer :size="14" />
                <span>Temperatura</span>
              </span>
              <span class="metric-target">Rango: {{ cuba.tempMin }}° - {{ cuba.tempMax }}°C</span>
            </div>

            <div class="metric-main-value">
              <span class="metric-digits">{{ cuba.temperatura.toFixed(1) }}</span>
              <span class="metric-unit">°C</span>

              <span
                v-if="cuba.tendenciaTemp === 'alza'"
                class="trend-tag trend-up"
                title="Tendencia al alza"
              >
                <TrendingUp :size="13" />
              </span>
              <span
                v-else-if="cuba.tendenciaTemp === 'baja'"
                class="trend-tag trend-down"
                title="Tendencia a la baja"
              >
                <TrendingDown :size="13" />
              </span>
            </div>

            <!-- Indicador gráfico de rango -->
            <div class="temp-range-bar">
              <div
                class="temp-range-marker"
                :style="{
                  left: `${Math.min(95, Math.max(5, ((cuba.temperatura - 10) / 25) * 100))}%`
                }"
              ></div>
            </div>
          </div>

          <!-- Métrica: Grados Brix -->
          <div class="metric-box brix-box">
            <div class="metric-header">
              <span class="metric-label">
                <Droplets :size="14" />
                <span>Densidad / Azúcar</span>
              </span>
              <span class="metric-target">Inicial: {{ cuba.brixInicial }} °Bx</span>
            </div>

            <div class="metric-main-value">
              <span class="metric-digits">{{ cuba.brix.toFixed(1) }}</span>
              <span class="metric-unit">°Bx</span>

              <span class="progress-percent" title="Progreso estimado de fermentación">
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
              <span>{{ ((cuba.volumenActual / cuba.volumenTotal) * 100).toFixed(0) }}% · {{ cuba.volumenActual.toLocaleString() }} L</span>
            </div>
            <div class="meta-item time">
              <Clock :size="13" />
              <span>{{ cuba.ultimaLectura }}</span>
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
    <div v-if="filteredCubas.length === 0" class="empty-state">
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
  gap: 0.45rem;
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
}
</style>
