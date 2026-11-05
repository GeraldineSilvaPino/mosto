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
  Info,
  RefreshCw,
  AlertCircle,
  Radio,
  Play,
  Square,
  X
} from 'lucide-vue-next'

import { Chart as ChartJS, registerables } from 'chart.js'
import cubaService from '../services/cubaService'
import alertService from '../services/alertService'
import processService from '../services/processService'

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

const loading = ref(true)
const chartLoading = ref(false)
const error = ref(null)
const lastSyncTime = ref(null)
const flashUpdate = ref(false)

const selectedCubaId = ref(1)
const activeTimeRange = ref('24h') // '24h' | '48h' | '7d'
const activeChartTab = ref('both') // 'both' | 'temp' | 'brix' | 'ph'

const chartCanvasRef = ref(null)
let chartInstance = null
let pollInterval = null

// ==========================================
// UTILITARIOS Y MAPEO DE TIEMPO
// ==========================================
function rangoToHoras(rango) {
  switch (rango) {
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
    case '48h':
      return '48 Horas'
    case '7d':
      return '7 Días'
    case '24h':
    default:
      return '24 Horas'
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

const tieneLecturas = computed(() => {
  if (!historico.value) return false
  const labels = historico.value.labels || historico.value.timestamps || []
  return labels.length > 0 && (historico.value.total_muestras > 0 || labels.length > 0)
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
  return [
    { id: 1, codigo_cuba: 'CB-01', nombre: 'Cuba CB-01' },
    { id: 2, codigo_cuba: 'CB-02', nombre: 'Cuba CB-02' },
    { id: 3, codigo_cuba: 'CB-03', nombre: 'Cuba CB-03' }
  ]
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
  return cuba.value.variedad || 'Cabernet Sauvignon'
})

const cubaLote = computed(() => {
  if (!cuba.value) return '--'
  if (!tieneProcesoActivo.value) return 'Cuba Disponible'
  return cuba.value.lote || `Lote ${cuba.value.proceso_activo_id || 1}-2026`
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
  const min = cuba.value.temp_min_perfil ?? 16.0
  const max = cuba.value.temp_max_perfil ?? 26.0

  if (temp !== null && temp !== undefined && (temp < min || temp > max)) {
    return 'warning'
  }
  return 'optimal'
})

const statusLabel = computed(() => {
  switch (statusOperativo.value) {
    case 'disponible':
      return 'Disponible · Sin Fermentación Activa'
    case 'warning':
      return 'Alerta · Desviación de Parámetros'
    case 'optimal':
      return 'Normal · Fermentación Activa'
    default:
      return 'Monitoreo en Curso'
  }
})

const alertReason = computed(() => {
  if (!tieneProcesoActivo.value || !cuba.value) return null
  const temp = temperaturaActual.value
  const min = cuba.value.temp_min_perfil ?? 16.0
  const max = cuba.value.temp_max_perfil ?? 26.0

  if (temp !== null && temp !== undefined) {
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

const tempChangeText = computed(() => {
  const temps = historico.value?.temp || historico.value?.temperaturas_vino || []
  if (temps.length >= 2) {
    const valid = temps.filter((t) => t !== null && t !== undefined)
    if (valid.length >= 2) {
      const last = valid[valid.length - 1]
      const prev = valid[Math.max(0, valid.length - 3)]
      const diff = last - prev
      return `${diff >= 0 ? '+' : ''}${diff.toFixed(1)}°C en últimas lecturas`
    }
  }
  return 'Estable en últimas lecturas'
})

const brixDeltaText = computed(() => {
  const brixs = historico.value?.brix || historico.value?.grados_brix || []
  if (brixs.length >= 2) {
    const valid = brixs.filter((b) => b !== null && b !== undefined)
    if (valid.length >= 2) {
      const diff = valid[valid.length - 1] - valid[0]
      return `${diff >= 0 ? '+' : ''}${diff.toFixed(1)} °Bx en ${activeTimeRangeLabel.value}`
    }
  }
  return 'Sin variación relevante'
})

const tiltAngleCalculado = computed(() => {
  if (brixActual.value !== null && brixActual.value !== undefined) {
    const brix = Number(brixActual.value)
    return (22 + brix * 1.7).toFixed(1) + '°'
  }
  return '--'
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
function construirDatasets(data) {
  if (!chartCanvasRef.value) return []
  const ctx = chartCanvasRef.value.getContext('2d')

  // Gradiente suave de temperatura
  const tempGrad = ctx.createLinearGradient(0, 0, 0, 260)
  tempGrad.addColorStop(0, 'rgba(118, 31, 51, 0.25)')
  tempGrad.addColorStop(1, 'rgba(118, 31, 51, 0.02)')

  // Gradiente suave de brix
  const brixGrad = ctx.createLinearGradient(0, 0, 0, 260)
  brixGrad.addColorStop(0, 'rgba(196, 127, 23, 0.25)')
  brixGrad.addColorStop(1, 'rgba(196, 127, 23, 0.02)')

  // Gradiente suave de pH
  const phGrad = ctx.createLinearGradient(0, 0, 0, 260)
  phGrad.addColorStop(0, 'rgba(107, 33, 168, 0.25)')
  phGrad.addColorStop(1, 'rgba(107, 33, 168, 0.02)')

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
      label: 'Temperatura DS18B20 (°C)',
      data: tempData,
      borderColor: '#761F33',
      backgroundColor: tempGrad,
      borderWidth: 2.5,
      tension: 0.3,
      pointRadius: isDense ? 0 : 3,
      pointHoverRadius: 6,
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
      data: brixData,
      borderColor: '#C47F17',
      backgroundColor: brixGrad,
      borderWidth: 2.5,
      borderDash: [5, 4],
      tension: 0.3,
      pointRadius: isDense ? 0 : 3,
      pointHoverRadius: 6,
      pointBackgroundColor: '#FFFFFF',
      pointBorderColor: '#C47F17',
      pointBorderWidth: 2,
      fill: true,
      yAxisID: activeChartTab.value === 'both' ? 'yBrix' : 'yTemp'
    })
  }

  if (activeChartTab.value === 'ph') {
    datasets.push({
      label: 'pH PH-4502C',
      data: phData,
      borderColor: '#6B21A8',
      backgroundColor: phGrad,
      borderWidth: 2.5,
      tension: 0.3,
      pointRadius: isDense ? 0 : 3,
      pointHoverRadius: 6,
      pointBackgroundColor: '#FFFFFF',
      pointBorderColor: '#6B21A8',
      pointBorderWidth: 2,
      fill: true,
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
      grid: { color: 'rgba(232, 224, 221, 0.6)' },
      ticks: {
        color: '#66525B',
        font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 },
        maxRotation: 45,
        autoSkip: true,
        maxTicksLimit: 12
      }
    },
    yTemp: {
      type: 'linear',
      position: 'left',
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
          titleFont: { size: 12, weight: 'bold' }
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

  const labels =
    data?.labels && data.labels.length > 0
      ? data.labels
      : data?.timestamps || []

  const tempData =
    data?.temp && data.temp.length > 0
      ? data.temp
      : data?.temperaturas_vino || []

  const brixData =
    data?.brix && data.brix.length > 0
      ? data.brix
      : data?.grados_brix || []

  const phData = data?.valores_ph || []

  // Actualizar labels del eje X
  chartInstance.data.labels = labels

  const isBoth = activeChartTab.value === 'both'
  const isTemp = activeChartTab.value === 'temp'
  const isBrix = activeChartTab.value === 'brix'
  const isPh = activeChartTab.value === 'ph'

  const expectedDatasetsCount = isBoth ? 2 : 1

  // Reconstruir si la cantidad de series no coincide con el tab activo
  if (chartInstance.data.datasets.length !== expectedDatasetsCount) {
    chartInstance.data.datasets = construirDatasets(data)
  } else {
    // Actualizar directamente los arrays de datos en la instancia
    if (isBoth) {
      if (chartInstance.data.datasets[0]) chartInstance.data.datasets[0].data = tempData
      if (chartInstance.data.datasets[1]) chartInstance.data.datasets[1].data = brixData
    } else if (isTemp) {
      if (chartInstance.data.datasets[0]) chartInstance.data.datasets[0].data = tempData
    } else if (isBrix) {
      if (chartInstance.data.datasets[0]) chartInstance.data.datasets[0].data = brixData
    } else if (isPh) {
      if (chartInstance.data.datasets[0]) chartInstance.data.datasets[0].data = phData
    }
  }

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
  activeTimeRange.value = nuevoRango
  const horas = rangoToHoras(nuevoRango)
  chartLoading.value = true

  try {
    // Dispara nueva petición cambiando rango_horas y actualiza cuba en paralelo
    const [cubaData, historicoData] = await Promise.all([
      cubaService.obtenerCuba(selectedCubaId.value),
      cubaService.obtenerHistorico(selectedCubaId.value, horas)
    ])

    cuba.value = cubaData
    historico.value = historicoData
    lastSyncTime.value = new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

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
    chartLoading.value = false
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
  if (loading.value || chartLoading.value || !selectedCubaId.value) return

  try {
    const horas = rangoToHoras(activeTimeRange.value)
    const [cubaData, historicoData] = await Promise.all([
      cubaService.obtenerCuba(selectedCubaId.value),
      cubaService.obtenerHistorico(selectedCubaId.value, horas)
    ])

    const prevTemp = temperaturaActual.value
    const prevBrix = brixActual.value

    cuba.value = cubaData
    historico.value = historicoData
    lastSyncTime.value = new Date().toLocaleTimeString('es-CL', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })

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
  }
}

// ==========================================
// CARGA DE DATOS EN PARALELO (CRITERIO 2)
// ==========================================
async function cargarAlertasCuba(id) {
  try {
    const data = await alertService.listarAlertas({ cuba_id: id, limit: 10 })
    alertasCuba.value = Array.isArray(data) ? data : data?.alertas || []
  } catch (err) {
    console.warn('No se pudieron cargar alertas de la cuba:', err)
    alertasCuba.value = []
  }
}

async function cargarDatosCuba(id, rangoHoras = 24) {
  loading.value = true
  error.value = null

  try {
    // Invocación en paralelo con Promise.all según Criterio de Aceptación 2
    const [cubaData, historicoData] = await Promise.all([
      cubaService.obtenerCuba(id),
      cubaService.obtenerHistorico(id, rangoHoras)
    ])

    cuba.value = cubaData
    historico.value = historicoData
    lastSyncTime.value = new Date().toLocaleTimeString('es-CL', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })

    // Cargar alertas asociadas de forma asíncrona
    cargarAlertasCuba(id)

    await nextTick()
    await renderChart()
  } catch (err) {
    console.error('Error al cargar datos de la cuba:', err)
    error.value = err.message || 'Error de comunicación al consultar los datos de la cuba'
  } finally {
    loading.value = false
  }
}

async function cargarListaCubas() {
  try {
    const lista = await cubaService.listarCubas()
    if (Array.isArray(lista) && lista.length > 0) {
      cubasDisponibles.value = lista
    }
  } catch (err) {
    console.warn('No se pudo listar cubas para el selector:', err)
  }
}

async function inicializarVista() {
  await cargarListaCubas()

  const rawId = route.params.id || route.query.id
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
                <option v-for="c in cubasList" :key="c.id" :value="c.id">
                  {{ c.nombre || `Cuba ${c.codigo_cuba || c.codigo || c.id}` }}
                </option>
              </select>
              <ChevronDown :size="18" class="select-chevron" />
            </div>
            <p class="cuba-subtitle">
              {{ cubaVariedad }} · {{ cubaLote }} · Monitoreo de Fermentación
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

          <span v-if="lastSyncTime" class="sync-badge">
            <Radio :size="12" class="sync-icon-pulse" />
            <span>En vivo ({{ lastSyncTime }})</span>
          </span>

          <button
            class="btn-refresh"
            :disabled="loading || chartLoading"
            @click="cargarDatosCuba(selectedCubaId, rangoToHoras(activeTimeRange))"
            title="Actualizar datos y telemetría"
          >
            <RefreshCw :size="15" :class="{ spin: loading || chartLoading }" />
            <span>Actualizar</span>
          </button>

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
        </div>

        <div class="days-tracker">
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
        <h4>Alerta por Regla Térmica Enológica</h4>
        <p>{{ alertReason }}</p>
      </div>
    </div>

    <!-- Paneles de métricas de telemetría IoT -->
    <section class="metrics-grid">
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
            {{ temperaturaActual !== null ? temperaturaActual.toFixed(1) : '--' }}
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
                : '16.0°C a 26.0°C'
            }}
          </span>
        </div>
      </div>

      <!-- 2. Sensor MPU-6050: Inclinación y Brix -->
      <div class="metric-card" :class="{ 'card-flash': flashUpdate }">
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
          <span class="metric-number">
            {{ brixActual !== null ? brixActual.toFixed(1) : '--' }}
          </span>
          <span class="metric-unit">°Bx</span>
        </div>

        <div class="metric-details">
          <div class="tilt-info">
            <span>Inclinación calculada:</span>
            <strong>{{ tiltAngleCalculado }}</strong>
          </div>
          <span class="metric-subtext">Ritmo: {{ brixDeltaText }}</span>
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
            :class="{
              'metric-icon-good': statusOperativo === 'optimal',
              'metric-icon-warn': statusOperativo === 'warning',
              'metric-icon-neutral': statusOperativo === 'disponible' || statusOperativo === 'loading'
            }"
          >
            <Activity :size="22" />
          </div>
        </div>

        <div class="metric-val-group">
          <span
            class="status-summary-text"
            :class="{
              'summary-optimal': statusOperativo === 'optimal',
              'summary-warning': statusOperativo === 'warning',
              'summary-neutral': statusOperativo === 'disponible'
            }"
          >
            {{
              !tieneProcesoActivo
                ? 'Cuba Disponible'
                : statusOperativo === 'optimal'
                ? 'Fermentación Normal'
                : 'Riesgo / Desviación'
            }}
          </span>
        </div>

        <div class="metric-details">
          <p class="rule-explanation">
            {{
              !tieneProcesoActivo
                ? 'Cuba en reposo o higienización, lista para recibir una nueva vendimia.'
                : statusOperativo === 'optimal'
                ? 'El consumo de azúcar es continuo y la temperatura se mantiene estable dentro de la banda enológica.'
                : 'Se detectó variación térmica o estancamiento de azúcar fuera del perfil óptimo.'
            }}
          </p>

          <div class="card-action-bar">
            <button
              v-if="!tieneProcesoActivo"
              class="btn-card-action btn-card-action--start"
              :disabled="!estaDisponible"
              @click="abrirModalIniciar"
            >
              <Play :size="13" />
              <span>{{ estaDisponible ? 'Iniciar Fermentación' : 'Cuba No Disponible' }}</span>
            </button>
            <button
              v-else
              class="btn-card-action btn-card-action--finish"
              @click="abrirModalFinalizar"
            >
              <Square :size="13" />
              <span>Finalizar Fermentación</span>
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- Gráficos de Telemetría Chart.js -->
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
              @click="cambiarTabGrafico('both')"
            >
              Ambos Sensores
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'temp' }"
              @click="cambiarTabGrafico('temp')"
            >
              Solo Temperatura
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'brix' }"
              @click="cambiarTabGrafico('brix')"
            >
              Solo Brix
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeChartTab === 'ph' }"
              @click="cambiarTabGrafico('ph')"
            >
              Solo pH
            </button>
          </div>

          <!-- Filtro de tiempo con petición dinámica a la API -->
          <div class="btn-group">
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '24h' }"
              :disabled="chartLoading"
              @click="cambiarRangoHoras('24h')"
            >
              24 Horas
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '48h' }"
              :disabled="chartLoading"
              @click="cambiarRangoHoras('48h')"
            >
              48 Horas
            </button>
            <button
              class="btn-filter"
              :class="{ active: activeTimeRange === '7d' }"
              :disabled="chartLoading"
              @click="cambiarRangoHoras('7d')"
            >
              7 Días
            </button>
          </div>
        </div>
      </div>

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

      <div class="chart-legend-box">
        <div class="legend-item">
          <span class="legend-color legend-temp"></span>
          <span><strong>Temperatura (°C):</strong> Curva del sensor sumergible DS18B20.</span>
        </div>
        <div class="legend-item">
          <span class="legend-color legend-brix"></span>
          <span><strong>Azúcar (°Bx):</strong> Grados Brix calculados por el flotador MPU-6050.</span>
        </div>
        <div
          class="legend-item"
          v-if="activeChartTab === 'ph' || (historico?.valores_ph && historico.valores_ph.length > 0)"
        >
          <span class="legend-color legend-ph"></span>
          <span><strong>Acidez (pH):</strong> Sensor de pH sumergible PH-4502C.</span>
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

.status-pill--neutral {
  background-color: #f1f3f5;
  color: #495057;
  border: 1px solid #ced4da;
}
.status-pill--neutral .status-dot {
  background-color: #868e96;
}

.days-tracker {
  font-size: 0.78rem;
  color: var(--text-secondary);
  font-weight: 500;
}

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
  background-color: #761f33;
}

.legend-brix {
  background-color: #c47f17;
}

.legend-ph {
  background-color: #6b21a8;
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
</style>
