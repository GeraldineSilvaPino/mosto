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
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
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
  Info,
  Check,
  Download,
  Layers,
  ArrowUpDown,
  RefreshCw
} from 'lucide-vue-next'
import alertService from '../services/alertService'
import EpisodeEvidence from '../components/EpisodeEvidence.vue'
import cubaService from '../services/cubaService'

// ==========================================
// Auditoría respaldada exclusivamente por respuestas del servidor.
const auditLogs = ref([])
const cubasList = ref([])
const isLoading = ref(false)
const loadError = ref('')
const metricsError = ref('')
const isResolving = ref(false)
const isExporting = ref(false)
const resolveError = ref(null)
const resolutionNoteInput = ref('')
const toastMessage = ref('')

// Métricas de Auditoría calculadas por el Backend (Fórmula oficial MTTR)
const metricas = ref({
  total_alertas: 0,
  alertas_activas: 0,
  alertas_criticas: 0,
  total_resueltas: 0,
  mttr_promedio_minutos: null,
  tasa_resolucion_pct: 0
})

// Filtros y búsqueda
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
      time: new Date(dto.timestamp).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
      author: 'Sistema Telemetría',
      text: dto.descripcion || `Disparo automático de alerta (${dto.tipo_alerta || 'desvío enológico'}).`
    })
  }
  if (dto.fecha_atencion || dto.nota_atencion) {
    timeline.push({
      time: dto.fecha_atencion
        ? new Date(dto.fecha_atencion).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
        : 'En Protocolo',
      author: dto.operador_nombre || 'Sin identificación',
      text: dto.nota_atencion || 'Atención técnica iniciada e inspección de cuba.'
    })
  }
  if (dto.fecha_resolucion || dto.nota_resolucion) {
    timeline.push({
      time: dto.fecha_resolucion
        ? new Date(dto.fecha_resolucion).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
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
async function loadMetricas() {
  metricsError.value = ''
  try {
    const cubaIdParam = filterCuba.value !== 'all' ? filterCuba.value : null
    const data = await alertService.obtenerMetricas(cubaIdParam)
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
    metricsError.value = 'Métricas no disponibles; no se pudo consultar el servidor.'
    metricas.value = { total_alertas: null, alertas_activas: null, alertas_criticas: null, total_resueltas: null, mttr_promedio_minutos: null, tasa_resolucion_pct: null }
  }
}

async function loadData(showToastFeedback = false) {
  isLoading.value = true
  try {
    // 1. Cargar métricas oficiales calculadas por backend (GET /api/alertas/metricas)
    await loadMetricas()

    // 2. Cargar historial completo de alertas (GET /api/alertas)
    const alertsData = await alertService.listarAlertas({ limit: 500 })
    if (!Array.isArray(alertsData)) throw new Error('Respuesta de auditoría inválida')
    auditLogs.value = alertsData.map(mapBackendAlertToAudit)
    loadError.value = ''

    // 3. Cargar lista de cubas disponibles para el filtro
    try {
      const cubasData = await cubaService.listarCubas()
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
    loadError.value = 'No se pudo actualizar la auditoría. Los registros visibles corresponden a la última consulta exitosa.'
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
const filteredLogs = computed(() => {
  return auditLogs.value.filter(item => {
    // Buscador
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
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
    if (datePreset.value === '7d') {
      const age = Date.now() - new Date(item.detectedAtRaw).getTime()
      if (!Number.isFinite(age) || age < 0 || age > 7 * 86400000) return false
    }

    return true
  })
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

function openAuditModal(item) {
  selectedIncident.value = item
  resolutionNoteInput.value = item.nota_resolucion || ''
  resolveError.value = null
  isAuditModalOpen.value = true
}

function closeAuditModal() {
  if (isResolving.value) return
  isAuditModalOpen.value = false
  selectedIncident.value = null
  resolveError.value = null
  resolutionNoteInput.value = ''
}

// Acción: Resolver Incidencia (PATCH /api/alertas/{id}/resolver)
async function resolveIncident() {
  if (!selectedIncident.value) return

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
    const updated = mapBackendAlertToAudit(await alertService.resolver(numericId, { nota_resolucion: nota }))
    const targetIdx = auditLogs.value.findIndex(item => item.rawId === numericId)
    if (targetIdx !== -1) auditLogs.value[targetIdx] = updated
    selectedIncident.value = updated

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
    `"${(i.title || '').replace(/"/g, '""')}"`,
    `"${i.triggerValue || ''}"`,
    `"${i.thresholdRule || ''}"`,
    i.resolutionTimeMin ?? '',
    i.resolutionLabel ?? '',
    `"${i.resolvedBy || ''}"`
  ])

  const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\r\n')
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

    <!-- Header Principal -->
    <p v-if="metricsError" role="alert" class="audit-load-error">{{ metricsError }}</p>
    <p class="metrics-scope">Métricas del historial completo de la cuba seleccionada. La tabla muestra hasta 500 registros recientes; sus filtros de texto, severidad y fecha no modifican las métricas.</p>
    <p v-if="loadError" role="alert" class="audit-load-error">{{ loadError }}</p>
    <header class="audit-header">
      <div>
        <h1 class="view-title">Historial de Alertas y Auditoría</h1>
      </div>

      <div class="header-actions">
        <button
          class="btn-secondary"
          @click="loadData(true)"
          :disabled="isLoading"
          title="Recargar métricas MTTR y bitácora desde el backend"
        >
          <RefreshCw :size="16" :class="{ 'spin-anim': isLoading }" />
          <span>Actualizar</span>
        </button>

        <button
          class="btn-primary"
          @click="exportToCSV"
          :disabled="isExporting"
          :class="{ 'btn-loading': isExporting }"
          title="Descargar bitácora histórica en formato CSV para Excel"
        >
          <RefreshCw v-if="isExporting" :size="16" class="spin-anim" />
          <Download v-else :size="16" />
          <span>{{ isExporting ? 'Generando CSV...' : 'Exportar Bitácora CSV' }}</span>
        </button>
      </div>
    </header>

    <!-- Tarjetas KPIs de Auditoría (Cálculo Oficial Backend MTTR) -->
    <section class="kpi-grid">
      <!-- 1. MTTR Promedio -->
      <div class="kpi-card">
        <div class="kpi-top">
          <span class="kpi-label">MTTR Promedio</span>
          <div class="kpi-icon-box kpi-icon--time">
            <Clock :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ metricas.mttr_promedio_minutos ?? 'N/D' }} <span class="kpi-unit">min</span></div>
        <div class="kpi-sub">
          <span>Fórmula oficial MTTR calculada</span>
        </div>
      </div>

      <!-- 2. Tasa de Resolución -->
      <div class="kpi-card">
        <div class="kpi-top">
          <span class="kpi-label">Tasa de Resolución</span>
          <div class="kpi-icon-box kpi-icon--good">
            <ShieldCheck :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ metricas.tasa_resolucion_pct }}%</div>
        <div class="kpi-sub">
          <span>{{ metricas.total_resueltas }} de {{ metricas.total_alertas }} incidencias cerradas</span>
        </div>
      </div>

      <!-- 3. Alertas Activas -->
      <div class="kpi-card">
        <div class="kpi-top">
          <span class="kpi-label">Alertas Activas</span>
          <div class="kpi-icon-box kpi-icon--warn">
            <AlertTriangle :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ metricas.alertas_activas }}</div>
        <div class="kpi-sub">
          <span>Total de alertas en curso (pendientes + atendidas)</span>
        </div>
      </div>

      <!-- 4. Alertas Críticas -->
      <div class="kpi-card">
        <div class="kpi-top">
          <span class="kpi-label">Alertas Críticas</span>
          <div class="kpi-icon-box kpi-icon--danger">
            <AlertOctagon :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ metricas.alertas_criticas }}</div>
        <div class="kpi-sub">
          <span>Alertas críticas activas en curso</span>
        </div>
      </div>
    </section>

    <!-- Filtros y Búsqueda -->
    <section class="filters-bar">
      <!-- Buscador -->
      <div class="search-box">
        <Search :size="16" class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar por código (#INC-), cuba, enólogo, regla o sensor..."
          class="search-input"
        />
        <button v-if="searchQuery" @click="searchQuery = ''" class="clear-search-btn">
          <X :size="14" />
        </button>
      </div>

      <!-- Controles de Filtros -->
      <div class="filter-controls">
        <!-- Rango de Fechas Preset -->
        <select v-model="datePreset" class="select-filter">
          <option value="all">Rango: Toda la Vendimia</option>
          <option value="7d">Últimos 7 días</option>
          <option value="vintage">Temporada 2026</option>
        </select>

        <!-- Severidad -->
        <select v-model="filterSeverity" class="select-filter">
          <option value="all">Severidad: Todas</option>
          <option value="danger">Críticas / Altas</option>
          <option value="warning">Advertencias</option>
          <option value="info">Informativas</option>
        </select>

        <!-- Tipo de Resolución -->
        <select v-model="filterResolution" class="select-filter">
          <option value="all">Resolución: Todas</option>
          <option value="resolved">Resuelta</option>
          <option value="mitigated">En Protocolo</option>
          <option value="pending">Pendiente</option>
          <option value="false_alarm">Sensor Descalibrado</option>
        </select>

        <!-- Cuba -->
        <select v-model="filterCuba" class="select-filter">
          <option value="all">Cuba: Todas</option>
          <option v-for="cuba in cubasAvailable" :key="cuba.id" :value="cuba.id">
            {{ cuba.code }}
          </option>
        </select>

        <!-- Reset -->
        <button
          v-if="searchQuery || datePreset !== 'all' || filterSeverity !== 'all' || filterResolution !== 'all' || filterCuba !== 'all'"
          class="btn-reset-filters"
          @click="searchQuery = ''; datePreset = 'all'; filterSeverity = 'all'; filterResolution = 'all'; filterCuba = 'all'"
        >
          Limpiar filtros
        </button>
      </div>
    </section>

    <!-- Tabla de Auditoría Histórica -->
    <section class="audit-table-card">
      <div class="table-header-info">
        <h3 class="table-title">Registro Cronológico de Alertas</h3>
        <span class="table-count">Mostrando {{ filteredLogs.length }} de {{ auditLogs.length }} registros</span>
      </div>

      <div class="table-responsive">
        <table class="audit-table">
          <thead>
            <tr>
              <th>ID & Detección</th>
              <th>Cuba & Cepa</th>
              <th>Sensor</th>
              <th>Anomalía Detectada</th>
              <th>Severidad</th>
              <th>Enólogo Responsable</th>
              <th>Tiempo</th>
              <th>Dictamen</th>
              <th class="th-actions">Ficha</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="filteredLogs.length === 0">
              <td colspan="9" class="td-empty">
                No se encontraron registros de auditoría con los filtros aplicados.
              </td>
            </tr>

            <tr
              v-for="log in filteredLogs"
              :key="log.id"
              class="audit-row"
            >
              <!-- ID & Fecha -->
              <td>
                <span class="id-badge">{{ log.id }}</span>
                <span class="date-subtext">{{ log.detectedAt }}</span>
              </td>

              <!-- Cuba & Cepa -->
              <td>
                <div class="cuba-cell">
                  <span class="cuba-code-tag">{{ log.cubaCode }}</span>
                  <span class="cuba-variety">{{ log.variety }}</span>
                </div>
              </td>

              <!-- Sensor -->
              <td>
                <span class="sensor-tag">
                  <component :is="log.sensorType === 'DS18B20' ? Thermometer : Compass" :size="13" />
                  <span>{{ log.sensorType }}</span>
                </span>
              </td>

              <!-- Anomalía -->
              <td>
                <div class="anomaly-cell">
                  <span class="anomaly-title">{{ log.title }}</span>
                  <span class="anomaly-value">Disparo: <strong>{{ log.triggerValue }}</strong></span>
                </div>
              </td>

              <!-- Severidad -->
              <td>
                <span
                  class="badge-severity"
                  :class="'badge-severity--' + log.severity"
                >
                  {{ log.severityLabel }}
                </span>
              </td>

              <!-- Responsable -->
              <td>
                <div class="user-cell">
                  <span class="user-name">{{ log.resolvedBy }}</span>
                  <span class="user-role">{{ log.role }}</span>
                </div>
              </td>

              <!-- Tiempo -->
              <td>
                <span class="time-cell">{{ log.resolutionTimeMin !== null ? log.resolutionTimeMin + ' min' : 'N/D' }}</span>
              </td>

              <!-- Dictamen -->
              <td>
                <span
                  class="resolution-chip"
                  :class="'resolution-chip--' + log.resolutionType"
                >
                  {{ log.resolutionLabel }}
                </span>
              </td>

              <!-- Botón Ficha -->
              <td class="td-actions">
                <button
                  class="btn-view-audit"
                  @click="openAuditModal(log)"
                  title="Ver trazabilidad completa de esta incidencia"
                >
                  <Eye :size="15" />
                  <span>Ficha</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- MODAL DE FICHA DE AUDITORÍA -->
    <div v-if="isAuditModalOpen && selectedIncident" class="modal-backdrop" @click.self="closeAuditModal">
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
              <h2 class="modal-title">{{ selectedIncident.title }}</h2>
            </div>
          </div>

          <button class="modal-close-btn" @click="closeAuditModal">
            <X :size="18" />
          </button>
        </div>

        <!-- Cuerpo del Modal -->
        <div class="modal-body">
          <EpisodeEvidence :alert="selectedIncident.raw" />
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
              <span class="meta-box-label">Tiempo de Respuesta:</span>
              <strong class="meta-box-val">
                {{ selectedIncident.status === 'resolved' || selectedIncident.resolutionType === 'resolved'
                  ? `${selectedIncident.resolutionTimeMin} minutos (Cierre: ${selectedIncident.resolvedAt})`
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
              <span class="signature-name">Firmado por: <strong>{{ selectedIncident.resolvedBy }}</strong> ({{ selectedIncident.role }})</span>
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
              v-model="resolutionNoteInput" maxlength="4000"
              rows="3"
              class="resolve-textarea"
              placeholder="Describa la acción correctiva realizada (ej: purga de camisa de refrigeración, ajuste de consigna a 18°C, adición de nutrientes)..."
              :disabled="isResolving"
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
          <button class="btn-secondary" @click="closeAuditModal" :disabled="isResolving">
            Cerrar Ficha
          </button>
          <button
            v-if="selectedIncident.status !== 'resolved' && selectedIncident.resolutionType !== 'resolved'"
            class="btn-resolve"
            :disabled="isResolving"
            @click="resolveIncident"
          >
            <CheckCircle2 :size="16" />
            <span>{{ isResolving ? 'Resolviendo Incidencia...' : 'Resolver Incidencia' }}</span>
          </button>
        </div>
      </div>
    </div>
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
.audit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.view-title {
  font-family: var(--font-serif);
  font-size: clamp(1.45rem, 2vw, 1.85rem);
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1.15;
  margin-bottom: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

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
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.15rem;
}

.kpi-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.15rem 1.25rem;
  display: flex;
  flex-direction: column;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(48, 12, 21, 0.05);
}

.kpi-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.65rem;
}

.kpi-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-muted);
}

