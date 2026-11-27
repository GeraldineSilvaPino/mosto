<script setup>
/**
 * 📋 Pantalla de Detalle de Cuba y Curvas de Fermentación
 * Módulo 2: Monitoreo en Vivo (Core)
 *
 * Características implementadas:
 * 1. Consumo en paralelo mediante Promise.all de:
 *    - GET /api/cubas/{id} (información de la cuba y proceso activo)
 *    - GET /api/cubas/{id}/historico?rango_horas={24|48|168} (serie temporal)
 * 2. Alimentación directa y reactiva a Chart.js:
 *    - Eje X: data.labels (o data.timestamps)
 *    - Dataset 1: data.temp (o data.temperaturas_vino) [DS18B20]
 *    - Dataset 2: data.brix (o data.grados_brix) [MPU-6050]
 *    - Dataset 3: data.valores_ph [PH-4502C]
 * 3. Polling automático cada 5 segundos para actualizar telemetría en vivo
 *    (temperatura, brix, estado de reglas y curvas de Chart.js) sincronizado con simulate_esp.py.
 * 4. Selectores de rango temporal reactivos (24h / 48h / 7d ➔ 24, 48, 168 horas)
 *    que disparan nueva petición a la API y ejecutan chartInstance.update().
 * 5. Manejo robusto de cubas sin proceso activo o sin lecturas (estado vacío
 *    amigable sin romper la vista ni Chart.js).
 * 6. Sincronización bidireccional con Vue Router (/cubas/:id) y selector de cubas.
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
  ClipboardList,
  Info,
  RefreshCw,
  AlertCircle,
  FlaskConical,
  Play,
  Square,
  Sparkles,
  X
} from 'lucide-vue-next'

import { Chart as ChartJS, registerables } from 'chart.js'
import TankSilhouette from '../components/TankSilhouette.vue'
import cubaService from '../services/cubaService'
import { telemetryPoints } from '../utils/telemetryChart'
import alertService from '../services/alertService'
import processService from '../services/processService'
import SimulationStatus from '../components/SimulationStatus.vue'
import KineticsPanel from '../components/KineticsPanel.vue'
import InterventionsPanel from '../components/InterventionsPanel.vue'
import ManualMeasurementsPanel from '../components/ManualMeasurementsPanel.vue'

ChartJS.register(...registerables)

const route = useRoute()
const router = useRouter()

// ==========================================
// ESTADO REACTIVO PRINCIPAL
// ==========================================
const cubasDisponibles = ref([])
const cuba = ref(null)
const historico = ref(null)
const alertasCuba = ref([])
const processToolsOpen = ref(false)
const registerView = ref('measurements')
const linksRevision = ref(0)
watch(() => cuba.value?.proceso_activo_id, () => { registerView.value = 'measurements' })

function toggleProcessTools(event) {
  processToolsOpen.value = event.currentTarget.open
  if (processToolsOpen.value) registerView.value = 'measurements'
}

const loading = ref(true)
const chartLoading = ref(false)
const error = ref(null)
const flashUpdate = ref(false)

const selectedCubaId = ref(1)
const activeTimeRange = ref('24h') // '24h' | '48h' | '7d'
const activeChartTab = ref('both') // 'both' | 'temp' | 'brix' | 'ph'

const chartCanvasRef = ref(null)
let chartInstance = null
let pollInterval = null
let dataGeneration = 0
let polling = false

// ==========================================
// ESTADO DE MACHINE LEARNING & PREDICCIÓN IA
// ==========================================
const isSimulatingAnomaly = ref(false)
const isRestoringNormality = ref(false)
const iaToastMessage = ref('')

const prediccionML = computed(() => {
  return (
    cuba.value?.prediccion_ml || {
      riesgo_pct: null,
      estado_ia: 'RECOLECTANDO_DATOS',
      alerta_ia: false,
      mensaje: 'Calibrando ventana temporal (mínimo 4 lecturas)...',
      brix_suavizado: null,
      temp_suavizada: null,
      pendiente_brix_ventana: null,
      pendiente_temp_ventana: null,
      turbulencia_brix_std: null
    }
  )
})

const sinModeloValidado = computed(() => prediccionML.value.estado_ia === 'NO_VALIDADO')

const estadoLabel = computed(() => {
  const map = {
    CRITICO: 'ALTO RIESGO DE PARADA',
    ADVERTENCIA: 'DESVIACIÓN CINÉTICA',
    NORMAL: 'CINÉTICA SALUDABLE',
    FINALIZADA: 'BRIX EN TRAMO FINAL',
    RECOLECTANDO_DATOS: 'REUNIENDO LECTURAS',
    NO_VALIDADO: 'MODELO EXPERIMENTAL',
    ERROR: 'EVALUACIÓN NO DISPONIBLE'
  }
  return map[prediccionML.value?.estado_ia] || prediccionML.value?.estado_ia || 'CALIBRANDO'
})

const iaStatusClass = computed(() => {
  const estado = prediccionML.value?.estado_ia || 'RECOLECTANDO_DATOS'
  switch (estado) {
    case 'CRITICO':
      return 'ia-status--critico'
    case 'ADVERTENCIA':
      return 'ia-status--advertencia'
    case 'NORMAL':
      return 'ia-status--normal'
    case 'FINALIZADA':
      return 'ia-status--finalizada'
    default:
      return 'ia-status--calibrando'
  }
})

const iaGaugeColor = computed(() => {
  if (prediccionML.value?.riesgo_pct == null) return '#64748b'
  const pct = Number(prediccionML.value?.riesgo_pct) || 0
  if (prediccionML.value.estado_ia === 'CRITICO') return '#e8b7c3'
  if (prediccionML.value.estado_ia === 'ADVERTENCIA') return '#d5b98d'
  return '#c9b7bd'
})

const ejecutarSimularAnomalia = async () => {
  if (isSimulatingAnomaly.value) return
  try {
    isSimulatingAnomaly.value = true
    await cubaService.simularAnomalia(selectedCubaId.value)
    // Refrescar inmediatamente datos de la cuba y gráfico
    await cargarDatosCuba(selectedCubaId.value, rangoToHoras(activeTimeRange.value))
    iaToastMessage.value = 'Escenario demo cargado. La evaluación se muestra con las nuevas lecturas.'
    setTimeout(() => {
      iaToastMessage.value = ''
    }, 5000)
  } catch (err) {
    iaToastMessage.value = err.message || 'No se pudo cargar el escenario.'
  } finally {
    isSimulatingAnomaly.value = false
  }
}

const ejecutarRestaurarNormalidad = async () => {
  if (isRestoringNormality.value) return
  try {
    isRestoringNormality.value = true
    await cubaService.restaurarNormalidad(selectedCubaId.value)
    await cargarDatosCuba(selectedCubaId.value, rangoToHoras(activeTimeRange.value))
    iaToastMessage.value = 'Cinética saludable restablecida con éxito.'
    setTimeout(() => {
      iaToastMessage.value = ''
    }, 5000)
  } catch (err) {
    iaToastMessage.value = err.message || 'No se pudo restaurar el escenario.'
  } finally {
    isRestoringNormality.value = false
  }
}

// ==========================================
// UTILITARIOS Y MAPEO DE TIEMPO
// ==========================================
function rangoToHoras(rango) {
  switch (rango) {
    case '1h':
      return 1
    case '48h':
      return 48
    case '7d':
      return 168
    case '24h':
    default:
      return 24
  }
}

const activeTimeRangeLabel = computed(() => {
  switch (activeTimeRange.value) {
    case '1h':
      return '1 h'
    case '48h':
      return '48 h'
    case '7d':
      return '7 días'
    case '24h':
    default:
      return '24 h'
  }
})

// ==========================================
// PROPIEDADES COMPUTADAS Y VALORES EN TIEMPO REAL
// ==========================================
const tieneProcesoActivo = computed(() => {
  return Boolean(cuba.value && cuba.value.proceso_activo_id)
})

const estaDisponible = computed(() => {
  if (!cuba.value) return false
  const estado = String(cuba.value.estado_operativo || '').toLowerCase()
  return (estado === 'disponible' || estado === '') && !cuba.value.proceso_activo_id
})

const capacidadMaximaLitros = computed(() => {
  return cuba.value?.capacidad_lts ? Number(cuba.value.capacidad_lts) : 10000
})

const nivelRegistrado = computed(() => {
  const volumen = cuba.value?.volumen_actual_lts
  const capacidad = cuba.value?.capacidad_lts
  return Number.isFinite(volumen) && volumen >= 0 && capacidad > 0
    ? Math.round(volumen * 100 / capacidad) : null
})
const formatoLectura = (valor, decimales = 1) => valor == null ? '—'
  : valor.toLocaleString('es-CL', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })

const tieneLecturas = computed(() => {
  if (!historico.value) return false
  const series = activeChartTab.value === 'ph' ? ['valores_ph'] : activeChartTab.value === 'temp'
    ? ['temperaturas_vino'] : activeChartTab.value === 'brix' ? ['grados_brix'] : ['temperaturas_vino', 'grados_brix']
  return historico.value.timestamps?.some((_, index) => {
    const origin = historico.value.origenes?.[index]
    return (scenarioNames[origin] ? origin : 'telemetria') === selectedSource.value &&
      series.some(key => Number.isFinite(historico.value[key]?.[index]))
  })
})

// Extracción unificada y reactiva de la temperatura actual
const temperaturaActual = computed(() => {
  if (cuba.value?.ultima_temperatura !== null && cuba.value?.ultima_temperatura !== undefined) {
    return Number(cuba.value.ultima_temperatura)
  }
  if (cuba.value?.temperatura !== null && cuba.value?.temperatura !== undefined) {
    return Number(cuba.value.temperatura)
  }
  if (cuba.value?.temperature !== null && cuba.value?.temperature !== undefined) {
    return Number(cuba.value.temperature)
  }
  if (cuba.value?.temp_mosto !== null && cuba.value?.temp_mosto !== undefined) {
    return Number(cuba.value.temp_mosto)
  }
  // Fallback a la lectura más reciente devuelta por la serie histórica
  const temps = historico.value?.temp || historico.value?.temperaturas_vino || []
  for (let i = temps.length - 1; i >= 0; i--) {
    if (temps[i] !== null && temps[i] !== undefined) {
      return Number(temps[i])
    }
  }
  return null
})

// Extracción unificada y reactiva de los grados Brix actuales
const brixActual = computed(() => {
  if (cuba.value?.ultimos_brix !== null && cuba.value?.ultimos_brix !== undefined) {
    return Number(cuba.value.ultimos_brix)
  }
  if (cuba.value?.brix !== null && cuba.value?.brix !== undefined) {
    return Number(cuba.value.brix)
  }
  if (cuba.value?.grados_brix !== null && cuba.value?.grados_brix !== undefined) {
    return Number(cuba.value.grados_brix)
  }
  // Fallback a la lectura más reciente de la serie histórica
  const brixs = historico.value?.brix || historico.value?.grados_brix || []
  for (let i = brixs.length - 1; i >= 0; i--) {
    if (brixs[i] !== null && brixs[i] !== undefined) {
      return Number(brixs[i])
    }
  }
  return null
})

const cubasList = computed(() => {
  if (cubasDisponibles.value && cubasDisponibles.value.length > 0) {
    return cubasDisponibles.value
  }
  if (cuba.value) {
    return [cuba.value]
  }
  return []
})

const cubaNombre = computed(() => {
  if (cuba.value) {
    return cuba.value.nombre || `Cuba ${cuba.value.codigo_cuba || ''}`
  }
  return `Cuba #${selectedCubaId.value}`
})

const cubaVariedad = computed(() => {
  if (!cuba.value) return '--'
  if (!tieneProcesoActivo.value) return 'Sin proceso activo'
  return cuba.value.variedad || 'Sin variedad'
})

const cubaLote = computed(() => {
  if (!cuba.value) return '--'
  if (!tieneProcesoActivo.value) return 'Cuba Disponible'
  return cuba.value.lote || 'Sin lote'
})

const diaFermentacion = computed(() => {
  if (!tieneProcesoActivo.value) return null
  return cuba.value?.dia_fermentacion || 1
})

const diasEstimados = computed(() => {
  return cuba.value?.dias_estimados || 14
})

const statusOperativo = computed(() => {
  if (!cuba.value) return 'loading'
  if (!tieneProcesoActivo.value) return 'disponible'

  const temp = temperaturaActual.value
  const min = cuba.value.temp_min_perfil
  const max = cuba.value.temp_max_perfil

  if (temp != null && min != null && max != null && (temp < min || temp > max)) {
    return 'warning'
  }
  if (temp == null || cuba.value.temp_min_perfil == null || cuba.value.temp_max_perfil == null) return 'no_evaluado'
  return 'optimal'
})

const statusLabel = computed(() => {
  switch (statusOperativo.value) {
    case 'disponible':
      return 'Disponible · Sin Fermentación Activa'
    case 'warning':
      return 'Alerta · Desviación de Parámetros'
    case 'optimal':
      return 'Temperatura en rango'
    case 'no_evaluado':
      return 'Monitoreo · Diagnóstico pendiente'
    default:
      return 'Monitoreo en Curso'
  }
})

const alertReason = computed(() => {
  if (!tieneProcesoActivo.value || !cuba.value) return null
  const temp = temperaturaActual.value
  const min = cuba.value.temp_min_perfil
  const max = cuba.value.temp_max_perfil

  if (temp != null && min != null && max != null) {
    if (temp > max) {
      return `Alerta Térmica: La temperatura actual (${temp.toFixed(1)}°C) supera el límite superior óptimo (${max.toFixed(1)}°C). Riesgo de estrés térmico en levaduras.`
    }
    if (temp < min) {
      return `Alerta Térmica: La temperatura actual (${temp.toFixed(1)}°C) se encuentra bajo el límite inferior óptimo (${min.toFixed(1)}°C). Riesgo de parada o aletargamiento.`
    }
  }
  return null
})

// Tendencia térmica dinámica calculada a partir de las últimas lecturas
const tempTrend = computed(() => {
  const temps = historico.value?.temp || historico.value?.temperaturas_vino || []
  if (temps.length >= 2) {
    const valid = temps.filter((t) => t !== null && t !== undefined)
    if (valid.length >= 2) {
      const last = valid[valid.length - 1]
      const prev = valid[Math.max(0, valid.length - 3)]
      const diff = last - prev
      if (diff > 0.05) return 'up'
      if (diff < -0.05) return 'down'
    }
  }
  return 'stable'
})

const variacion = new Intl.NumberFormat('es-CL', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })
const tempChangeText = computed(() => {
  const temps = historico.value?.temp || historico.value?.temperaturas_vino || []
  if (temps.length >= 2) {
    const valid = temps.filter((t) => t !== null && t !== undefined)
    if (valid.length >= 2) {
      const last = valid[valid.length - 1]
      const prev = valid[Math.max(0, valid.length - 3)]
      const diff = last - prev
      return `${variacion.format(diff)} °C en últimas lecturas`
    }
  }
  return 'Sin muestras suficientes'
})

const brixDeltaText = computed(() => {
  const brixs = historico.value?.brix || historico.value?.grados_brix || []
  if (brixs.length >= 2) {
    const valid = brixs.filter((b) => b !== null && b !== undefined)
    if (valid.length >= 2) {
      const diff = valid[valid.length - 1] - valid[0]
      return `${variacion.format(diff)} °Bx entre muestras disponibles`
    }
  }
  return 'Sin muestras suficientes'
})


const alertsList = computed(() => {
  if (alertasCuba.value && alertasCuba.value.length > 0) {
    return alertasCuba.value.map((a) => ({
      id: a.id,
      time: a.timestamp
        ? new Date(a.timestamp).toLocaleString('es-CL', {
            hour: '2-digit',
            minute: '2-digit',
            day: '2-digit',
            month: '2-digit'
          })
        : 'Reciente',
      text:
        a.mensaje ||
        `${(a.tipo_alerta || 'alerta').replace('_', ' ').toUpperCase()} (${a.severidad || 'media'}): Incidencia detectada en la cuba`,
      type: a.severidad === 'critica' || a.severidad === 'alta' ? 'warning' : 'normal'
    }))
  }

  if (tieneProcesoActivo.value && temperaturaActual.value !== null) {
    return [
      {
        id: 'telemetry-ok',
        time: cuba.value?.ultima_lectura_timestamp
          ? new Date(cuba.value.ultima_lectura_timestamp).toLocaleTimeString('es-CL', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit'
            })
          : 'En vivo',
        text: `Lectura telemétrica actual: ${temperaturaActual.value.toFixed(1)}°C${
          brixActual.value !== null ? ` y ${brixActual.value.toFixed(1)} °Bx.` : '.'
        }`,
        type: 'normal'
      }
    ]
  }

  return []
})

// ==========================================
// CONFIGURACIÓN Y DATASETS DE CHART.JS
// ==========================================
const scenarioNames = {
  simulacion_anomalia_ia: 'Ensayo de desviación',
  restauracion_normalidad: 'Ensayo de recuperación'
}
const chartSource = ref('telemetria')
const scenarioSources = computed(() => [...new Set(historico.value?.origenes || [])].filter(key => scenarioNames[key]))
const selectedSource = computed(() => scenarioSources.value.includes(chartSource.value) ? chartSource.value : 'telemetria')

function chartPoints(data, values) {
  const times = []
  const readings = []
  for (const [i, time] of (data?.timestamps || []).entries()) {
    const origin = data.origenes?.[i]
    const source = scenarioNames[origin] ? origin : 'telemetria'
    if (source === selectedSource.value) {
      times.push(time)
      readings.push(values[i])
    }
  }
  return telemetryPoints(times, readings)
}

watch(chartSource, () => {
  if (chartInstance && historico.value) actualizarGraficoEnInstancia(historico.value, 'none')
})

function construirDatasets(data) {
  if (!chartCanvasRef.value) return []
  const labels =
    data?.labels && data.labels.length > 0
      ? data.labels
      : data?.timestamps || []

  // Dataset 1 (Temperatura): data.temp o data.temperaturas_vino
  const tempData =
    data?.temp && data.temp.length > 0
      ? data.temp
      : data?.temperaturas_vino || []

  // Dataset 2 (Brix / Densidad): data.brix o data.grados_brix
  const brixData =
    data?.brix && data.brix.length > 0
      ? data.brix
      : data?.grados_brix || []

  // Dataset 3 (pH): data.valores_ph
  const phData = data?.valores_ph || []

  const isDense = labels.length > 35
  const datasets = []

  if (activeChartTab.value === 'both' || activeChartTab.value === 'temp') {
    datasets.push({
      label: 'Temperatura (°C)',
      data: chartPoints(data, tempData),
      borderColor: '#761F33',
      backgroundColor: '#761F33',
      borderWidth: 1.8,
      tension: 0,
      stepped: false,
      spanGaps: false,
      pointRadius: isDense ? 0 : 3,
      pointHoverRadius: 6,
      pointBackgroundColor: '#FFFFFF',
      pointBorderColor: '#761F33',
      pointBorderWidth: 2,
      fill: false,
      yAxisID: 'yTemp'
    })
  }

  if (activeChartTab.value === 'both' || activeChartTab.value === 'brix') {
    datasets.push({
      label: 'Brix aparente (°Bx)',
      data: chartPoints(data, brixData),
      borderColor: '#C47F17',
      backgroundColor: '#C47F17',
      borderWidth: 1.8,
      borderDash: [5, 4],
      tension: 0,
      stepped: false,
      spanGaps: false,
      pointRadius: isDense ? 0 : 3,
      pointHoverRadius: 6,
      pointBackgroundColor: '#FFFFFF',
      pointBorderColor: '#C47F17',
      pointBorderWidth: 2,
      fill: false,
      yAxisID: activeChartTab.value === 'both' ? 'yBrix' : 'yTemp'
    })
  }

  if (activeChartTab.value === 'ph') {
    datasets.push({
      label: 'pH',
      data: chartPoints(data, phData),
      borderColor: '#6B21A8',
      backgroundColor: '#6B21A8',
      borderWidth: 1.8,
      tension: 0,
      stepped: false,
      spanGaps: false,
      pointRadius: isDense ? 0 : 3,
      pointHoverRadius: 6,
      pointBackgroundColor: '#FFFFFF',
      pointBorderColor: '#6B21A8',
      pointBorderWidth: 2,
      fill: false,
      yAxisID: 'yTemp'
    })
  }

  return datasets
}

function construirScalesConfig() {
  const isBoth = activeChartTab.value === 'both'
  const isBrix = activeChartTab.value === 'brix'
  const isPh = activeChartTab.value === 'ph'

  const scales = {
    x: {
      type: 'linear',
      bounds: 'data',
      grid: { color: 'rgba(232, 224, 221, 0.6)' },
      ticks: {
        color: '#66525B',
        font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
        maxRotation: 45,
        autoSkip: true,
        maxTicksLimit: 7,
        callback: value => new Date(value).toLocaleString('es-CL', ['1h', '24h'].includes(activeTimeRange.value) ? { hour: '2-digit', minute: '2-digit' } : { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
      }
    },
    yTemp: {
      type: 'linear',
      position: 'left',
      ...(isBrix ? { suggestedMin: 0, suggestedMax: 25 } : isPh ? { suggestedMin: 3, suggestedMax: 4 } : { suggestedMin: 18, suggestedMax: 26 }),
      title: {
        display: true,
        text: isBrix ? 'Grados Brix (°Bx)' : isPh ? 'pH Enológico' : 'Temperatura (°C)',
        color: isBrix ? '#C47F17' : isPh ? '#6B21A8' : '#761F33',
        font: { family: "'Plus Jakarta Sans', sans-serif", size: 12, weight: '600' }
      },
      grid: { color: 'rgba(232, 224, 221, 0.5)' },
      ticks: {
        color: isBrix ? '#C47F17' : isPh ? '#6B21A8' : '#761F33',
        font: { family: "'JetBrains Mono', monospace", size: 11 }
      }
    }
  }

  if (isBoth) {
    scales.yBrix = {
      type: 'linear',
      position: 'right',
      suggestedMin: 0,
      suggestedMax: 25,
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

  return scales
}

async function renderChart() {
  await nextTick()
  if (!chartCanvasRef.value) return

  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }

  const data = historico.value || {}
  const labels =
    data.labels && data.labels.length > 0
      ? data.labels
      : data.timestamps || []

  const datasets = construirDatasets(data)
  const scalesConfig = construirScalesConfig()
  const ctx = chartCanvasRef.value.getContext('2d')

  chartInstance = new ChartJS(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 400
      },
      interaction: {
        intersect: false,
        mode: 'index'
      },
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
          titleFont: { size: 12, weight: 'bold' },
          callbacks: { title: items => items.length ? new Date(items[0].parsed.x).toLocaleString('es-CL') : '' }
        }
      },
      scales: scalesConfig
    }
  })
}

/**
 * Actualiza la instancia activa de Chart.js inyectando los arrays del backend
 * Eje X: data.labels (horas formateadas)
 * Dataset 1 (Temperatura): data.temp o data.temperaturas_vino
 * Dataset 2 (Brix / Densidad): data.brix o data.grados_brix
 */
