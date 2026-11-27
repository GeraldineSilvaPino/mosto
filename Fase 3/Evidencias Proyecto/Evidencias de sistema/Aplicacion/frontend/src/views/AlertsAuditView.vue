<script setup>
/**
 * 📋 11. [FRONT - VUE] Pantalla de Historial de Alertas / Auditoría
 * Módulo 5: Administración SaaS y Gestión de Empresa
 *
 * Integración Backend Real (TASK-FE-INT2):
 * 1. KPIs globales y MTTR oficial desde GET /api/alertas/metricas?cuba_id= mediante alertService.obtenerMetricas().
 * 2. Visualización reactiva en tarjetas superiores:
 *    - MTTR Promedio (mttr_promedio_minutos en min).
 *    - Tasa de Resolución (tasa_resolucion_pct en %).
 *    - Total de Alertas Activas y Alertas Críticas.
 * 3. Bitácora histórica cronológica conectada a GET /api/alertas con fallback resiliente.
 * 4. Ficha de detalle de auditoría con formulario y botón "Resolver Incidencia".
 * 5. Consumo de PATCH /api/alertas/{id}/resolver con { nota_resolucion: "..." }.
 * 6. Actualización automática de estado a "resuelta" y recálculo automático de KPIs MTTR.
 * 7. Exportación oficial de bitácora CSV vía backend GET /api/alertas/exportar con fallback local.
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import {
  ShieldCheck,
  FileSpreadsheet,
  Calendar,
  Filter,
  Search,
  X,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  Clock,
  User,
  Cylinder,
  Thermometer,
  Compass,
  Eye,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Info,
  Check,
  Download,
  Layers,
  ArrowUpDown,
  RefreshCw
} from 'lucide-vue-next'
import alertService from '../services/alertService'
import binnacleService from '../services/binnacleService'
import EpisodeEvidence from '../components/EpisodeEvidence.vue'
import cubaService from '../services/cubaService'

// ==========================================
// Auditoría respaldada exclusivamente por respuestas del servidor.
const auditLogs = ref([])
const hasLoadedLogs = ref(false)
const cubasList = ref([])
const isLoading = ref(false)
const loadError = ref('')
const metricsError = ref('')
const isResolving = ref(false)
const isAttending = ref(false)
const isSavingNote = ref(false)
const isSaving = computed(() => isResolving.value || isAttending.value || isSavingNote.value)
const followupNote = ref('')
const noteError = ref('')
const attendError = ref('')
const evidenceRevision = ref(0)
const isExporting = ref(false)
const resolveError = ref(null)
const resolutionNoteInput = ref('')
const toastMessage = ref('')

// Métricas de Auditoría calculadas por el Backend (Fórmula oficial MTTR)
const metricas = ref({
  total_alertas: null,
  alertas_activas: null,
  alertas_criticas: null,
  total_resueltas: null,
  mttr_promedio_minutos: null,
  tasa_resolucion_pct: null
})

// Filtros y búsqueda
const filtersOpen = ref(false)
const searchQuery = ref('')
const datePreset = ref('all') // all | 7d | vintage
const filterSeverity = ref('all')
const filterResolution = ref('all') // all | resolved | mitigated | pending | false_alarm
const filterCuba = ref('all')

// Modal de detalle y resolución
const isAuditModalOpen = ref(false)
const selectedIncident = ref(null)

// ==========================================
// FUNCIONES AUXILIARES DE FORMATEO Y MAPEO
// ==========================================
function formatDateTime(isoString) {
  if (!isoString) return '-'
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return isoString
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    return `${yyyy}-${mm}-${dd} ${hh}:${min}`
  } catch {
    return isoString
  }
}

function mapBackendAlertToAudit(dto) {
  // Normalizar severidad
  let severity = 'info'
  let severityLabel = 'Informativa'
  const sevLower = (dto.severidad || '').toLowerCase()
  if (sevLower === 'critica' || sevLower === 'danger') {
    severity = 'danger'
    severityLabel = 'Crítica'
  } else if (sevLower === 'alta') {
    severity = 'danger'
    severityLabel = 'Alta'
  } else if (sevLower === 'media' || sevLower === 'warning') {
    severity = 'warning'
    severityLabel = 'Advertencia'
  } else if (sevLower === 'baja' || sevLower === 'info') {
    severity = 'info'
    severityLabel = 'Baja'
  }

  // Normalizar estado y resolución
  let status = 'active'
  let statusLabel = 'Pendiente'
  let resolutionType = 'pending'
  let resolutionLabel = 'Pendiente'
  const stLower = (dto.estado || '').toLowerCase()
  if (stLower === 'resuelta' || stLower === 'resolved') {
    status = 'resolved'
    statusLabel = 'Resuelta'
    resolutionType = 'resolved'
    resolutionLabel = 'Resuelta'
  } else if (stLower === 'atendida' || stLower === 'in_progress') {
    status = 'in_progress'
    statusLabel = 'En Protocolo'
    resolutionType = 'mitigated'
    resolutionLabel = 'En Protocolo'
  }

  // Sensor
  let sensorType = 'DS18B20'
  let sensorName = 'Sonda Térmica Central'
  const rawType = (dto.sensor_tipo || dto.tipo_alerta || '').toUpperCase()
  if (rawType.includes('MPU') || rawType.includes('BRIX') || rawType.includes('FLOTADOR')) {
    sensorType = 'MPU-6050'
    sensorName = 'Cápsula Flotante Inclinómetro'
  } else if (rawType.includes('PH')) {
    sensorType = 'PH-4502C'
    sensorName = 'Sonda de pH Analógica'
  }

  // Tiempo de resolución en minutos si está resuelta
  let resolutionTimeMin = null
  if (dto.timestamp && dto.fecha_resolucion) {
    const diffMs = new Date(dto.fecha_resolucion) - new Date(dto.timestamp)
    if (Number.isFinite(diffMs) && diffMs >= 0) resolutionTimeMin = Number((diffMs / 60000).toFixed(1))
  }

  // Línea de tiempo
  const timeline = []
  if (dto.timestamp) {
    timeline.push({
      time: formatDateTime(dto.timestamp),
      author: 'Sistema Telemetría',
      text: dto.descripcion || `Disparo automático de alerta (${dto.tipo_alerta || 'desvío enológico'}).`
    })
  }
  if (dto.fecha_atencion || dto.nota_atencion) {
    timeline.push({
      time: dto.fecha_atencion
        ? formatDateTime(dto.fecha_atencion)
        : 'En Protocolo',
      author: dto.operador_nombre || 'Sin identificación',
      text: dto.nota_atencion || 'Atención técnica iniciada e inspección de cuba.'
    })
  }
  if (dto.fecha_resolucion || dto.nota_resolucion) {
    timeline.push({
      time: dto.fecha_resolucion
        ? formatDateTime(dto.fecha_resolucion)
        : 'Resuelta',
      author: dto.resolvedor_nombre || 'Sin identificación',
      text: dto.nota_resolucion || 'Incidencia resuelta y protocolo completado satisfactoriamente.'
    })
  }

  const cubaCode = dto.cuba_codigo || (dto.cuba_id ? `CB-${String(dto.cuba_id).padStart(2, '0')}` : 'CB-01')
  const cubaName = dto.cuba_nombre || `Cuba ${cubaCode}`

  return {
    id: `INC-${String(dto.id).padStart(4, '0')}`,
    rawId: dto.id,
    cubaId: String(dto.cuba_id || '1'),
    cubaCode,
    cubaName,
    variety: dto.variedad || 'Sin variedad registrada',
    lot: dto.fermentacion_id ? `Proceso #${dto.fermentacion_id}` : 'Sin proceso vinculado',
    sensorType,
    sensorName,
    severity,
    severityLabel,
    title: dto.titulo || (dto.tipo_alerta ? `Alerta: ${dto.tipo_alerta.replace(/_/g, ' ')}` : 'Desvío enológico'),
    triggerValue: dto.met_dispar ? `Lectura: ${dto.met_dispar}` : 'Desvío de parámetro',
    thresholdRule: dto.descripcion || 'Regla de perfil de fermentación',
    detectedAt: formatDateTime(dto.timestamp),
    detectedAtRaw: dto.timestamp,
    resolvedAt: dto.fecha_resolucion ? formatDateTime(dto.fecha_resolucion) : '-',
    resolvedAtRaw: dto.fecha_resolucion,
    resolutionTimeMin,
    status,
    statusBackend: dto.estado,
    resolutionType,
    resolutionLabel,
    resolvedBy: dto.resolvedor_nombre || (status === 'resolved' ? 'Sin identificación' : 'Sin resolución'),
    role: '',
    summaryResolution: dto.nota_resolucion || dto.nota_atencion || (status === 'resolved' ? 'Incidencia resuelta.' : 'Incidencia activa.'),
    nota_resolucion: dto.nota_resolucion || '',
    timeline,
    raw: dto
  }
}

// ==========================================
// CARGA DE DATOS Y CONSUMO DE ENDPOINTS
// ==========================================
let metricsGeneration = 0
async function loadMetricas() {
  const generation = ++metricsGeneration
  metricsError.value = ''
  try {
    const cubaIdParam = filterCuba.value !== 'all' ? filterCuba.value : null
    const data = await alertService.obtenerMetricas(cubaIdParam)
    if (generation !== metricsGeneration) return
    if (data) {
      metricas.value = {
        total_alertas: data.total_alertas ?? 0,
        alertas_activas: data.alertas_activas ?? 0,
        alertas_criticas: data.alertas_criticas ?? 0,
        total_resueltas: data.total_resueltas ?? 0,
        mttr_promedio_minutos: typeof data.mttr_promedio_minutos === 'number' ? Number(data.mttr_promedio_minutos.toFixed(1)) : null,
        tasa_resolucion_pct: typeof data.tasa_resolucion_pct === 'number' ? Number(data.tasa_resolucion_pct.toFixed(1)) : 0
      }
    }
  } catch (err) {
    if (generation !== metricsGeneration) return
    metricsError.value = 'Métricas no disponibles; no se pudo consultar el servidor.'
    metricas.value = { total_alertas: null, alertas_activas: null, alertas_criticas: null, total_resueltas: null, mttr_promedio_minutos: null, tasa_resolucion_pct: null }
  }
}

let incidentRevision = 0
async function loadData(showToastFeedback = false) {
  if (isLoading.value) return
  const revision = incidentRevision
  isLoading.value = true
  try {
    // 1. Cargar métricas oficiales calculadas por backend (GET /api/alertas/metricas)
    await loadMetricas()

    const pageSize = 500
    const alertsData = await alertService.listarAlertas({ limit: pageSize })
    if (!Array.isArray(alertsData)) throw new Error('Respuesta de auditoría inválida')
    const byId = new Map(alertsData.map(dto => [dto.id, dto]))
    // El turno también necesita las incidencias abiertas antes de la ventana reciente.
    if (alertsData.length === pageSize) {
      for (const estado of ['pendiente', 'atendida']) {
        let offset = 0
        let page
        do {
          page = await alertService.listarAlertas({ estado, limit: pageSize, offset })
          for (const dto of page) byId.set(dto.id, dto)
          offset += page.length
        } while (page.length === pageSize)
      }
    }
    if (revision !== incidentRevision) return
    auditLogs.value = Array.from(byId.values(), mapBackendAlertToAudit)
    hasLoadedLogs.value = true
    loadError.value = ''

    // 3. Cargar lista de cubas disponibles para el filtro
    try {
      const cubasData = await cubaService.listarCubas({ incluirPrediccion: false })
      if (Array.isArray(cubasData)) {
        cubasList.value = cubasData
      }
    } catch {
      // Ignorar si cubaService no responde
    }

    if (showToastFeedback) {
      showToast('Auditoría y métricas MTTR actualizadas.')
    }
  } catch (err) {
    loadError.value = auditLogs.value.length ? 'No se pudo actualizar la auditoría. Se muestra la última consulta.' : 'No se pudo consultar el historial. Usa Actualizar para reintentar.'
  } finally {
    isLoading.value = false
  }
}

let pollInterval = null

onMounted(() => {
  loadData()
  // Polling cada 15 segundos para sincronizar anomalías generadas por el simulador IoT
  pollInterval = setInterval(() => {
    if (!isAuditModalOpen.value && !isResolving.value) {
      loadData(false)
    }
  }, 15000)
})

onBeforeUnmount(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})

// Recalcular métricas cuando cambia el filtro de cuba
watch(filterCuba, () => {
  loadMetricas()
})

// ==========================================
// FILTRADO Y COMPUTADOS DE VISTA
// ==========================================
const pendingCount = computed(() => auditLogs.value.filter(item =>
  item.resolutionType === 'pending' && (filterCuba.value === 'all' || item.cubaId === filterCuba.value)
).length)
const showingPending = computed(() => filterResolution.value === 'pending')
function togglePending() {
  const next = showingPending.value ? 'all' : 'pending'
  searchQuery.value = ''
  datePreset.value = filterSeverity.value = 'all'
  filterResolution.value = next
}
const filteredLogs = computed(() => {
  return auditLogs.value.filter(item => {
    // Buscador
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase()
      const match =
        item.id.toLowerCase().includes(q) ||
        (item.cubaName && item.cubaName.toLowerCase().includes(q)) ||
        (item.cubaCode && item.cubaCode.toLowerCase().includes(q)) ||
        (item.title && item.title.toLowerCase().includes(q)) ||
        (item.resolvedBy && item.resolvedBy.toLowerCase().includes(q)) ||
        (item.sensorType && item.sensorType.toLowerCase().includes(q))
      if (!match) return false
    }

    // Severidad
    if (filterSeverity.value !== 'all' && item.severity !== filterSeverity.value) {
      return false
    }

    // Resolución
    if (filterResolution.value !== 'all') {
      if (filterResolution.value === 'resolved' && item.resolutionType !== 'resolved') return false
      if (filterResolution.value === 'mitigated' && item.resolutionType !== 'mitigated') return false
      if (filterResolution.value === 'pending' && item.resolutionType !== 'pending') return false
      if (filterResolution.value === 'false_alarm' && item.resolutionType !== 'false_alarm') return false
    }

    // Cuba
    if (filterCuba.value !== 'all') {
      const targetCuba = String(filterCuba.value)
      if (item.cubaId !== targetCuba && item.cubaCode !== targetCuba) {
        return false
      }
    }

    // Rango de fechas (presets)
    if (datePreset.value === 'vintage' && new Date(item.detectedAtRaw).getFullYear() !== 2026) return false
    if (datePreset.value === '7d') {
      const age = Date.now() - new Date(item.detectedAtRaw).getTime()
      if (!Number.isFinite(age) || age < 0 || age > 7 * 86400000) return false
    }

    return true
  })
})

const journalFilterCount = computed(() => [datePreset, filterSeverity, filterResolution].filter(f => f.value !== 'all').length)
const hasFilters = computed(() => Boolean(searchQuery.value || [datePreset, filterSeverity, filterResolution, filterCuba].some(f => f.value !== 'all')))
function resetFilters() {
  searchQuery.value = ''
  datePreset.value = filterSeverity.value = filterResolution.value = filterCuba.value = 'all'
}
const displayMetric = value => value == null ? '—' : value.toLocaleString('es-CL')
const dateLabel = new Intl.DateTimeFormat('es-CL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
const journalDays = computed(() => {
  const days = new Map()
  const sorted = [...filteredLogs.value].sort((a, b) => b.detectedAt.localeCompare(a.detectedAt) || b.rawId - a.rawId)
  for (const log of sorted) {
    const key = log.detectedAt.slice(0, 10)
    if (!days.has(key)) {
      const date = new Date(log.detectedAtRaw)
      days.set(key, { key, label: log.detectedAtRaw && Number.isFinite(+date) ? dateLabel.format(date) : 'Fecha desconocida', rows: [] })
    }
    days.get(key).rows.push(log)
  }
  return [...days.values()]
})

// Cubas únicas disponibles para el selector
const cubasAvailable = computed(() => {
  const map = new Map()
  auditLogs.value.forEach(i => {
    if (i.cubaId && !map.has(String(i.cubaId))) {
      map.set(String(i.cubaId), { id: String(i.cubaId), code: i.cubaCode, name: i.cubaName })
    }
  })
  cubasList.value.forEach(c => {
    if (!map.has(String(c.id))) {
      map.set(String(c.id), { id: String(c.id), code: c.codigo_cuba || `CB-${c.id}`, name: c.nombre || `Cuba ${c.codigo_cuba}` })
    }
  })
  return Array.from(map.values())
})

// ==========================================
// ACCIONES Y RESOLUCIÓN DE INCIDENCIAS
// ==========================================
function showToast(msg) {
  toastMessage.value = msg
  setTimeout(() => {
    toastMessage.value = ''
  }, 4000)
}

const auditDialog = ref(null)
async function openAuditModal(item) {
  selectedIncident.value = item
  resolutionNoteInput.value = item.nota_resolucion || ''
  followupNote.value = ''
  attendError.value = noteError.value = ''
  resolveError.value = null
  isAuditModalOpen.value = true
  await nextTick()
  auditDialog.value?.showModal()
}

function closeAuditModal() {
  if (isSaving.value) return
  auditDialog.value?.close()
  isAuditModalOpen.value = false
  selectedIncident.value = null
  resolveError.value = null
  resolutionNoteInput.value = ''
}

function updateIncident(dto) {
  incidentRevision++
  const updated = mapBackendAlertToAudit(dto)
  const index = auditLogs.value.findIndex(item => item.rawId === dto.id)
  if (index >= 0) auditLogs.value[index] = updated
  selectedIncident.value = updated
  window.dispatchEvent(new Event('mosto:incident-updated'))
}

async function attendIncident() {
  if (isSaving.value || selectedIncident.value?.resolutionType !== 'pending') return
  isAttending.value = true
  attendError.value = ''
  try {
    updateIncident(await alertService.atender(selectedIncident.value.rawId))
    showToast('Atención registrada.')
  } catch (err) {
    attendError.value = err.message || 'No se pudo registrar la atención.'
  } finally {
    isAttending.value = false
  }
}

async function saveFollowupNote() {
  const message = followupNote.value.trim()
  if (isSaving.value || !selectedIncident.value || message.length < 2) return
  isSavingNote.value = true
  noteError.value = ''
  try {
    await binnacleService.registrarEntrada({ type: 'nota', message, alerta_id: selectedIncident.value.rawId })
    evidenceRevision.value++
    followupNote.value = ''
    showToast('Nota guardada en la bitácora.')
  } catch (err) {
    noteError.value = err.message || 'No se pudo guardar la nota.'
  } finally {
    isSavingNote.value = false
  }
}

async function resolveIncident() {
  if (!selectedIncident.value || isSaving.value) return

  const incidentRawId = selectedIncident.value.rawId || selectedIncident.value.id
  const numericId = typeof incidentRawId === 'number'
    ? incidentRawId
    : parseInt(String(incidentRawId).replace(/\D/g, ''), 10)

  const nota = resolutionNoteInput.value.trim()
  if (nota.length < 10) {
    resolveError.value = 'Describe la revisión y las acciones realizadas en al menos 10 caracteres.'
    return
  }
  isResolving.value = true
  resolveError.value = null
  try {
    if (!Number.isInteger(numericId) || numericId < 1) throw new Error('Identificador de incidencia inválido')
    updateIncident(await alertService.resolver(numericId, { nota_resolucion: nota }))

    // Actualizar los KPIs automáticamente desde el backend (Criterio 4)
    await loadMetricas()

    showToast('Incidencia resuelta formalmente y KPIs actualizados.')
  } catch (err) {
    console.error('Error al resolver alerta:', err)
    resolveError.value = err.message || 'Error al registrar la resolución en el servidor.'
    showToast('Error: ' + (err.message || 'No se pudo resolver la incidencia'))
  } finally {
    isResolving.value = false
  }
}

// Exportación a CSV oficial (GET /api/alertas/exportar) con feedback y fallback resiliente
async function exportToCSV() {
  if (isExporting.value) return
  isExporting.value = true
  try {
    if (searchQuery.value.trim() || datePreset.value !== 'all' || filterSeverity.value === 'danger') {
      exportToCSVClientFallback()
      return
    }
    const params = {}
    if (filterCuba.value !== 'all') {
      params.cuba_id = filterCuba.value
    }
    if (filterSeverity.value !== 'all') {
      params.severidad = filterSeverity.value === 'danger' ? 'critica' : (filterSeverity.value === 'warning' ? 'media' : 'baja')
    }
    if (filterResolution.value !== 'all') {
      if (filterResolution.value === 'resolved') params.estado = 'resuelta'
      else if (filterResolution.value === 'mitigated') params.estado = 'atendida'
      else if (filterResolution.value === 'pending') params.estado = 'pendiente'
    }
    const result = await alertService.exportarCsv(params)
    const exportedFilename = result?.filename || 'bitacora_alertas_export.csv'
    showToast(`Bitácora exportada exitosamente (${exportedFilename}).`)
  } catch (err) {
    console.warn('Fallo exportación remota CSV, utilizando exportación cliente fallback:', err)
    exportToCSVClientFallback()
  } finally {
    isExporting.value = false
  }
}

function exportToCSVClientFallback() {
  const headers = [
    'ID Incidencia',
    'Fecha Deteccion',
    'Cuba',
    'Variedad',
    'Lote',
    'Sensor',
    'Severidad',
    'Titulo Alerta',
    'Lectura Disparo',
    'Umbral',
    'Tiempo Resolucion (min)',
    'Tipo Resolucion',
    'Responsable'
  ]

  const rows = filteredLogs.value.map(i => [
    i.id,
    i.detectedAt,
    i.cubaCode,
    i.variety,
    i.lot,
    i.sensorType,
    i.severityLabel,
    i.title,
    i.triggerValue,
    i.thresholdRule,
    i.resolutionTimeMin ?? '',
    i.resolutionLabel,
    i.resolvedBy
  ])
  const quote = value => '"' + String(value).replaceAll('"', '""') + '"'
  const csvContent = '\uFEFF' + [headers, ...rows].map(row => row.map(quote).join(',')).join('\r\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const fallbackName = `bitacora_alertas_export_${new Date().toISOString().slice(0, 10)}.csv`
  alertService.descargarBlob(blob, fallbackName)

  showToast('Informe de auditoría exportado exitosamente en formato CSV.')
}
</script>

<template>
  <div class="view-container alerts-audit-view">
    <!-- Toast Flotante -->
    <transition name="toast-fade">
      <div v-if="toastMessage" class="toast-popup">
        <CheckCircle2 :size="16" />
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

    <header class="audit-head">
      <div><h1>Auditoría</h1><p>Incidencias y resoluciones de la bodega</p></div>
      <div class="head-actions">
        <button class="action" @click="loadData(true)" :disabled="isLoading"><RefreshCw :size="15" :class="{'spin-anim':isLoading}"/>Actualizar</button>
        <button class="action primary" @click="exportToCSV" :disabled="isExporting || (!auditLogs.length && isLoading)"><Download :size="15"/>{{ isExporting ? 'Exportando…' : 'Exportar CSV' }}</button>
      </div>
    </header>
    <p v-if="metricsError" role="alert" class="audit-load-error">{{ metricsError }}</p>
    <p v-if="loadError" role="alert" class="audit-load-error">{{ loadError }}</p>

    <section class="balance" aria-labelledby="balance-title">
      <div class="balance-lead">
        <h2 id="balance-title">Balance de resolución</h2>
        <strong>{{ displayMetric(metricas.tasa_resolucion_pct) }}<small v-if="metricas.tasa_resolucion_pct != null"> %</small></strong>
        <div class="ratio-track" aria-hidden="true"><i :style="{width: (metricas.tasa_resolucion_pct ?? 0) + '%'}"></i></div>
        <p v-if="metricas.total_alertas != null">{{ metricas.total_resueltas }} de {{ metricas.total_alertas }} incidencias resueltas</p>
      </div>
      <div class="balance-body">
        <label class="scope"><span>Historial completo de</span><span class="scope-picker"><select v-model="filterCuba" aria-label="Cuba"><option value="all">Todas las cubas</option><option v-for="c in cubasAvailable" :key="c.id" :value="c.id">{{ c.code }}</option></select><ChevronDown :size="15" aria-hidden="true"/></span></label>
        <dl><div><dt>Alertas activas</dt><dd>{{ displayMetric(metricas.alertas_activas) }}</dd></div><div><dt>Críticas activas</dt><dd>{{ displayMetric(metricas.alertas_criticas) }}</dd></div><div><dt>Tiempo medio de resolución</dt><dd>{{ displayMetric(metricas.mttr_promedio_minutos) }} <small v-if="metricas.mttr_promedio_minutos != null">min</small></dd></div></dl>
      </div>
    </section>

    <section class="ledger" aria-labelledby="ledger-title">
      <header class="ledger-head">
        <div>
          <h2 id="ledger-title">Registro cronológico</h2>
          <span class="journal-count" aria-live="polite">{{ filteredLogs.length }} {{ showingPending ? 'pendientes en la selección' : 'de ' + auditLogs.length + ' registros' }}</span>
        </div>
        <button type="button" class="action pending-shortcut" :aria-pressed="showingPending" @click="togglePending">
          <Clock :size="15" aria-hidden="true"/>Por atender
          <strong>{{ hasLoadedLogs ? pendingCount : '—' }}</strong>
        </button>
      </header>
      <div class="journal-filters" :class="{expanded: filtersOpen}">
        <label class="journal-search"><Search :size="16"/><input v-model="searchQuery" aria-label="Buscar incidencias" type="search" placeholder="Buscar en el registro"></label>
        <button type="button" class="filter-toggle action" :aria-expanded="filtersOpen" aria-controls="audit-filters" @click="filtersOpen = !filtersOpen"><Filter :size="14"/>Filtros<span v-if="journalFilterCount"> ({{ journalFilterCount }})</span></button>
        <div id="audit-filters" class="filter-options">
        <select aria-label="Periodo" v-model="datePreset"><option value="all">Todo el periodo</option><option value="7d">Últimos 7 días</option><option value="vintage">Temporada 2026</option></select>
        <select aria-label="Severidad" v-model="filterSeverity"><option value="all">Toda severidad</option><option value="danger">Críticas y altas</option><option value="warning">Advertencias</option><option value="info">Informativas</option></select>
        <select aria-label="Resolución" v-model="filterResolution"><option value="all">Toda resolución</option><option value="pending">Pendiente</option><option value="mitigated">En protocolo</option><option value="resolved">Resuelta</option></select>
        </div>
        <button v-if="hasFilters" class="reset" @click="resetFilters">Limpiar filtros</button>
      </div>
      <p v-if="!filteredLogs.length" class="ledger-empty">{{ isLoading && !hasLoadedLogs ? 'Consultando el historial…' : loadError && !hasLoadedLogs ? 'Historial no disponible' : showingPending && !pendingCount ? 'No quedan incidencias por atender.' : hasFilters ? 'Sin incidencias para esta búsqueda' : 'Todavía no hay incidencias registradas.' }}</p>
      <section v-for="day in journalDays" :key="day.key" class="ledger-day">
        <h3><Calendar :size="15"/>{{ day.label }}</h3>
        <ul>
          <li v-for="log in day.rows" :key="log.id">
            <button class="btn-view-audit journal-entry" @click="openAuditModal(log)" :aria-label="'Abrir ficha '+log.id+' · '+log.title">
              <span class="entry-time">{{ log.detectedAt.slice(11) || '—' }}<small>{{ log.id }}</small></span>
              <span class="entry-main"><strong>{{ log.title }}</strong><small>{{ log.cubaCode }} · {{ log.variety }} · {{ log.sensorType }}</small></span>
              <span class="badge-severity" :class="'badge-severity--'+log.severity">{{ log.severityLabel }}</span>
              <span class="entry-resolution"><span class="resolution-chip" :class="'resolution-chip--'+log.resolutionType">{{ log.resolutionLabel }}</span><small v-if="log.status==='resolved'">{{ log.resolvedBy }}<template v-if="log.resolutionTimeMin != null"> · {{ log.resolutionTimeMin }} min</template></small></span>
              <ChevronRight :size="17" aria-hidden="true" class="entry-arrow"/>
            </button>
          </li>
        </ul>
      </section>
    </section>
    <!-- MODAL DE FICHA DE AUDITORÍA -->
    <dialog v-if="isAuditModalOpen && selectedIncident" ref="auditDialog" class="audit-dialog" aria-labelledby="incident-title" @cancel.prevent="closeAuditModal" @click.self="closeAuditModal">
      <div class="audit-modal">
        <!-- Header Modal -->
        <div class="modal-header">
          <div class="modal-title-group">
            <div class="modal-icon-badge">
              <ShieldCheck :size="22" />
            </div>
            <div>
              <div class="modal-tag-row">
                <span class="id-modal-badge">{{ selectedIncident.id }}</span>
                <span
                  class="badge-severity"
                  :class="'badge-severity--' + selectedIncident.severity"
                >
                  {{ selectedIncident.severityLabel }}
                </span>
                <span
                  class="resolution-chip"
                  :class="'resolution-chip--' + selectedIncident.resolutionType"
                >
                  {{ selectedIncident.resolutionLabel }}
                </span>
              </div>
              <h2 id="incident-title" class="modal-title">{{ selectedIncident.title }}</h2>
            </div>
          </div>

          <button aria-label="Cerrar ficha" class="modal-close-btn" :disabled="isSaving" @click="closeAuditModal">
            <X :size="18" />
          </button>
        </div>

        <!-- Cuerpo del Modal -->
        <div class="modal-body">
          <div v-if="selectedIncident.resolutionType === 'pending'" class="attendance">
            <button class="action primary" :disabled="isSaving" @click="attendIncident">
              <Check :size="15" aria-hidden="true"/>{{ isAttending ? 'Registrando…' : 'Atender incidencia' }}
            </button>
            <span v-if="attendError" role="alert">{{ attendError }}</span>
          </div>
          <p v-else-if="selectedIncident.status === 'in_progress'" class="attendance-record" role="status">
            Atención registrada<span v-if="selectedIncident.raw.operador_nombre"> por {{ selectedIncident.raw.operador_nombre }}</span><span v-if="selectedIncident.raw.fecha_atencion"> · {{ formatDateTime(selectedIncident.raw.fecha_atencion) }}</span>
          </p>
          <EpisodeEvidence class="audit-evidence" :alert="selectedIncident.raw" :revision="evidenceRevision">
            <template #note-editor>
              <details v-if="selectedIncident.raw.fermentacion_id" class="followup-editor">
                <summary>Añadir nota de seguimiento</summary>
                <form @submit.prevent="saveFollowupNote">
                  <label>Observación de seguimiento
                    <textarea v-model="followupNote" rows="2" minlength="2" maxlength="4000" required :disabled="isSaving" />
                  </label>
                  <p v-if="noteError" role="alert">{{ noteError }}</p>
                  <button type="submit" :disabled="isSaving || followupNote.trim().length < 2">{{ isSavingNote ? 'Guardando…' : 'Guardar nota' }}</button>
                </form>
              </details>
              <p v-else>Las notas de bitácora requieren un proceso vinculado a la incidencia.</p>
            </template>
          </EpisodeEvidence>
          <!-- Datos del Tanque e Instalación -->
          <div class="audit-meta-grid">
            <div class="meta-box">
              <span class="meta-box-label">Cuba / Tanque:</span>
              <strong class="meta-box-val">{{ selectedIncident.cubaName }}</strong>
            </div>
            <div class="meta-box">
              <span class="meta-box-label">Lote Vinícola:</span>
              <strong class="meta-box-val">{{ selectedIncident.lot }}</strong>
            </div>
            <div class="meta-box">
              <span class="meta-box-label">Sensor Físico:</span>
              <strong class="meta-box-val">{{ selectedIncident.sensorType }} ({{ selectedIncident.sensorName }})</strong>
            </div>
            <div class="meta-box">
              <span class="meta-box-label">Tiempo de resolución</span>
              <strong class="meta-box-val">
                {{ selectedIncident.status === 'resolved' || selectedIncident.resolutionType === 'resolved'
                  ? `${selectedIncident.resolutionTimeMin == null ? 'Duración sin registrar' : selectedIncident.resolutionTimeMin + ' min'} (Cierre: ${selectedIncident.resolvedAt})`
                  : `En curso (Detección: ${selectedIncident.detectedAt})` }}
              </strong>
            </div>
          </div>

          <!-- Cuadro de Disparo de Alarma -->
          <div class="trigger-box">
            <div class="trigger-row">
              <span class="trigger-label">Lectura Telemétrica al Disparo:</span>
              <span class="trigger-highlight">{{ selectedIncident.triggerValue }}</span>
            </div>
            <div class="trigger-row">
              <span class="trigger-label">Regla de Umbral Infringida:</span>
              <span class="trigger-rule">{{ selectedIncident.thresholdRule }}</span>
            </div>
          </div>

          <!-- Caso 1: Incidencia ya resuelta -> Dictamen Final Registrado -->
          <div
            v-if="selectedIncident.status === 'resolved' || selectedIncident.resolutionType === 'resolved'"
            class="summary-action-box"
          >
            <span class="summary-action-title">Dictamen y Protocolo Aplicado:</span>
            <p class="summary-action-text">{{ selectedIncident.summaryResolution || selectedIncident.nota_resolucion || 'Incidencia resuelta y cerrada conforme a protocolo enológico.' }}</p>
            <div class="signature-row">
              <span class="signature-name">Firmado por: <strong>{{ selectedIncident.resolvedBy }}</strong></span>
              <span v-if="selectedIncident.resolvedAt && selectedIncident.resolvedAt !== '-'" class="signature-date"> · Fecha: {{ selectedIncident.resolvedAt }}</span>
            </div>
          </div>

          <!-- Caso 2: Incidencia activa/pendiente -> Formulario para Resolver Incidencia -->
          <div
            v-else
            class="resolve-section"
          >
            <div class="resolve-section-header">
              <div class="resolve-icon-badge">
                <CheckCircle2 :size="18" />
              </div>
              <div>
                <h4 class="resolve-section-title">Registrar Resolución Técnica</h4>
                <p class="resolve-section-desc">Ingrese el protocolo, acción correctiva o dictamen enológico aplicado en bodega para resolver formalmente esta incidencia.</p>
              </div>
            </div>
            <textarea
              aria-label="Nota de resolución" v-model="resolutionNoteInput" maxlength="4000"
              rows="3"
              class="resolve-textarea"
              placeholder="Describa la acción correctiva realizada (ej: purga de camisa de refrigeración, ajuste de consigna a 18°C, adición de nutrientes)..."
              :disabled="isSaving"
            ></textarea>
            <span v-if="resolveError" class="resolve-error-msg">{{ resolveError }}</span>
          </div>

          <!-- Línea de Tiempo de Intervención -->
          <div v-if="!selectedIncident.raw.version_regla" class="timeline-section">
            <h4 class="timeline-title">Línea de Tiempo y Trazabilidad Operativa</h4>
            <div class="audit-timeline">
              <div
                v-for="(step, idx) in selectedIncident.timeline"
                :key="idx"
                class="timeline-item"
              >
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                  <div class="timeline-meta">
                    <span class="timeline-author">{{ step.author }}</span>
                    <span class="timeline-time">{{ step.time }}</span>
                  </div>
                  <p class="timeline-desc">{{ step.text }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer Modal -->
        <div class="modal-footer">
          <button class="btn-secondary" @click="closeAuditModal" :disabled="isSaving">
            Cerrar Ficha
          </button>
          <button
            v-if="selectedIncident.status !== 'resolved' && selectedIncident.resolutionType !== 'resolved'"
            class="btn-resolve"
            :disabled="isSaving"
            @click="resolveIncident"
          >
            <CheckCircle2 :size="16" />
            <span>{{ isResolving ? 'Resolviendo Incidencia...' : 'Resolver Incidencia' }}</span>
          </button>
        </div>
      </div>
    </dialog>
  </div>
</template>

<style scoped>
.audit-load-error { padding: 12px; color: #92400e; background: #fffbeb; border: 1px solid #f59e0b; border-radius: 8px; }
/* =========================================
   ESTILOS DE HISTORIAL DE ALERTAS / AUDITORÍA
   ========================================= */
