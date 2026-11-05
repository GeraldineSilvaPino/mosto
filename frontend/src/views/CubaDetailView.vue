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
  Radio
} from 'lucide-vue-next'

import { Chart as ChartJS, registerables } from 'chart.js'
import cubaService from '../services/cubaService'
import alertService from '../services/alertService'

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

onBeforeUnmount(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
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
</style>