function actualizarGraficoEnInstancia(data, updateMode = 'default') {
  if (!chartInstance) {
    renderChart()
    return
  }

  chartInstance.data.datasets = construirDatasets(data)

  chartInstance.options.scales = construirScalesConfig()

  if (updateMode === 'none') {
    chartInstance.update('none')
  } else {
    chartInstance.update()
  }
}

// ==========================================
// CAMBIO DE RANGO TEMPORAL (CRITERIO 4)
// ==========================================
async function cambiarRangoHoras(nuevoRango) {
  const request = ++dataGeneration
  activeTimeRange.value = nuevoRango
  const horas = rangoToHoras(nuevoRango)
  chartLoading.value = true

  try {
    // Dispara nueva petición cambiando rango_horas y actualiza cuba en paralelo
    const [cubaData, historicoData] = await Promise.all([
      cubaService.obtenerCuba(selectedCubaId.value),
      cubaService.obtenerHistorico(selectedCubaId.value, horas)
    ])

    if (request !== dataGeneration) return
    cuba.value = cubaData
    historico.value = historicoData

    await nextTick()
    if (!chartInstance) {
      await renderChart()
    } else {
      // Ejecuta chartInstance.update() según Criterio de Aceptación 4
      actualizarGraficoEnInstancia(historicoData)
    }
  } catch (err) {
    console.error('Error al actualizar histórico de la cuba:', err)
  } finally {
    if (request === dataGeneration) chartLoading.value = false
  }
}