.kpi-icon-box {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

.kpi-icon--neutral {
  background-color: var(--bg-subtle);
  color: var(--wine-800);
}

.kpi-icon--time {
  background-color: #E8F4FD;
  color: #1565C0;
}

.kpi-icon--good {
  background-color: var(--status-good-bg);
  color: var(--status-good);
}

.kpi-icon--warn {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
}

.kpi-icon--danger {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
}

.kpi-number {
  font-family: var(--font-mono);
  font-size: 2.1rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1;
}

.kpi-unit {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.kpi-sub {
  font-size: 0.72rem;
  color: var(--text-secondary);
  margin-top: 0.4rem;
}

/* 2. Filtros y Búsqueda */
.filters-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 0.85rem 1.15rem;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 280px;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 0.45rem 0.75rem;
}

.search-icon {
  color: var(--text-muted);
}

.search-input {
  border: none;
  background: transparent;
  outline: none;
  width: 100%;
  font-size: 0.85rem;
  color: var(--text-primary);
}

.clear-search-btn {
  color: var(--text-muted);
  cursor: pointer;
}

.clear-search-btn:hover {
  color: var(--text-primary);
}

.filter-controls {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.select-filter {
  padding: 0.45rem 0.75rem;
  font-size: 0.82rem;
  font-weight: 500;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.select-filter:focus {
  border-color: var(--wine-700);
}

.btn-reset-filters {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--wine-700);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.35rem 0.65rem;
  border-radius: var(--radius-sm);
  transition: background-color 0.15s ease;
}

.btn-reset-filters:hover {
  background-color: var(--wine-50);
}

/* 3. Tabla de Auditoría */
.audit-table-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.table-header-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
}

.table-title {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wine-900);
}