.alerts-audit-view {
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
.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 1rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-secondary:hover:not(:disabled) {
  background-color: var(--bg-hover);
  border-color: var(--border-subtle);
}

.btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn-loading {
  pointer-events: none;
}

.spin-anim {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 1. KPIs Grid */
.badge-severity {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-full);
  white-space: nowrap;
}

.badge-severity--danger {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border: 1px solid var(--status-danger-border);
}

.badge-severity--warning {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
  border: 1px solid var(--status-warn-border);
}

.badge-severity--info {
  background-color: #E8F4FD;
  color: #1565C0;
  border: 1px solid #BBDEFB;
}

.user-cell {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-weight: 600;
  color: var(--text-primary);
}

.user-role {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.time-cell {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-secondary);
}

.resolution-chip {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

.resolution-chip--resolved {
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border: 1px solid var(--status-good-border);
}

.resolution-chip--mitigated {
  background-color: #E8F4FD;
  color: #1565C0;
  border: 1px solid #BBDEFB;
}

.resolution-chip--pending {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border: 1px solid var(--status-danger-border);
}

.resolution-chip--in_progress {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
  border: 1px solid var(--status-warn-border);
}

.resolution-chip--false_alarm {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
  border: 1px solid var(--status-warn-border);
}

.th-actions,
.td-actions {
  text-align: right;
}

.audit-modal {
  width: 100%;
  max-width: 680px;
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

@keyframes modal-pop {
  from { opacity: 0; transform: scale(0.96) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.modal-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.modal-title-group {
  display: flex;
  gap: 0.85rem;
}

.modal-icon-badge {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-sm);
  background-color: var(--wine-100);
  color: var(--wine-700);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.modal-tag-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.3rem;
}

.id-modal-badge {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--wine-900);
}

.modal-title {
  font-family: var(--font-serif);
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1.2;
}

.modal-close-btn {
  color: var(--text-muted);
  padding: 0.4rem;
  border-radius: var(--radius-sm);
  transition: color 0.15s ease;
  background: none;
  border: none;
  cursor: pointer;
}

.modal-close-btn:hover {
  color: var(--text-primary);
  background-color: var(--bg-subtle);
}

.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.audit-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1rem;
}

.meta-box {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.meta-box-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.meta-box-val {
  font-size: 0.84rem;
  color: var(--text-primary);
}

.trigger-box {
  background-color: var(--wine-50);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.trigger-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
}

.trigger-label {
  color: var(--text-secondary);
}

.trigger-highlight {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--wine-900);
}

.trigger-rule {
  font-family: var(--font-mono);
  color: var(--text-muted);
}

.summary-action-box {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.summary-action-title {
  font-size: 0.76rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--wine-800);
}

.summary-action-text {
  font-size: 0.84rem;
  color: var(--text-primary);
  line-height: 1.4;
}

.signature-row {
  margin-top: 0.4rem;
  padding-top: 0.4rem;
  border-top: 1px solid var(--border-subtle);
  font-size: 0.74rem;
  color: var(--text-muted);
}

.signature-name strong {
  color: var(--wine-900);
}

.signature-date {
  color: var(--text-muted);
}

/* Sección de Resolución Técnica */
.resolve-section {
  background: linear-gradient(180deg, var(--wine-50) 0%, var(--bg-surface) 100%);
  border: 1px solid var(--wine-200, #E0C8CF);
  border-radius: var(--radius-md);
  padding: 1.15rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.resolve-section-header {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
}

.resolve-icon-badge {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background-color: var(--status-good-bg);
  color: var(--status-good);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.resolve-section-title {
  font-size: 0.86rem;
  font-weight: 700;
  color: var(--wine-900);
  margin-bottom: 0.15rem;
}

.resolve-section-desc {
  font-size: 0.76rem;
  color: var(--text-secondary);
  line-height: 1.35;
}

.resolve-textarea {
  width: 100%;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background-color: var(--bg-canvas);
  font-family: inherit;
  font-size: 0.84rem;
  color: var(--text-primary);
  line-height: 1.4;
  resize: vertical;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.resolve-textarea:focus {
  outline: none;
  border-color: var(--wine-700);
  box-shadow: 0 0 0 3px rgba(107, 30, 49, 0.12);
  background-color: #FFFFFF;
}

.resolve-error-msg {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--status-danger);
}

/* Timeline Modal */
.timeline-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.timeline-title {
  font-family: var(--font-serif);
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--wine-900);
}

.audit-timeline {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  border-left: 2px solid var(--border-color);
  margin-left: 0.5rem;
  padding-left: 1rem;
}

.timeline-item {
  position: relative;
}

.timeline-dot {
  position: absolute;
  left: -1.35rem;
  top: 0.3rem;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background-color: var(--wine-700);
  border: 2px solid var(--bg-surface);
}

.timeline-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  margin-bottom: 0.15rem;
}

.timeline-author {
  font-weight: 600;
  color: var(--wine-900);
}

.timeline-time {
  color: var(--text-muted);
}

.timeline-desc {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.35;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.75rem;
  background-color: var(--bg-canvas);
}

.btn-resolve {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  background-color: var(--status-good, #2E7D32);
  color: #FFFFFF;
  border: 1px solid var(--status-good, #2E7D32);
  padding: 0.55rem 1.15rem;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-resolve:hover:not(:disabled) {
  background-color: #1B5E20;
  border-color: #1B5E20;
  box-shadow: 0 4px 12px rgba(46, 125, 50, 0.25);
}

.btn-resolve:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.alerts-audit-view {
  --display: 'Instrument Serif', Georgia, serif;
  --ink: #30232a;
  --muted: #675b60;
  --line: #dcd3ca;
  --paper: #fffdf9;
  --wine: #763c51;
  --wine-900: var(--ink);
  --wine-700: var(--wine);
  --wine-100: #f0e1e5;
  gap: 18px; max-width: 1540px; margin-inline: auto; color: var(--ink);
}
.audit-head,.head-actions,.ledger-head,.journal-filters,.journal-search,.scope,.action,.ledger-day h3 { display:flex; align-items:center; }
.audit-head,.ledger-head { justify-content:space-between; gap:12px; flex-wrap:wrap; }
.audit-head h1,.balance h2,.ledger-head h2,.modal-title { font:400 3.2rem/1.12 var(--display); letter-spacing:-.025em; }
.audit-head p,.ledger-head > span { font-size:.82rem; color:var(--muted); margin-top:4px; }
.head-actions { gap:8px; }
.action,.journal-filters select,.journal-search { min-height:38px; border:1px solid var(--line); border-radius:7px; background:var(--paper); color:var(--ink); font-size:.8rem; }
.action { gap:7px; padding:8px 13px; font-weight:600; }
.action.primary,.btn-resolve { background:var(--wine); color:white; border-color:var(--wine); }
.action:hover { border-color:var(--wine); }
.action:disabled { opacity:.65; }
.balance { display:grid; grid-template-columns:minmax(210px,.85fr) minmax(0,1.8fr); background:#efe8de; border-radius:14px; overflow:hidden; }
.balance-lead { padding:20px 24px; background:#32232d; color:#fff6ef; }
.balance h2,.ledger-head h2,.modal-title { font-size:1.9rem; }
.balance-lead strong { display:block; margin:8px 0; font:400 2.8rem/1.05 var(--display); }
.balance-lead small,.balance-body dd small { font:500 .95rem var(--font-sans); }
.balance-lead p { color:#e5cdd4; font-size:.78rem; margin-top:7px; }
.ratio-track { height:5px; background:#644652; overflow:hidden; border-radius:3px; }
.ratio-track i { display:block; height:100%; background:#e9aaa7; }
.balance-body { padding:18px 24px; align-self:center; }
.scope-picker { position:relative; display:inline-flex; max-width:100%; color:var(--wine); }
.scope-picker select { appearance:none; min-height:36px; max-width:100%; padding:0 22px 0 2px; border:none; border-bottom:1px solid #b798a3; border-radius:0; background:transparent; color:inherit; font:600 .91rem var(--font-sans); cursor:pointer; }
.scope-picker select:hover { border-bottom-color:var(--wine); }
.scope-picker select:focus-visible { outline:2px solid var(--wine); outline-offset:2px; }
.scope-picker svg { position:absolute; right:2px; top:50%; transform:translateY(-50%); pointer-events:none; }
.scope { gap:8px; color:var(--muted); font-size:.8rem; flex-wrap:wrap; }
.journal-filters select { padding:5px 8px; max-width:100%; }
.balance-body dl { display:grid; grid-template-columns:1fr 1fr 1.3fr; margin:14px 0 0; }
.balance-body dl div + div { padding-left:16px; border-left:1px solid #d3c6bc; }
.balance-body dt { font-size:.8rem; color:var(--muted); }
.balance-body dd { font:400 2.25rem/1.15 var(--display); margin:4px 0 0; }
.ledger { min-width:0; background:var(--paper); border:1px solid var(--line); border-radius:12px; overflow:hidden; }
.ledger-head { padding:17px 21px 10px; }
.journal-count, .attendance-record { font-size:.81rem; color:var(--muted); }
.pending-shortcut { color:var(--wine); }
.pending-shortcut strong { font-variant-numeric:tabular-nums; }
.pending-shortcut[aria-pressed="true"] { color:var(--paper); background:var(--wine); border-color:var(--wine); }
.attendance { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.attendance [role="alert"] { color:#902e42; font-size:.84rem; }
.followup-editor { margin:8px 0; }
.followup-editor form, .followup-editor label { display:grid; gap:6px; }
.followup-editor textarea { box-sizing:border-box; padding:10px; border:1px solid var(--line); border-radius:6px; resize:vertical; }
.followup-editor button:disabled { opacity:.55; cursor:default; }
.journal-filters { padding:3px 21px 15px; gap:8px; flex-wrap:wrap; }
.journal-search { gap:7px; padding:0 10px; min-width:0; flex:1 1 230px; color:var(--muted); }
.journal-search input { border:0; background:transparent; min-width:0; width:100%; height:36px; font-size:.8rem; }
.journal-search input::placeholder { color:var(--muted); }
.reset { text-decoration:underline; color:var(--wine); font-weight:600; font-size:.8rem; padding:5px; }
.ledger-day h3 { gap:8px; border-block:1px solid var(--line); background:#f4efe8; color:#604754; padding:8px 21px; font:600 .81rem var(--font-sans); }
.ledger-day ul { list-style:none; }
.ledger-day li+li { border-top:1px solid #ebe3dd; }
.journal-entry { display:grid; grid-template-columns:82px minmax(160px,1fr) minmax(80px,.25fr) minmax(100px,.3fr) 16px; gap:12px; text-align:left; align-items:center; width:100%; padding:13px 21px; color:var(--ink); }
.journal-entry:hover { background:#f9f3ed; }
.journal-entry:focus-visible { outline-offset:-3px; }
.entry-time { font-size:.9rem; font-variant-numeric:tabular-nums; }
.journal-entry small { display:block; color:var(--muted); font-weight:400; font-size:.75rem; margin-top:3px; }
.entry-main strong { font-size:.89rem; }
.entry-main,.entry-resolution { min-width:0; overflow-wrap:anywhere; }
.journal-entry .badge-severity { justify-self:start; }
.entry-arrow { color:var(--wine); }
.ledger-empty { padding:22px; border-top:1px solid var(--line); color:var(--muted); }
.audit-dialog { margin:auto; padding:0; width:min(680px,calc(100% - 24px)); max-height:94dvh; max-width:none; border:0; border-radius:12px; color:var(--ink); background:var(--paper); }
.audit-dialog::backdrop { background:rgba(40,25,34,.55); }
.audit-modal { max-height:94dvh; background:var(--paper); border:0; }
.modal-header { background:#f1e8df; }
.modal-title { margin-top:6px; }
.modal-close-btn { align-self:flex-start; }
.modal-tag-row,.modal-footer { flex-wrap:wrap; }
.resolve-section, .trigger-box { border:1px solid var(--line); background:#f6f0ea; }
@media(max-width:1100px) {
 .balance-body { padding:16px; }
 .journal-entry { grid-template-columns:75px minmax(120px,1fr) auto auto 14px; gap:9px; }
}
@media(max-width:750px) {
 .audit-head h1 { font-size:2.45rem; }
 .balance { grid-template-columns:1fr; }
 .balance-lead { padding:14px 16px; }
 .balance-lead strong { font-size:2.2rem; }
 .balance-body dl { gap:8px; }
 .balance-body dl div+div { padding-left:8px; }
 .balance-body dt { font-size:.76rem; }
 .ledger-head,.journal-filters { padding-inline:13px; }
 .journal-filters select { flex:1 1 95px; min-width:0; }
 .ledger-day h3 { padding-inline:13px; }
 .journal-entry { padding:13px; grid-template-columns:minmax(0,1fr) auto 12px; gap:7px; }
 .entry-time { grid-column:1/-1; display:flex; align-items:center; gap:8px; color:var(--muted); font-size:.78rem; }
 .entry-time small { margin:0; }
 .entry-main { grid-column:1/3; }
 .entry-arrow { grid-column:3; grid-row:2; }
 .entry-resolution { grid-column:2/4; justify-self:end; }
 .audit-meta-grid { grid-template-columns:1fr; }
 .modal-header,.modal-body,.modal-footer { padding:14px; }
 .modal-icon-badge { display:none; }
}
@media(max-width:380px) {
 .journal-filters select { flex-basis:100%; }
 .action { padding-inline:9px; }
 .balance-body dl { grid-template-columns:repeat(2,minmax(0,1fr)); }
 .balance-body dl div:last-child { grid-column:1/-1; padding:5px 0 0; border:0; }
}

.filter-options { display:flex; flex-wrap:wrap; gap:8px; }
.filter-toggle { display:none; }
.badge-severity--danger { color:#902e42; background:#f9e2e4; border-color:#efd0d7; }
.resolution-chip--pending { color:#754c1d; background:#f9ecd2; border-color:#edd8b3; }
.resolution-chip--mitigated { color:#694354; background:#f0e4e9; border-color:#dcc6d1; }
.resolution-chip--resolved { color:#345c40; background:#e5efdf; border-color:#cddfc8; }
@media(max-width:750px) {
  .filter-options { display:none; width:100%; }
  .expanded .filter-options { display:flex; }
  .journal-search { flex:1 1 110px; }
  .filter-toggle { display:inline-flex; }
  .balance-lead { display:grid; grid-template-columns:1fr auto; align-items:center; gap:4px 10px; }
  .balance-lead strong { margin:0; }
  .balance-lead p,.ratio-track { grid-column:1/-1; }
  .balance-lead h2 { font-size:1.5rem; }
  .balance-body { padding:12px 16px; }
  .balance-body dl { margin-top:9px; }
}

/* El expediente comparte el papel, la tinta y las reglas del registro de auditoría. */
.audit-evidence {
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--ink);
  overflow-wrap: anywhere;
}
.audit-evidence :deep(.evidence-title) {
  margin: 0 0 16px;
  font: 400 1.85rem/1.1 var(--display);
  letter-spacing: -.02em;
}
.audit-evidence :deep(.log-title) {
  color: var(--ink);
  margin: 14px 0 3px;
  font-size: .84rem;
}
.audit-evidence :deep(p), .audit-evidence :deep(li) {
  color: var(--muted);
  font-size: .84rem;
  line-height: 1.6;
}
.audit-evidence :deep(.episode-tags span) { color: var(--wine); background: #f2e8e7; }
.audit-evidence :deep(dl) {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  margin: 12px 0;
  padding-block: 12px;
  border-block: 1px solid var(--line);
}
.audit-evidence :deep(article) { border-color: var(--line); }
.audit-evidence :deep(:is(.interventions, .manual-measurements)) {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px 12px;
  margin: 18px 0 0;
  padding: 16px 0 0;
  background: transparent;
  color: inherit;
  border: 0;
  border-top: 1px solid var(--line);
  border-radius: 0;
}
.audit-evidence :deep(:is(.interventions, .manual-measurements) > *) { grid-column: 1 / -1; min-width: 0; }
.audit-evidence :deep(.panel-title) {
  grid-area: 1 / 1;
  margin: 0;
  font: 400 1.55rem/1.12 var(--display);
}
.audit-evidence :deep(button) {
  color: var(--wine);
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 10px;
  font: 600 .8rem/1.4 var(--font-sans);
}
.audit-evidence :deep(button:hover:enabled) { background: #f3ece6; }
.audit-evidence :deep(button.panel-refresh) {
  grid-area: 1 / 2;
  margin: 0;
  padding: 6px 0;
  border: 0;
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: #ba9da5;
}
.audit-evidence :deep(button.panel-refresh:hover:enabled) { background: transparent; text-decoration-color: currentColor; }
.audit-evidence :deep(details) { padding: 0; border: 0; }
.audit-evidence :deep(summary) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 38px;
  padding: 8px 12px;
  background: #f4efe8;
  color: var(--wine);
  font: 600 .84rem/1.45 var(--font-sans);
  border-radius: 5px;
  cursor: pointer;
  list-style: none;
}
.audit-evidence :deep(summary::-webkit-details-marker) { display: none; }
.audit-evidence :deep(summary::after) {
  content: '';
  width: 7px;
  height: 7px;
  flex: none;
  margin-right: 3px;
  border: solid currentColor;
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(45deg) translate(-1px, -1px);
}
.audit-evidence :deep(details[open] > summary::after) { transform: rotate(225deg); }
.audit-evidence :deep(summary:hover) { background: #ede4db; }
.audit-evidence :deep(form) {
  min-width: 0;
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
  margin: 14px 0 8px;
}
.audit-evidence :deep(label) { min-width: 0; color: var(--ink); font-size: .82rem; font-weight: 600; }
.audit-evidence :deep(:is(input, select, textarea)) {
  width: 100%;
  min-width: 0;
  background: var(--paper);
  border-color: #baaea6;
  color: var(--ink);
  font: 400 .88rem/1.5 var(--font-sans);
  caret-color: var(--wine);
}
.audit-evidence :deep(form > button) { justify-self: start; margin: 0; }
.audit-evidence :deep(form > button:not([type=button])) { color: var(--paper); border-color: var(--wine); background: var(--wine); padding: 9px 14px; }
.audit-evidence :deep(form > button:not([type=button]):hover:enabled) { background: #603044; }
.audit-evidence :deep(:focus-visible) { outline: 2px solid var(--wine); outline-offset: 2px; }
.audit-evidence :deep([role=alert]) { color: #902e42; }
.audit-evidence :deep(.empty-register) { font-size: .78rem; }
@media (max-width: 480px) {
  .audit-evidence :deep(:is(.interventions, .manual-measurements)) { grid-template-columns: minmax(0, 1fr); gap: 6px; }
  .audit-evidence :deep(button.panel-refresh) { grid-area: auto; justify-self: start; }
}

@media(prefers-reduced-motion:reduce) { .audit-modal,.spin-anim { animation:none; } }
</style>