function cambiarTabGrafico(tab) {
  activeChartTab.value = tab
  if (chartInstance && historico.value) {
    actualizarGraficoEnInstancia(historico.value)
  }
}

// ==========================================
// POLLING EN TIEMPO REAL (SINCRONIZACIÓN CONTINUA)
// ==========================================
async function refrescarDatosEnVivo() {
  if (polling || loading.value || chartLoading.value || !selectedCubaId.value) return

  const request = dataGeneration
  const id = selectedCubaId.value
  polling = true
  try {
    const horas = rangoToHoras(activeTimeRange.value)
    const [cubaData, historicoData] = await Promise.all([
      cubaService.obtenerCuba(selectedCubaId.value),
      cubaService.obtenerHistorico(selectedCubaId.value, horas)
    ])

    if (request !== dataGeneration || id !== selectedCubaId.value) return
    const prevTemp = temperaturaActual.value
    const prevBrix = brixActual.value

    cuba.value = cubaData
    historico.value = historicoData

    const newTemp = temperaturaActual.value
    const newBrix = brixActual.value

    if (prevTemp !== newTemp || prevBrix !== newBrix) {
      flashUpdate.value = true
      setTimeout(() => {
        flashUpdate.value = false
      }, 1200)
    }

    // Actualiza Chart.js con la nueva lectura sin parpadeo de animación
    actualizarGraficoEnInstancia(historicoData, 'none')
  } catch (err) {
    console.warn('Fallo silencioso en polling de telemetría de cuba:', err)
  } finally { polling = false }
}

// ==========================================
// CARGA DE DATOS EN PARALELO (CRITERIO 2)
// ==========================================
async function cargarAlertasCuba(id) {
  try {
    const data = await alertService.listarAlertas({ cuba_id: id, limit: 10 })
    if (Number(id) !== Number(selectedCubaId.value)) return
    alertasCuba.value = Array.isArray(data) ? data : data?.alertas || []
  } catch (err) {
    console.warn('No se pudieron cargar alertas de la cuba:', err)
    alertasCuba.value = []
  }
}

async function cargarDatosCuba(id, rangoHoras = 24) {
  const request = ++dataGeneration
  loading.value = true
  chartLoading.value = false
  error.value = null

  try {
    // Invocación en paralelo con Promise.all según Criterio de Aceptación 2
    const [cubaData, historicoData] = await Promise.all([
      cubaService.obtenerCuba(id),
      cubaService.obtenerHistorico(id, rangoHoras)
    ])

    if (request !== dataGeneration) return
    cuba.value = cubaData
    historico.value = historicoData

    // Cargar alertas asociadas de forma asíncrona
    cargarAlertasCuba(id)

    loading.value = false
    await nextTick()
    await renderChart()
  } catch (err) {
    console.error('Error al cargar datos de la cuba:', err)
    if (request !== dataGeneration) return
    error.value = err.message || 'Error de comunicación al consultar los datos de la cuba'
  } finally {
    if (request === dataGeneration) loading.value = false
  }
}

async function cargarListaCubas() {
  try {
    const lista = await cubaService.listarCubas({ incluirPrediccion: false })
    if (Array.isArray(lista) && lista.length > 0) {
      cubasDisponibles.value = lista
    }
  } catch (err) {
    console.warn('No se pudo listar cubas para el selector:', err)
  }
}

async function inicializarVista() {
  const rawId = route.params.id || route.query.id
  const lista = cargarListaCubas()
  const idRuta = Number(rawId)
  if (Number.isSafeInteger(idRuta) && idRuta > 0) {
    selectedCubaId.value = idRuta
    await Promise.all([lista, cargarDatosCuba(idRuta, rangoToHoras(activeTimeRange.value))])
    return
  }
  await lista
  if (rawId !== (route.params.id || route.query.id)) return
  let idNumerico = null

  if (rawId) {
    const match = cubasDisponibles.value.find(
      (c) =>
        String(c.id) === String(rawId) ||
        (c.codigo_cuba && c.codigo_cuba.toLowerCase() === String(rawId).toLowerCase())
    )
    if (match) {
      idNumerico = match.id
    } else if (!isNaN(Number(rawId))) {
      idNumerico = Number(rawId)
    }
  }

  if (!idNumerico) {
    if (cubasDisponibles.value.length > 0) {
      idNumerico = cubasDisponibles.value[0].id
    } else {
      idNumerico = 1
    }
  }

  selectedCubaId.value = idNumerico
  const horas = rangoToHoras(activeTimeRange.value)
  await cargarDatosCuba(idNumerico, horas)
}

async function onCubaChange(e) {
  const newId = Number(e.target.value) || e.target.value
  selectedCubaId.value = newId
  router.replace({ path: `/cubas/${newId}` })
  const horas = rangoToHoras(activeTimeRange.value)
  await cargarDatosCuba(newId, horas)
}

// ==========================================
// CICLO DE VIDA Y WATCHERS
// ==========================================
onMounted(() => {
  inicializarVista()

  // Polling cada 5 segundos para actualización continua en tiempo real
  pollInterval = setInterval(refrescarDatosEnVivo, 5000)
})

watch(
  () => route.params.id,
  async (newId) => {
    if (newId && String(newId) !== String(selectedCubaId.value)) {
      let idNumerico = Number(newId)
      if (isNaN(idNumerico)) {
        const match = cubasDisponibles.value.find(
          (c) => c.codigo_cuba && c.codigo_cuba.toLowerCase() === String(newId).toLowerCase()
        )
        if (match) idNumerico = match.id
      }
      if (idNumerico) {
        selectedCubaId.value = idNumerico
        const horas = rangoToHoras(activeTimeRange.value)
        await cargarDatosCuba(idNumerico, horas)
      }
    }
  }
)

// ==========================================
// CICLO DE VIDA DE PROCESOS (INICIAR / FINALIZAR)
// ==========================================
const isStartModalOpen = ref(false)
const startFormSubmitting = ref(false)
const startFormError = ref(null)
const startForm = ref({
  volumen_litros: '',
  brix_inicial: 24.5,
  brix_objetivo: 1.0,
  dias_estimados: 14,
  densidad_inicial_sg: 1.1000
})

const isFinishModalOpen = ref(false)
const finishFormSubmitting = ref(false)
const finishFormError = ref(null)
const finishForm = ref({
  densidad_final_sg: '',
  brix_final: '',
  observaciones: ''
})

const toastMessage = ref('')
const toastType = ref('success') // 'success' | 'error' | 'warning' | 'info'
let toastTimeout = null

function showToast(message, type = 'success') {
  toastMessage.value = message
  toastType.value = type
  if (toastTimeout) clearTimeout(toastTimeout)
  toastTimeout = setTimeout(() => {
    toastMessage.value = ''
  }, 4000)
}

function abrirModalIniciar() {
  if (!estaDisponible.value) {
    showToast(`La cuba ${cubaNombre.value} no está en estado "disponible".`, 'warning')
    return
  }
  startFormError.value = null
  const cap = capacidadMaximaLitros.value
  const sugerido = Math.round(cap * 0.8)
  startForm.value = {
    volumen_litros: sugerido,
    brix_inicial: 24.5,
    brix_objetivo: 1.0,
    dias_estimados: 14,
    densidad_inicial_sg: 1.1000
  }
  isStartModalOpen.value = true
}

function cerrarModalIniciar() {
  isStartModalOpen.value = false
  startFormError.value = null
}

async function ejecutarIniciarProceso() {
  if (!estaDisponible.value) {
    startFormError.value = 'La cuba no está disponible para iniciar una fermentación.'
    return
  }

  const vol = Number(startForm.value.volumen_litros)
  if (!vol || vol <= 0) {
    startFormError.value = 'Debe ingresar un volumen en litros válido y mayor a 0.'
    return
  }

  const capMax = capacidadMaximaLitros.value
  if (vol > capMax) {
    startFormError.value = `El volumen ingresado (${vol} L) supera la capacidad máxima de la cuba (${capMax} L).`
    return
  }

  startFormSubmitting.value = true
  startFormError.value = null

  try {
    const payload = {
      cuba_id: selectedCubaId.value,
      volumen_litros: vol,
      brix_inicial: Number(startForm.value.brix_inicial),
      brix_objetivo: Number(startForm.value.brix_objetivo),
      dias_estimados: Number(startForm.value.dias_estimados),
      densidad_inicial_sg: Number(startForm.value.densidad_inicial_sg) || 1.1000
    }

    await processService.iniciar(payload)

    cerrarModalIniciar()
    showToast(`¡Fermentación iniciada exitosamente! Cuba ${cuba.value?.codigo_cuba || selectedCubaId.value} ahora está en proceso.`, 'success')

    // Refrescar los datos de la cuba y lista de cubas
    await Promise.all([
      cargarDatosCuba(selectedCubaId.value, rangoToHoras(activeTimeRange.value)),
      cargarListaCubas()
    ])
  } catch (err) {
    const msg = err.message || 'Error al iniciar el proceso de fermentación'
    startFormError.value = msg
    showToast(msg, 'error')
  } finally {
    startFormSubmitting.value = false
  }
}