.table-count {
  font-size: 0.76rem;
  color: var(--text-muted);
}

.table-responsive {
  overflow-x: auto;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.audit-table th {
  background-color: var(--bg-canvas);
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}

.audit-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: middle;
}

.audit-row:hover {
  background-color: var(--bg-hover);
}

.td-empty {
  text-align: center;
  padding: 2.5rem 1rem;
  color: var(--text-muted);
}

/* Celdas específicas */
.id-badge {
  display: block;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--wine-900);
  font-size: 0.8rem;
}

.date-subtext {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.cuba-cell {
  display: flex;
  flex-direction: column;
}

.cuba-code-tag {
  font-weight: 700;
  color: var(--text-primary);
}

.cuba-variety {
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.sensor-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--text-secondary);
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
}

.anomaly-cell {
  display: flex;
  flex-direction: column;
  max-width: 260px;
}

.anomaly-title {
  font-weight: 600;
  color: var(--text-primary);
}

.anomaly-value {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.anomaly-value strong {
  font-family: var(--font-mono);
  color: var(--wine-800);
}

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

.btn-view-audit {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.65rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--wine-800);
  transition: all 0.15s ease;
  cursor: pointer;
}

.btn-view-audit:hover {
  background-color: var(--wine-700);
  color: #FFFFFF;
  border-color: var(--wine-700);
}

/* =========================================
   MODAL DE FICHA DE AUDITORÍA
   ========================================= */
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
</style>