function abrirModalFinalizar() {
  if (!tieneProcesoActivo.value) {
    showToast('Esta cuba no cuenta con un proceso de fermentación activo para finalizar.', 'warning')
    return
  }
  finishFormError.value = null
  finishForm.value = {
    densidad_final_sg:
      cuba.value?.densidad_final_sg ||
      (brixActual.value !== null ? Number((0.998 + (brixActual.value * 0.0038)).toFixed(4)) : 0.9940),
    brix_final: brixActual.value !== null ? Number(brixActual.value.toFixed(1)) : 1.0,
    observaciones: 'Fermentación alcohólica completada dentro de los parámetros esperados. Proceder a descube y clarificación.'
  }
  isFinishModalOpen.value = true
}

function cerrarModalFinalizar() {
  isFinishModalOpen.value = false
  finishFormError.value = null
}

async function ejecutarFinalizarProceso() {
  const procesoId = cuba.value?.proceso_activo_id
  if (!procesoId) {
    finishFormError.value = 'No se encontró el ID del proceso activo a finalizar.'
    return
  }

  finishFormSubmitting.value = true
  finishFormError.value = null

  try {
    const payload = {
      densidad_final_sg: finishForm.value.densidad_final_sg !== '' ? Number(finishForm.value.densidad_final_sg) : undefined,
      brix_final: finishForm.value.brix_final !== '' ? Number(finishForm.value.brix_final) : undefined,
      motivo: finishForm.value.observaciones || undefined,
      observaciones: finishForm.value.observaciones || undefined
    }

    await processService.finalizar(procesoId, payload)

    cerrarModalFinalizar()
    showToast(`¡Proceso #${procesoId} finalizado exitosamente! Cuba liberada y en estado "disponible".`, 'success')

    // Refrescar los datos de la cuba y lista de cubas
    await Promise.all([
      cargarDatosCuba(selectedCubaId.value, rangoToHoras(activeTimeRange.value)),
      cargarListaCubas()
    ])
  } catch (err) {
    const msg = err.message || 'Error al finalizar el proceso de fermentación'
    finishFormError.value = msg
    showToast(msg, 'error')
  } finally {
    finishFormSubmitting.value = false
  }
}

onBeforeUnmount(() => {
  dataGeneration++
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }
  if (toastTimeout) {
    clearTimeout(toastTimeout)
    toastTimeout = null
  }
})
</script>

<template>
  <!-- Estado de Carga Inicial -->
  <div v-if="loading && !cuba" class="view-loading-state">
    <RefreshCw class="spin" :size="36" />
    <p>Cargando información y curvas de fermentación...</p>
  </div>

  <!-- Estado de Error Inicial -->
  <div v-else-if="error && !cuba" class="view-error-state">
    <AlertCircle :size="40" class="error-icon" />
    <h3>No se pudo cargar la cuba</h3>
    <p>{{ error }}</p>
    <button
      class="btn-retry"
      @click="cargarDatosCuba(selectedCubaId, rangoToHoras(activeTimeRange))"
    >
      <RefreshCw :size="16" />
      <span>Reintentar</span>
    </button>
  </div>

  <!-- Vista Principal de Detalle -->
  <div v-else class="view-container cuba-detail-view">
    <!-- Encabezado con selector de cuba -->
    <header class="detail-header">
      <div class="header-left">
        <router-link to="/" class="back-link">
          <ArrowLeft :size="16" />
          <span>Volver al atlas</span>
        </router-link>

        <div class="title-selector-row">
          <div>
            <h1 class="sr-only">{{ cubaNombre }}</h1>
            <div class="selector-wrapper">
              <select
                :value="selectedCubaId"
                @change="onCubaChange"
                aria-label="Seleccionar cuba"
                class="cuba-select"
              >
                <option v-for="c in cubasList" :key="c.id" :value="c.id">
                  {{ c.nombre || `Cuba ${c.codigo_cuba || c.codigo || c.id}` }}
                </option>
              </select>
              <ChevronDown :size="18" class="select-chevron" />
            </div>
            <p class="cuba-subtitle">
              {{ cubaVariedad }} · {{ cubaLote }}
            </p>
          </div>
        </div>
      </div>

      <!-- Estado en base a reglas y sincronización en vivo -->
      <div class="header-right">
        <div class="header-actions-row">
          <!-- Botón Iniciar Fermentación (Habilitado solo si cuba está 'disponible') -->
          <button
            v-if="!tieneProcesoActivo"
            class="btn-lifecycle btn-lifecycle--start"
            :disabled="!estaDisponible"
            :title="estaDisponible ? 'Iniciar un nuevo ciclo de vendimia en esta cuba' : 'Esta cuba no está en estado disponible para iniciar una fermentación'"
            @click="abrirModalIniciar"
          >
            <Play :size="14" />
            <span>Iniciar Fermentación</span>
          </button>

          <!-- Botón Finalizar Fermentación (Disponible cuando hay proceso activo) -->
          <button
            v-if="tieneProcesoActivo"
            class="btn-lifecycle btn-lifecycle--finish"
            @click="abrirModalFinalizar"
            title="Finalizar proceso activo y liberar la cuba"
          >
            <Square :size="13" />
            <span>Finalizar Fermentación</span>
          </button>



          <button
            class="btn-refresh"
            :disabled="loading || chartLoading"
            @click="cargarDatosCuba(selectedCubaId, rangoToHoras(activeTimeRange))"
            title="Actualizar datos y telemetría"
          >
            <RefreshCw :size="15" :class="{ spin: loading || chartLoading }" />
            <span>Actualizar</span>
          </button>


        </div>

        <div class="days-tracker">
          <div
            class="status-pill"
            :class="{
              'status-pill--optimal': statusOperativo === 'optimal',
              'status-pill--warning': statusOperativo === 'warning',
              'status-pill--neutral': statusOperativo === 'disponible' || statusOperativo === 'loading'
            }"
          >
            <span class="status-dot"></span>
            <span>{{ statusLabel }}</span>
          </div>
          <span v-if="tieneProcesoActivo">
            Día {{ diaFermentacion }} de aprox. {{ diasEstimados }} días
          </span>
          <span v-else class="days-tracker--empty">
            Sin proceso activo en curso
          </span>
        </div>
      </div>
    </header>

    <!-- Alerta destacada si se rompen las reglas de fermentación -->
    <div v-if="alertReason" class="alert-box">
      <div class="alert-box-icon">
        <AlertTriangle :size="22" />
      </div>
      <div class="alert-box-content">
        <h4>Temperatura fuera del perfil</h4>
        <p>{{ alertReason }}</p>
      </div>
    </div>

    <!-- Paneles de métricas de telemetría IoT -->
    <section class="telemetry-spread" aria-label="Ficha y lecturas de la cuba">
      <figure class="vessel-profile">
        <TankSilhouette v-if="cuba" :id="'detail-' + cuba.id" :nivel="nivelRegistrado" />
        <figcaption>
          <h2>Ocupación de la cuba</h2>
          <strong>{{ nivelRegistrado == null ? '—' : nivelRegistrado + ' %' }}</strong>
          <span v-if="nivelRegistrado != null">{{ cuba.volumen_actual_lts.toLocaleString('es-CL') }} de {{ cuba.capacidad_lts.toLocaleString('es-CL') }} L</span>
          <span v-else>Nivel sin datos</span>
        </figcaption>
      </figure>
      <div class="readings">
        <h2>Lecturas del mosto</h2>
        <div class="metrics-grid">
      <!-- 1. Sensor DS18B20: Temperatura -->
      <div class="metric-card" :class="{ 'card-flash': flashUpdate }">
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
          <span class="metric-number">
            {{ formatoLectura(temperaturaActual) }}
          </span>
          <span class="metric-unit">°C</span>
        </div>

        <div class="metric-details">
          <div
            v-if="tieneProcesoActivo && temperaturaActual !== null"
            class="trend-tag"
            :class="tempTrend === 'up' ? 'trend-up' : tempTrend === 'down' ? 'trend-down' : 'trend-stable'"
          >
            <component
              :is="tempTrend === 'up' ? TrendingUp : tempTrend === 'down' ? TrendingDown : Activity"
              :size="14"
            />
            <span>{{ tempChangeText }}</span>
          </div>
          <span v-else class="metric-subtext">Sin lecturas registradas</span>

          <span class="metric-subtext">
            Banda óptima:
            {{
              cuba?.temp_min_perfil !== null && cuba?.temp_min_perfil !== undefined
                ? `${cuba.temp_min_perfil}°C a ${cuba.temp_max_perfil}°C`
                : 'Sin banda registrada'
            }}
          </span>
        </div>
      </div>

      <!-- 2. Sensor MPU-6050: Inclinación y Brix -->
      <div class="metric-card" :class="{ 'card-flash': flashUpdate }">
        <div class="metric-card-top">
          <div>
            <span class="sensor-tag">Sensor MPU-6050</span>
            <h3 class="metric-title">Brix aparente</h3>
          </div>
          <div class="metric-icon metric-icon-brix">
            <Compass :size="22" />
          </div>
        </div>

        <div class="metric-val-group">
          <span class="metric-number">
            {{ formatoLectura(brixActual) }}
          </span>
          <span class="metric-unit">°Bx</span>
        </div>

        <div class="metric-details">
          <span class="metric-subtext">Variación: {{ brixDeltaText }}</span>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-card-top">
          <div>
            <span class="sensor-tag">Sensor PH-4502C</span>
            <h3 class="metric-title">Acidez del mosto</h3>
          </div>
          <div class="metric-icon metric-icon-ph"><FlaskConical :size="22" /></div>
        </div>
        <div class="metric-val-group">
          <span class="metric-number">{{ formatoLectura(cuba?.ultimo_ph, 2) }}</span>
          <span class="metric-unit">pH</span>
        </div>
        <div class="metric-details">
          <span class="metric-subtext" v-if="cuba?.ultima_lectura_timestamp">Última lectura · {{ new Date(cuba.ultima_lectura_timestamp).toLocaleTimeString('es-CL') }}</span>
          <span class="metric-subtext" v-else>Sin lecturas registradas</span>
        </div>
      </div>
        </div>
      </div>
    </section>

    <nav class="detail-index" aria-label="Secciones de la ficha">
      <a href="#curvas">Curvas de fermentación</a>
      <a v-if="tieneProcesoActivo" href="#riesgo-parada">Riesgo de parada</a>
      <a href="#eventos">Lecturas y alertas</a>
    </nav>
    <!-- Gráficos de Telemetría Chart.js -->
    <section class="chart-section" id="curvas">
      <div class="chart-header">
        <div>
          <h2 class="chart-main-title">Evolución de la cuba</h2>
          <p class="chart-main-subtitle">
            Hora local
          </p>
        </div>

        <div class="chart-controls">
          <select v-if="scenarioSources.length" v-model="chartSource" aria-label="Origen de las lecturas" class="chart-source">
            <option value="telemetria">Telemetría continua</option>
            <option v-for="source in scenarioSources" :key="source" :value="source">{{ scenarioNames[source] }}</option>
          </select>
          <!-- Filtro de series -->
          <div class="btn-group">
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'both' }"
              @click="cambiarTabGrafico('both')"
            >
              Temp. y Brix
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'temp' }"
              @click="cambiarTabGrafico('temp')"
            >
              Temperatura
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'brix' }"
              @click="cambiarTabGrafico('brix')"
            >
              Brix
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'ph' }"
              @click="cambiarTabGrafico('ph')"
            >
              pH
            </button>
          </div>

          <!-- Filtro de tiempo con petición dinámica a la API -->
          <div class="btn-group">
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '1h' }"
              :disabled="chartLoading"
              @click="cambiarRangoHoras('1h')"
            >
              1 h
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '24h' }"
              :disabled="chartLoading"
              @click="cambiarRangoHoras('24h')"
            >
              24 h
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '48h' }"
              :disabled="chartLoading"
              @click="cambiarRangoHoras('48h')"
            >
              48 h
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '7d' }"
              :disabled="chartLoading"
              @click="cambiarRangoHoras('7d')"
            >
              7 días
            </button>
          </div>
        </div>
      </div>

      <p v-if="historico?.truncated" role="status">La ventana supera 10.000 muestras; se muestran las más recientes.</p>
      <!-- Canvas de Chart.js y Estados de Carga / Vacío -->
      <div class="chart-wrapper">
        <!-- Indicador de carga al cambiar rango -->
        <div v-if="chartLoading" class="chart-loading-overlay">
          <RefreshCw class="spin" :size="24" />
          <span>Actualizando serie histórica...</span>
        </div>

        <!-- Estado vacío sin romper Chart.js (Criterio 5) -->
        <div v-if="!tieneLecturas && !chartLoading" class="chart-empty-state">
          <div class="empty-icon-wrap">
            <Activity :size="32" class="empty-icon" />
          </div>
          <h4 class="empty-title">Sin registros de telemetría disponibles</h4>
          <p v-if="!tieneProcesoActivo" class="empty-desc">
            Esta cuba se encuentra en estado <strong>{{ cuba?.estado_operativo || 'disponible' }}</strong> y no tiene un proceso activo de fermentación en curso. Inicie una vendimia para comenzar a registrar lecturas de sensores.
          </p>
          <p v-else class="empty-desc">
            No se han registrado lecturas en la ventana seleccionada ({{ activeTimeRangeLabel }}).
          </p>
          <button
            v-if="estaDisponible"
            class="btn-lifecycle btn-lifecycle--start empty-state-btn"
            @click="abrirModalIniciar"
          >
            <Play :size="14" />
            <span>Iniciar Fermentación en {{ cubaNombre }}</span>
          </button>
        </div>

        <canvas ref="chartCanvasRef"></canvas>
      </div>

    </section>
    <!-- SECCIÓN PREDICCIÓN IA: Detección Temprana de Parada de Fermentación (Machine Learning) -->
    <KineticsPanel v-if="cuba?.proceso_activo_id" :key="`kinetics-${cuba.proceso_activo_id}`" :process-id="cuba.proceso_activo_id" />

    <section v-if="tieneProcesoActivo" class="ml-summary" id="riesgo-parada" aria-label="Estimación experimental de riesgo">
      <div class="ml-copy">
        <span class="ml-eyebrow">SIMULACIÓN · MACHINE LEARNING</span>
        <h2>Riesgo de parada <span class="ml-state">{{ estadoLabel }}</span></h2>
        <p>{{ prediccionML.mensaje }}</p>
        <details v-if="prediccionML.metodo === 'legacy_experimental'" class="ml-demo">
          <summary>Escenarios de demostración</summary>
          <div class="ml-actions">
            <button :disabled="isSimulatingAnomaly || isRestoringNormality" @click="ejecutarSimularAnomalia">{{ isSimulatingAnomaly ? 'Cargando…' : 'Cargar desviación' }}</button>
            <button :disabled="isSimulatingAnomaly || isRestoringNormality" @click="ejecutarRestaurarNormalidad">{{ isRestoringNormality ? 'Cargando…' : 'Cargar evolución normal' }}</button>
          </div>
        </details>
        <p v-if="iaToastMessage" role="status">{{ iaToastMessage }}</p>
      </div>
      <div v-if="prediccionML.riesgo_pct != null" class="ml-value" :style="{ color: iaGaugeColor }">
        <strong>{{ prediccionML.riesgo_pct.toFixed(1) }}<small>%</small></strong>
        <span>Estimación experimental</span>
        <span v-if="prediccionML.riesgo_instantaneo_pct != null">Instantánea: {{ prediccionML.riesgo_instantaneo_pct.toFixed(1) }} %</span>
      </div>
      <span v-else class="ml-wait">{{ sinModeloValidado ? 'Sin modelo aplicable' : 'Esperando evaluación' }}</span>
    </section>

    <details v-if="cuba?.proceso_activo_id" class="process-tools" @toggle="toggleProcessTools">
      <summary class="register-heading">
        <span>Mediciones e intervenciones</span>
        <small>Proceso #{{ cuba.proceso_activo_id }}</small>
        <ChevronDown :size="19" aria-hidden="true" />
      </summary>
      <template v-if="processToolsOpen">
        <fieldset class="register-switch" aria-label="Registro del proceso">
          <label><input v-model="registerView" type="radio" name="process-register" value="measurements" /><FlaskConical :size="16" />Mediciones</label>
          <label><input v-model="registerView" type="radio" name="process-register" value="interventions" /><ClipboardList :size="16" />Intervenciones</label>
        </fieldset>
        <ManualMeasurementsPanel v-show="registerView === 'measurements'" :key="`manual-${cuba.proceso_activo_id}`" :process-id="cuba.proceso_activo_id" :links-revision="linksRevision" in-register />
        <InterventionsPanel v-show="registerView === 'interventions'" :key="`interventions-${cuba.proceso_activo_id}`" :process-id="cuba.proceso_activo_id" in-register @changed="linksRevision++" />
        <SimulationStatus :key="cuba.proceso_activo_id" :process-id="cuba.proceso_activo_id" />
      </template>
    </details>
    <RouterLink v-if="cuba?.proceso_activo_id" class="process-history-link" :to="`/procesos/${cuba.proceso_activo_id}`">Ver historial y comparar procesos →</RouterLink>


    <!-- Historial de Alertas y Eventos Recientes -->
    <section class="events-section" id="eventos">
      <div class="events-header">
        <div class="events-title">
          <Clock :size="18" />
          <h3>Lecturas y alertas recientes</h3>
        </div>
        <span class="events-count">{{ alertsList.length }} registros</span>
      </div>

      <div v-if="alertsList.length === 0" class="empty-alerts">
        <p>No se registran alertas ni incidencias recientes en esta cuba.</p>
      </div>

      <div v-else class="events-list">
        <div
          v-for="item in alertsList"
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

    <!-- ======================================================= -->
    <!-- MODAL 1: INICIAR FERMENTACIÓN (VENDIMIA)                -->
    <!-- Habilitado solo si la cuba está en estado "disponible"  -->
    <!-- ======================================================= -->
    <div
      v-if="isStartModalOpen"
      class="modal-backdrop"
      @click.self="cerrarModalIniciar"
    >
      <div class="process-modal" role="dialog" aria-modal="true" aria-labelledby="start-modal-title">
        <!-- Header -->
        <div class="modal-header">
          <div class="modal-title-group">
            <div class="modal-icon-badge modal-icon--start">
              <Play :size="20" />
            </div>
            <div>
              <h2 id="start-modal-title" class="modal-title">Iniciar Proceso de Fermentación</h2>
              <p class="modal-sub">
                {{ cubaNombre }} · Capacidad máxima: {{ capacidadMaximaLitros.toLocaleString('es-CL') }} L
              </p>
            </div>
          </div>
          <button
            type="button"
            class="modal-close-btn"
            @click="cerrarModalIniciar"
            :disabled="startFormSubmitting"
            aria-label="Cerrar modal"
          >
            <X :size="18" />
          </button>
        </div>

        <!-- Banner de Error Backend -->
        <div v-if="startFormError" class="modal-error-banner">
          <AlertCircle :size="18" class="flex-shrink-0" />
          <div class="error-text">
            <strong>Error de validación:</strong>
            <span>{{ startFormError }}</span>
          </div>
        </div>

        <!-- Formulario con campos requeridos por Criterios de Aceptación -->
        <form @submit.prevent="ejecutarIniciarProceso" class="modal-form">
          <div class="modal-body">
            <div class="form-grid">
              <!-- Cuba ID (Informativo / Preseleccionado) -->
              <div class="form-group form-group--full">
                <label class="form-label">Cuba Asignada</label>
                <div class="input-readonly-box">
                  <Cylinder :size="16" class="text-wine" />
                  <span><strong>{{ cubaNombre }}</strong> (ID: {{ selectedCubaId }}) · Estado actual: <span class="badge-disponible">{{ cuba?.estado_operativo || 'disponible' }}</span></span>
                </div>
              </div>

              <!-- Volumen Litros -->
              <div class="form-group form-group--full">
                <label for="volumen_litros" class="form-label">
                  Volumen de Vendimia (Litros) <span class="required">*</span>
                </label>
                <div class="input-with-affix">
                  <input
                    id="volumen_litros"
                    v-model.number="startForm.volumen_litros"
                    type="number"
                    step="50"
                    min="1"
                    :max="capacidadMaximaLitros"
                    placeholder="Ej: 8000"
                    class="form-input"
                    :class="{ 'input--invalid': Number(startForm.volumen_litros) > capacidadMaximaLitros }"
                    required
                  />
                  <span class="input-suffix">Litros</span>
                </div>
                <small
                  class="form-hint"
                  :class="{ 'text-danger': Number(startForm.volumen_litros) > capacidadMaximaLitros }"
                >
                  Capacidad máxima de la cuba: {{ capacidadMaximaLitros.toLocaleString('es-CL') }} L
                  <span v-if="Number(startForm.volumen_litros) > capacidadMaximaLitros"> — ¡Volumen excede la capacidad!</span>
                </small>
              </div>

              <!-- Brix Inicial -->
              <div class="form-group">
                <label for="brix_inicial" class="form-label">
                  Brix Inicial (°Bx) <span class="required">*</span>
                </label>
                <div class="input-with-affix">
                  <input
                    id="brix_inicial"
                    v-model.number="startForm.brix_inicial"
                    type="number"
                    step="0.1"
                    min="10"
                    max="35"
                    placeholder="24.5"
                    class="form-input"
                    required
                  />
                  <span class="input-suffix">°Bx</span>
                </div>
                <small class="form-hint">Azúcar inicial del mosto (Típico: 22 - 26 °Bx)</small>
              </div>

              <!-- Brix Objetivo -->
              <div class="form-group">
                <label for="brix_objetivo" class="form-label">
                  Brix Objetivo (°Bx) <span class="required">*</span>
                </label>
                <div class="input-with-affix">
                  <input
                    id="brix_objetivo"
                    v-model.number="startForm.brix_objetivo"
                    type="number"
                    step="0.1"
                    min="0"
                    max="10"
                    placeholder="1.0"
                    class="form-input"
                    required
                  />
                  <span class="input-suffix">°Bx</span>
                </div>
                <small class="form-hint">Meta fin de fermentación (Vino seco: 0 - 2 °Bx)</small>
              </div>

              <!-- Días Estimados -->
              <div class="form-group">
                <label for="dias_estimados" class="form-label">
                  Duración Estimada (Días) <span class="required">*</span>
                </label>
                <div class="input-with-affix">
                  <input
                    id="dias_estimados"
                    v-model.number="startForm.dias_estimados"
                    type="number"
                    step="1"
                    min="1"
                    max="60"
                    placeholder="14"
                    class="form-input"
                    required
                  />
                  <span class="input-suffix">Días</span>
                </div>
                <small class="form-hint">Tiempo estimado de fermentación alcohólica</small>
              </div>

              <!-- Densidad Inicial SG (opcional) -->
              <div class="form-group">
                <label for="densidad_inicial" class="form-label">
                  Densidad Inicial (SG)
                </label>
                <div class="input-with-affix">
                  <input
                    id="densidad_inicial"
                    v-model.number="startForm.densidad_inicial_sg"
                    type="number"
                    step="0.0001"
                    min="1.0500"
                    max="1.1500"
                    placeholder="1.1000"
                    class="form-input"
                  />
                  <span class="input-suffix">SG</span>
                </div>
                <small class="form-hint">Gravedad específica estimada (1.090 - 1.115)</small>
              </div>
            </div>
          </div>

          <!-- Footer con botones de acción -->
          <div class="modal-footer">
            <button
              type="button"
              class="btn-modal-cancel"
              @click="cerrarModalIniciar"
              :disabled="startFormSubmitting"
            >
              Cancelar
            </button>
            <button
              type="submit"
              class="btn-modal-submit btn-modal-submit--start"
              :disabled="startFormSubmitting || Number(startForm.volumen_litros) > capacidadMaximaLitros"
            >
              <RefreshCw v-if="startFormSubmitting" :size="15" class="spin" />
              <Play v-else :size="15" />
              <span>{{ startFormSubmitting ? 'Iniciando proceso...' : 'Confirmar e Iniciar' }}</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ======================================================= -->
    <!-- MODAL 2: FINALIZAR FERMENTACIÓN                         -->
    <!-- Confirmación, captura de densidad final y observaciones -->
    <!-- ======================================================= -->
    <div
      v-if="isFinishModalOpen"
      class="modal-backdrop"
      @click.self="cerrarModalFinalizar"
    >
      <div class="process-modal" role="dialog" aria-modal="true" aria-labelledby="finish-modal-title">
        <!-- Header -->
        <div class="modal-header">
          <div class="modal-title-group">
            <div class="modal-icon-badge modal-icon--finish">
              <CheckCircle2 :size="20" />
            </div>
            <div>
              <h2 id="finish-modal-title" class="modal-title">Finalizar Fermentación y Liberar Cuba</h2>
              <p class="modal-sub">
                {{ cubaNombre }} · Proceso Activo #{{ cuba?.proceso_activo_id }}
              </p>
            </div>
          </div>
          <button
            type="button"
            class="modal-close-btn"
            @click="cerrarModalFinalizar"
            :disabled="finishFormSubmitting"
            aria-label="Cerrar modal"
          >
            <X :size="18" />
          </button>
        </div>

        <!-- Banner de Advertencia / Confirmación -->
        <div class="modal-warning-banner">
          <AlertTriangle :size="20" class="flex-shrink-0 text-warn" />
          <p>
            ¿Confirmas la finalización del proceso de fermentación? Esta acción marcará el proceso como <strong>"finalizado"</strong>, registrará la fecha real de fin y liberará la cuba cambiando su estado operativo a <strong>"disponible"</strong>.
          </p>
        </div>

        <!-- Banner de Error Backend -->
        <div v-if="finishFormError" class="modal-error-banner">
          <AlertCircle :size="18" class="flex-shrink-0" />
          <div class="error-text">
            <strong>Error:</strong>
            <span>{{ finishFormError }}</span>
          </div>
        </div>

        <!-- Resumen de Telemetría al Cierre -->
        <div class="closeout-summary">
          <div class="summary-item">
            <span class="label">Temperatura Actual:</span>
            <span class="val">{{ temperaturaActual !== null ? temperaturaActual.toFixed(1) + ' °C' : '--' }}</span>
          </div>
          <div class="summary-item">
            <span class="label">Último Brix:</span>
            <span class="val">{{ brixActual !== null ? brixActual.toFixed(1) + ' °Bx' : '--' }}</span>
          </div>
          <div class="summary-item">
            <span class="label">Días Transcurridos:</span>
            <span class="val">{{ diaFermentacion }} días</span>
          </div>
        </div>

        <!-- Formulario de Finalización -->
        <form @submit.prevent="ejecutarFinalizarProceso" class="modal-form">
          <div class="modal-body">
            <div class="form-grid">
              <!-- Densidad Final SG -->
              <div class="form-group">
                <label for="densidad_final_sg" class="form-label">
                  Densidad Final (SG)
                </label>
                <div class="input-with-affix">
                  <input
                    id="densidad_final_sg"
                    v-model.number="finishForm.densidad_final_sg"
                    type="number"
                    step="0.0001"
                    min="0.9800"
                    max="1.1000"
                    placeholder="Ej: 0.9940"
                    class="form-input"
                  />
                  <span class="input-suffix">SG</span>
                </div>
                <small class="form-hint">Densidad final registrada por densímetro o picnómetro</small>
              </div>

              <!-- Brix Final -->
              <div class="form-group">
                <label for="brix_final" class="form-label">
                  Grados Brix Final (°Bx)
                </label>
                <div class="input-with-affix">
                  <input
                    id="brix_final"
                    v-model.number="finishForm.brix_final"
                    type="number"
                    step="0.1"
                    min="0"
                    max="10"
                    placeholder="Ej: 1.0"
                    class="form-input"
                  />
                  <span class="input-suffix">°Bx</span>
                </div>
                <small class="form-hint">Azúcar residual medido al cierre de fermentación</small>
              </div>

              <!-- Observaciones / Motivo -->
              <div class="form-group form-group--full">
                <label for="observaciones" class="form-label">
                  Observaciones Enológicas de Cierre
                </label>
                <textarea
                  id="observaciones"
                  v-model="finishForm.observaciones"
                  rows="3"
                  placeholder="Detalles sobre el descube, cata sensorial, trasiego a barrica o motivo de término..."
                  class="form-textarea"
                ></textarea>
                <small class="form-hint">Quedará registrado para la trazabilidad del lote y la cuba</small>
              </div>
            </div>
          </div>

          <!-- Footer con botones -->
          <div class="modal-footer">
            <button
              type="button"
              class="btn-modal-cancel"
              @click="cerrarModalFinalizar"
              :disabled="finishFormSubmitting"
            >
              Cancelar
            </button>
            <button
              type="submit"
              class="btn-modal-submit btn-modal-submit--finish"
              :disabled="finishFormSubmitting"
            >
              <RefreshCw v-if="finishFormSubmitting" :size="15" class="spin" />
              <CheckCircle2 v-else :size="15" />
              <span>{{ finishFormSubmitting ? 'Finalizando proceso...' : 'Confirmar Cierre y Liberar Cuba' }}</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Toast de Notificaciones Flotante -->
    <transition name="toast-fade">
      <div
        v-if="toastMessage"
        class="toast-popup"
        :class="'toast-popup--' + toastType"
        role="alert"
      >
        <CheckCircle2 v-if="toastType === 'success'" :size="18" class="toast-icon text-good" />
        <AlertTriangle v-else-if="toastType === 'warning'" :size="18" class="toast-icon text-warn" />
        <AlertCircle v-else :size="18" class="toast-icon text-error" />
        <span class="toast-text">{{ toastMessage }}</span>
      </div>
    </transition>
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
  text-decoration: none;
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

.metric-icon-ph { background: #f3edf9; color: #75419a; }
.header-actions-row > button { min-height: 36px; }
.header-actions-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.sync-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background-color: var(--status-good-bg, #edf7ee);
  border: 1px solid var(--status-good-border, #c3e6cb);
  color: var(--status-good, #2a6644);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.3rem 0.65rem;
  border-radius: var(--radius-full);
}

.sync-icon-pulse {
  animation: pulseSync 2s infinite ease-in-out;
}

@keyframes pulseSync {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--wine-800);
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.35rem 0.75rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s;
}

.btn-refresh:hover:not(:disabled) {
  background-color: var(--wine-100);
  border-color: var(--wine-300);
}

.btn-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.status-pill { display:inline-flex; align-items:center; gap:6px; font-weight:600; color:var(--text-primary); }
.status-dot { width:7px; height:7px; border:1px solid #786c71; border-radius:50%; flex:none; }
.status-pill--optimal .status-dot { background:#587354; border-color:#587354; }
.status-pill--warning { color:#805011; }
.status-pill--warning .status-dot { background:currentColor; border:0; border-radius:0; transform:rotate(45deg); }
.days-tracker { display:flex; align-items:center; flex-wrap:wrap; justify-content:flex-end; gap:4px 12px; font-size:.78rem; color:var(--text-secondary); font-weight:500; }
.days-tracker--empty {
  color: var(--text-muted);
  font-style: italic;
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
  transition: all 0.3s ease;
}

.card-flash {
  animation: pulseCard 1s ease-out;
}

@keyframes pulseCard {
  0% {
    border-color: var(--wine-500);
    box-shadow: 0 0 14px rgba(118, 31, 51, 0.3);
  }
  100% {
    border-color: var(--border-color);
    box-shadow: var(--shadow-subtle);
  }
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
  background-color: #fef8ef;
  color: #c47f17;
}

.metric-icon-good {
  background-color: var(--status-good-bg);
  color: var(--status-good);
}

.metric-icon-warn {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
}

.metric-icon-neutral {
  background-color: #f1f3f5;
  color: #868e96;
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

.summary-neutral {
  color: var(--text-secondary);
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
  color: #1565c0;
}

.trend-stable {
  color: var(--text-muted);
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

.chart-source { background: white; border: 1px solid var(--border-color); border-radius: 6px; padding: 0 .5rem; min-height: 32px; }
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
  background: transparent;
  border: none;
  cursor: pointer;
}

.btn-filter.active {
  background-color: var(--bg-surface);
  color: var(--wine-800);
  box-shadow: 0 1px 3px rgba(35, 22, 28, 0.08);
}

.btn-filter:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chart-wrapper {
  position: relative;
  height: 320px;
  width: 100%;
}

.chart-loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(2px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  z-index: 10;
  color: var(--wine-800);
  font-size: 0.85rem;
  font-weight: 600;
}

.chart-empty-state {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 2rem;
  z-index: 5;
}

.empty-icon-wrap {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background-color: var(--bg-subtle, #f5f2f0);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.75rem;
  color: var(--text-muted);
}

.empty-title {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wine-900);
  margin-bottom: 0.35rem;
}

.empty-desc {
  max-width: 440px;
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.45;
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
  background-color: var(--bg-subtle, #f5f2f0);
  padding: 0.2rem 0.5rem;
  border-radius: var(--radius-full);
}

.empty-alerts {
  padding: 1.5rem 0;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.85rem;
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

/* Estados Globales de Carga y Error */
.view-loading-state,
.view-error-state {
  min-height: 380px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 1rem;
  color: var(--text-secondary);
}

.view-error-state .error-icon {
  color: #dc3545;
}

.btn-retry {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--wine-700);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-sm);
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn-retry:hover {
  background-color: var(--wine-800);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* ==========================================
   BOTONES DE CICLO DE VIDA (HEADER Y CARDS)
   ========================================== */
.btn-lifecycle {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.42rem 0.85rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.btn-lifecycle--start {
  background-color: var(--wine-700);
  color: #FFFFFF;
}

.btn-lifecycle--start:hover:not(:disabled) {
  background-color: var(--wine-800);
  box-shadow: 0 2px 6px rgba(118, 31, 51, 0.25);
}

.btn-lifecycle--start:disabled {
  background-color: #e9ecef;
  color: #adb5bd;
  border-color: #dee2e6;
  cursor: not-allowed;
  opacity: 0.7;
}

.btn-lifecycle--finish {
  background-color: #FFF1F0;
  color: #CF1322;
  border-color: #FFA39E;
}

.btn-lifecycle--finish:hover {
  background-color: #CF1322;
  color: #FFFFFF;
  border-color: #CF1322;
}

.card-action-bar {
  margin-top: 0.85rem;
  padding-top: 0.75rem;
  border-top: 1px dashed var(--border-color);
}

.btn-card-action {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  font-size: 0.76rem;
  font-weight: 600;
  padding: 0.45rem 0.75rem;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-card-action--start {
  background-color: var(--wine-100);
  color: var(--wine-800);
  border-color: var(--wine-300);
}

.btn-card-action--start:hover:not(:disabled) {
  background-color: var(--wine-700);
  color: #FFFFFF;
}

.btn-card-action--start:disabled {
  background-color: #f1f3f5;
  color: #adb5bd;
  border-color: #dee2e6;
  cursor: not-allowed;
}

.btn-card-action--finish {
  background-color: #FFF2F0;
  color: #D4380D;
  border-color: #FFBB96;
}

.btn-card-action--finish:hover {
  background-color: #D4380D;
  color: #FFFFFF;
}

.empty-state-btn {
  margin-top: 1rem;
}

/* ==========================================
   MODALES DE PROCESOS
   ========================================== */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(35, 22, 28, 0.45);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1.5rem;
  animation: fadeIn 0.2s ease-out;
}

.process-modal {
  background-color: var(--bg-surface);
  border-radius: var(--radius-md);
  box-shadow: 0 15px 40px rgba(35, 22, 28, 0.25);
  border: 1px solid var(--border-color);
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.25s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--bg-surface);
}

.modal-title-group {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.modal-icon-badge {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.modal-icon--start {
  background-color: var(--wine-100);
  color: var(--wine-700);
}

.modal-icon--finish {
  background-color: #E6F7ED;
  color: #1E7E34;
}

.modal-title {
  font-family: var(--font-serif);
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--wine-900);
  margin: 0;
  line-height: 1.2;
}

.modal-sub {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-top: 0.2rem;
}

.modal-close-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.35rem;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.modal-close-btn:hover:not(:disabled) {
  background-color: var(--bg-canvas);
  color: var(--wine-900);
}

.modal-error-banner {
  background-color: #FFF2F0;
  border: 1px solid #FFCCC7;
  color: #CF1322;
  padding: 0.75rem 1.25rem;
  font-size: 0.82rem;
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
}

.modal-error-banner .error-text {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.modal-warning-banner {
  background-color: var(--status-warn-bg);
  border-bottom: 1px solid var(--status-warn-border);
  color: var(--status-warn);
  padding: 0.85rem 1.35rem;
  font-size: 0.82rem;
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  line-height: 1.4;
}

.modal-warning-banner p {
  margin: 0;
  color: var(--text-secondary);
}

.closeout-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background-color: var(--bg-canvas);
  border-bottom: 1px solid var(--border-color);
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.summary-item .label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  font-weight: 600;
}

.summary-item .val {
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--wine-900);
}

.modal-form {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-body {
  padding: 1.25rem 1.5rem;
  overflow-y: auto;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
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
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.form-label .required {
  color: #CF1322;
}

.input-readonly-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.85rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  color: var(--text-primary);
}

.badge-disponible {
  background-color: #E6F7ED;
  color: #1E7E34;
  font-weight: 700;
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
  font-size: 0.72rem;
}

.input-with-affix {
  position: relative;
  display: flex;
  align-items: center;
}

.form-input {
  width: 100%;
  padding: 0.55rem 0.75rem;
  padding-right: 3.5rem;
  font-size: 0.85rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background-color: var(--bg-surface);
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.form-input:focus {
  border-color: var(--wine-700);
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.1);
}

.form-input.input--invalid {
  border-color: #CF1322;
  background-color: #FFF2F0;
}

.input-suffix {
  position: absolute;
  right: 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  pointer-events: none;
}

.form-textarea {
  width: 100%;
  padding: 0.6rem 0.75rem;
  font-size: 0.84rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background-color: var(--bg-surface);
  color: var(--text-primary);
  outline: none;
  resize: vertical;
  font-family: inherit;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.form-textarea:focus {
  border-color: var(--wine-700);
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.1);
}

.form-hint {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.form-hint.text-danger {
  color: #CF1322;
  font-weight: 600;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color);
  background-color: var(--bg-canvas);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-modal-cancel {
  padding: 0.5rem 1rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-modal-cancel:hover:not(:disabled) {
  background-color: var(--bg-surface);
  color: var(--wine-900);
}

.btn-modal-submit {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.5rem 1.15rem;
  font-size: 0.82rem;
  font-weight: 600;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-modal-submit--start {
  background-color: var(--wine-700);
  color: #FFFFFF;
}

.btn-modal-submit--start:hover:not(:disabled) {
  background-color: var(--wine-800);
  box-shadow: 0 2px 6px rgba(118, 31, 51, 0.25);
}

.btn-modal-submit--finish {
  background-color: #1E7E34;
  color: #FFFFFF;
}

.btn-modal-submit--finish:hover:not(:disabled) {
  background-color: #155724;
  box-shadow: 0 2px 6px rgba(30, 126, 52, 0.25);
}

.btn-modal-submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* ==========================================
   TOAST FLOTANTE DE NOTIFICACIONES
   ========================================== */
.toast-popup {
  position: fixed;
  top: 1.5rem;
  right: 1.75rem;
  z-index: 2000;
  padding: 0.85rem 1.25rem;
  border-radius: var(--radius-md);
  box-shadow: 0 10px 25px rgba(35, 22, 28, 0.18);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.85rem;
  font-weight: 500;
  border: 1px solid transparent;
  max-width: 420px;
}

.toast-popup--success {
  background-color: #0F5132;
  color: #FFFFFF;
  border-color: #0A3622;
}

.toast-popup--error {
  background-color: #842029;
  color: #FFFFFF;
  border-color: #58151C;
}

.toast-popup--warning {
  background-color: #664D03;
  color: #FFFFFF;
  border-color: #433302;
}

.toast-icon.text-good {
  color: #75B798;
}

.toast-icon.text-error {
  color: #EA868F;
}

.toast-icon.text-warn {
  color: #FFDA6A;
}

.toast-text {
  line-height: 1.35;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.25s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

.ml-summary { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 24px; border: 1px solid #653747; border-radius: 16px; background: #38202b; color: #f4e9ed; }
.ml-copy { flex: 1; } .ml-eyebrow { color: #d0aeb9; font-size: 10px; font-weight: 700; letter-spacing: .13em; }
.ml-summary h2 { font-size: 19px; margin: 8px 0; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.ml-state { font-size: 10px; padding: 5px 9px; border: 1px solid #805364; border-radius: 20px; color: #e2c7d0; }
.ml-summary p { font-size: 13px; color: #d8c3ca; line-height: 1.6; margin: 6px 0; }
.ml-value { display: grid; gap: 6px; min-width: 150px; text-align: right; } .ml-value strong { font-size: 40px; font-variant-numeric: tabular-nums; } .ml-value small { font-size: 22px; }
.ml-value span, .ml-wait { font-size: 12px; color: #d8c3ca; }
.ml-demo { margin-top: 12px; font-size: 12px; } .ml-demo summary { cursor: pointer; color: #d8c3ca; }
.ml-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; } .ml-actions button { background: #573342; color: #f4e9ed; border: 1px solid #805364; border-radius: 8px; padding: 9px 12px; cursor: pointer; }
.ml-actions button:disabled { opacity: .5; cursor: wait; }
.process-tools {
  --register-line: #dbd2ca;
  min-width: 0;
  border: 1px solid var(--register-line);
  border-radius: 12px;
  background: var(--bg-surface);
  color: var(--wine-900);
}
.register-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  padding: 17px clamp(14px, 2vw, 26px);
  border-radius: 11px;
  cursor: pointer;
  background: #eee7dd;
  list-style: none;
}
.register-heading::-webkit-details-marker, .process-tools :deep(summary::-webkit-details-marker) { display: none; }
.register-heading > span { flex: 1; font: 400 clamp(1.65rem, 2.5vw, 2.1rem)/1.15 var(--font-serif); }
.register-heading small { font-size: .8rem; color: var(--text-muted); }
.register-heading svg { color: var(--wine-700); flex: none; }
.process-tools[open] > .register-heading { border-radius: 11px 11px 0 0; }
.process-tools[open] > .register-heading svg { transform: rotate(180deg); }
.register-switch {
  display: flex; flex-wrap: wrap; gap: 0 20px;
  margin: 0; padding: 0 clamp(14px, 2vw, 26px);
  border: 0; border-bottom: 1px solid var(--register-line);
  min-width: 0;
}
.register-switch label { position: relative; display: flex; align-items: center; gap: 7px; padding: 11px 0; border-bottom: 2px solid transparent; cursor: pointer; color: var(--text-muted); font-size: .88rem; }
.register-switch label:has(:checked) { color: var(--wine-700); border-color: currentColor; font-weight: 650; }
.register-switch input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.process-tools :deep(:is(.manual-measurements, .interventions)) { margin: 0; padding: 18px clamp(14px, 2vw, 26px) 22px; background: transparent; border: 0; color: var(--wine-900); }
.process-tools :deep(.register-toolbar), .process-tools :deep(.reading-head) { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px 14px; }
.process-tools :deep(.register-toolbar h3) { margin: 0; font: 400 1.75rem/1.15 var(--font-serif); }
.process-tools :deep(.register-toolbar h3 span) { margin-left: 5px; font: 500 .83rem var(--font-sans); color: var(--text-muted); }
.process-tools :deep(p), .process-tools :deep(li) { font-size: .86rem; line-height: 1.55; }
.process-tools :deep(.register-toolbar + p) { max-width: 76ch; color: var(--text-muted); margin: 6px 0 12px; }
.process-tools :deep(button), .process-tools :deep(details > summary) { display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px; padding: 7px 11px; margin: 0; border: 1px solid var(--register-line); border-radius: 6px; color: var(--wine-700); background: var(--bg-surface); font: 600 .81rem/1.45 var(--font-sans); cursor: pointer; }
.process-tools :deep(button:hover:enabled) { border-color: var(--wine-700); }
.process-tools :deep(.register-toolbar button) { border: 0; padding: 5px 0; min-height: 30px; }
.process-tools :deep(.register-toolbar button:hover:enabled) { text-decoration: underline; text-underline-offset: 3px; }
.process-tools :deep(details) { padding: 0; border: 0; margin: 12px 0 16px; }
.process-tools :deep(details > summary), .process-tools :deep(form button:not([type=button])) { color: var(--bg-surface); background: var(--wine-700); border-color: var(--wine-700); }
.process-tools :deep(details > summary:hover), .process-tools :deep(form button:not([type=button]):hover:enabled) { background: #603044; }
.process-tools :deep(details[open] > summary svg) { transform: rotate(45deg); }
.process-tools :deep(.reading-details) { margin: 4px 0 0; }
.process-tools :deep(.reading-details > summary) { min-height: 32px; padding: 3px 0; border: 0; border-radius: 0; color: var(--wine-700); background: transparent; }
.process-tools :deep(.reading-details > summary:hover) { background: transparent; text-decoration: underline; }
.process-tools :deep(.reading-details > summary::after) { content: ''; width: 6px; height: 6px; margin: -3px 3px 0; border: solid currentColor; border-width: 0 1.5px 1.5px 0; transform: rotate(45deg); }
.process-tools :deep(.reading-details[open] > summary::after) { margin-top: 3px; transform: rotate(225deg); }
.process-tools :deep(.reading-details > p) { margin-block: 5px; }
.process-tools :deep(form) { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); align-items: start; gap: 12px 18px; padding: 18px; margin-top: 12px; background: #f5f0e8; border-radius: 8px; }
.process-tools :deep(form > p), .process-tools :deep(form > div), .process-tools :deep(form > label:has(textarea)) { grid-column: 1/-1; }
.process-tools :deep(form label) { min-width: 0; font-size: .84rem; font-weight: 600; }
.process-tools :deep(form :is(input,select,textarea)) { color: var(--wine-900); background: var(--bg-surface); border: 1px solid #bbaea6; font: 400 .9rem/1.4 var(--font-sans); }
.process-tools :deep(form p) { color: var(--text-muted); font-size: .8rem; }
.process-tools :deep(form button) { justify-self: start; }
.process-tools :deep(.empty-register) { color: var(--text-muted); border-top: 1px solid var(--register-line); padding-top: 13px; }
.process-tools :deep(article) { padding: 16px 0 4px; margin-top: 12px; border: 0; border-top: 1px solid var(--register-line); }
.process-tools :deep(.reading-head) { justify-content: flex-start; margin-bottom: 8px; }
.process-tools :deep(.reading-head h4) { margin: 0 auto 0 0; font: 600 1rem/1.4 var(--font-sans); }
.process-tools :deep(.reading-head small), .process-tools :deep(.reading-head span) { font: 500 .81rem var(--font-sans); color: var(--text-muted); }
.process-tools :deep(.reading-head strong) { font: 400 1.9rem/1 var(--font-serif); font-variant-numeric: tabular-nums; }
.process-tools :deep(article > p), .process-tools :deep(article > button) { margin: 3px 7px 5px 0; }
.process-tools :deep(article ol) { padding-left: 22px; margin-block: 10px; }
.process-tools :deep(article li) { padding: 5px 0; }
.process-tools :deep(nav) { margin-top: 16px; }
.process-tools :deep([role=alert]) { color: #8c3446; }
.process-tools :deep(:focus-visible), .register-switch label:has(:focus-visible) { outline: 2px solid var(--wine-700); outline-offset: 3px; }
.process-tools :deep(.simulation-panel) { margin: 0; border: 0; border-top: 1px solid var(--register-line); border-radius: 0 0 12px 12px; background: #f5f0e8; }
@media(max-width: 650px) {
  .register-heading small { display: none; }
  .register-switch { gap: 0 12px; }
  .register-switch label { font-size: .8rem; gap: 4px; }
  .process-tools :deep(form) { grid-template-columns: minmax(0,1fr); padding: 13px; }
  .process-tools :deep(.register-toolbar) { align-items: center; }
}
.process-history-link { color: #76263d; font-size: 13px; align-self: flex-start; }
@media(max-width: 900px) { .ml-summary { align-items: flex-start; flex-direction: column; padding: 18px; } .ml-value { text-align: left; } }
.header-left, .title-selector-row, .selector-wrapper { min-width: 0; max-width: 100%; }
.cuba-select { max-width: 100%; } .cuba-subtitle { overflow-wrap: anywhere; }
/* Ficha del atlas */
.cuba-detail-view {
  --font-serif: 'Instrument Serif', Georgia, serif;
  --wine-900: #30232a;
  --wine-800: #53313f;
  --wine-700: #763c51;
  --wine-100: #efe3e6;
  --bg-surface: #fffdf9;
  --border-subtle: #e7ddd5;
  --text-muted: #695d61;
  max-width: 1540px;
  width: 100%;
  margin-inline: auto;
  gap: 1.15rem;
}
.detail-header { align-items: flex-end; padding-bottom: 1rem; border-bottom: 1px solid var(--border-color); }
.header-left, .header-right, .title-selector-row > div, .selector-wrapper { min-width: 0; max-width: 100%; }
.back-link { color: var(--wine-700); }
.cuba-select { max-width: 100%; font: 400 3.15rem/1.12 var(--font-serif); letter-spacing: -.025em; }
.cuba-select option { font: 1rem var(--font-sans); }
.cuba-subtitle { margin-top: 3px; font-size: .91rem; color: var(--text-secondary); }
.btn-lifecycle--finish, .btn-lifecycle--start { background: #fffdf9; color: #673548; border: 1px solid #c9afba; }
.btn-refresh { background: #763c51; color: #fffdf9; border: 1px solid #763c51; }
.btn-refresh:hover { background: #5e293d; color: white; }
.alert-box { border: 1px solid #dac2aa; background: #f6e7d7; border-radius: 10px; }
.telemetry-spread { display: grid; grid-template-columns: minmax(240px,.85fr) minmax(0,1.7fr); gap: 16px; }
.vessel-profile { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 20px 16px; background: #32232d; color: #fff6ef; border-radius: 14px; }
.vessel-profile svg { width: 43%; max-width: 140px; flex-shrink: 0; }
.vessel-profile figcaption { display: grid; gap: 5px; }
.vessel-profile h2 { font-size: .88rem; font-weight: 550; color: #eddbdb; }
.vessel-profile strong { font: 400 3.15rem/1.1 var(--font-serif); }
.vessel-profile span { font-size: .8rem; color: #e6cfd6; }
.readings { border-block: 1px solid #dcd4ca; padding: 16px 0; }
.readings > h2, .chart-main-title, .events-title h3, .ml-summary h2, .modal-title { font: 400 2rem/1.15 var(--font-serif); }
.readings > h2 { margin-bottom: 16px; }
.metrics-grid { grid-template-columns: repeat(3,minmax(0,1fr)); gap: 0; }
.metric-card { background: transparent; box-shadow: none; border: 0; border-radius: 0; padding: 0 14px; justify-content: flex-start; }
.metric-card + .metric-card { border-left: 1px solid #dcd4ca; }
.metric-card:first-child { padding-left: 0; }
.metric-card-top { display: block; margin-bottom: 9px; }
.metric-card-top > div:first-child { display: flex; flex-direction: column-reverse; }
.metric-title { font-size: .86rem; margin: 0; }
.sensor-tag { text-transform: none; font-size: .75rem; font-weight: 450; letter-spacing: 0; }
.metric-icon { display: none; }
.metric-number { font: 400 2.7rem/1 var(--font-serif); }
.metric-val-group { margin-bottom: 10px; }
.metric-details { border: 0; padding: 0; gap: 4px; }
.metric-subtext, .trend-tag { font-size: .75rem; }
.card-flash { animation: none; }
.detail-index { display: flex; gap: 8px 24px; flex-wrap: wrap; border-bottom: 1px solid #dcd4ca; }
.detail-index a { color: #763c51; font-weight: 650; font-size: .83rem; padding: 7px 0 10px; }
.detail-index a:hover { text-decoration: underline; }
.chart-section, .events-section { border-radius: 12px; box-shadow: none; }
.chart-section, .events-section, .ml-summary { scroll-margin-top: 14px; }
.btn-filter { color: #5c5054; min-height: 32px; }
.btn-filter.active { background: #763c51; color: #fffdf9; }
.chart-wrapper { height: 285px; }
.ml-eyebrow { color: #ecd4da; }
@media (max-width: 1150px) {
  .telemetry-spread { grid-template-columns: minmax(195px,.65fr) minmax(0,1.6fr); }
  .vessel-profile { padding: 12px; }
  .metric-card { padding-inline: 8px; }
}
@media (max-width: 720px) {
  .detail-header { gap: 12px; flex-direction: column; align-items: stretch; }
  .header-right { align-items: flex-start; }
  .cuba-select { font-size: 2.3rem; }
  .telemetry-spread { grid-template-columns: minmax(0,1fr); }
  .vessel-profile { justify-content: flex-start; padding: 8px 16px; }
  .vessel-profile svg { height: 107px; width: 95px; }
  .vessel-profile strong { font-size: 2.4rem; }
  .metrics-grid { grid-template-columns: minmax(0,1fr); }
  .metric-card, .metric-card:first-child { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 3px 8px; padding: 8px 0; }
  .metric-card + .metric-card { border-left: none; border-top: 1px solid var(--border-subtle); }
  .metric-details { grid-column: 1/-1; flex-direction: row; flex-wrap: wrap; }
  .metric-card-top, .metric-val-group { margin: 0; }
  .metric-number { font-size: 2rem; }
  .detail-index { gap: 0 16px; }
  .chart-controls, .btn-group, .form-grid { max-width: 100%; }
  .btn-group { flex-wrap: wrap; }
  .chart-section, .events-section { padding: 14px; }
  .chart-wrapper { height: 265px; }
  .chart-empty-state { padding: 10px; }
  .form-grid { grid-template-columns: 1fr; }
}
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
@media (max-width: 720px) {
  .header-right .days-tracker { order:-1; justify-content:flex-start; }
}
</style>
