<script setup>
/**
 * 📋 05. [FRONT - VUE] Pantalla de Alertas y Gestión de Incidencias
 * Módulo 3: Alertas y Protocolo
 *
 * Integración Backend Real (TASK-FE-02A):
 * 1. Consumo de GET /api/alertas con filtros reactivos (estado, severidad, cuba_id).
 * 2. Protocolo de Atención con PATCH /api/alertas/{id}/atender.
 * 3. Actualización optimista e inmediata de estado sin recarga de página.
 * 4. Badges de severidad y estado mapeados desde Supabase PostgreSQL.
 * 5. Contador reactivo de alertas pendientes en la cabecera.
 * 6. Polling periódico cada 15s para capturar anomalías del simulador IoT.
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import {
  Bell,
  AlertTriangle,
  AlertOctagon,
  Info,
  CheckCircle2,
  Clock,
  Search,
  Filter,
  Cylinder,
  Thermometer,
  Compass,
  FileText,
  UserCheck,
  Ban,
  Check,
  X,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
  PlusCircle,
  RefreshCw
} from 'lucide-vue-next'
import alertService from '../services/alertService'

// ==========================================
// ESTADO REACTIVO (Conectado a FastAPI / Supabase)
// ==========================================
let nextAlertId = 1000

const allAlerts = ref([]) // Lista global no filtrada para KPIs estables
const alerts = ref([])    // Lista filtrada para la tabla
const isLoading = ref(false)
const isRefreshing = ref(false)
const isAttending = ref(false)
const fetchError = ref(null)

// Filtros y búsqueda
const searchQuery = ref('')
const filterSeverity = ref('all') // all | danger | warning | info
const filterStatus = ref('all')   // all | active | in_progress | resolved
const filterCuba = ref('all')

const toastMessage = ref('')

// Modal de Protocolo de Revisión
const isProtocolModalOpen = ref(false)
const selectedAlert = ref(null)
const newNoteText = ref('')
const manualSampleInput = ref('')

// ==========================================
// MAPEO DE DATOS BACKEND DTO ➔ VIEW MODEL
// ==========================================
function formatTimeAgo(isoString) {
  if (!isoString) return 'Reciente'
  const date = new Date(isoString)
  const now = new Date()
  const diffSec = Math.floor((now - date) / 1000)
  if (diffSec < 60) return `Hace ${Math.max(1, diffSec)} seg`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `Hace ${diffMin} min`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `Hace ${diffHours} h`
  const diffDays = Math.floor(diffHours / 24)
  return `Hace ${diffDays} d`
}

function mapBackendAlert(dto) {
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

  // Normalizar estado
  let status = 'active'
  let statusLabel = 'Pendiente'
  const stLower = (dto.estado || '').toLowerCase()
  if (stLower === 'atendida' || stLower === 'in_progress') {
    status = 'in_progress'
    statusLabel = 'En Protocolo'
  } else if (stLower === 'resuelta' || stLower === 'resolved') {
    status = 'resolved'
    statusLabel = 'Resuelta'
  } else {
    status = 'active'
    statusLabel = 'Pendiente'
  }

  // Construir historial de notas acumuladas
  const notes = []
  if (dto.timestamp) {
    notes.push({
      id: 'n-sys',
      author: 'Sistema Telemetría',
      time: new Date(dto.timestamp).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
      text: dto.descripcion || 'Incidencia registrada por sensor.'
    })
  }
  if (dto.fecha_atencion || dto.nota_atencion) {
    notes.push({
      id: 'n-att',
      author: dto.operador_nombre || 'Enólogo en Turno',
      time: dto.fecha_atencion
        ? new Date(dto.fecha_atencion).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
        : 'En Protocolo',
      text: dto.nota_atencion || 'Atención de incidencia iniciada en bodega.'
    })
  }
  if (dto.fecha_resolucion || dto.nota_resolucion) {
    notes.push({
      id: 'n-res',
      author: dto.operador_nombre || 'Enólogo en Turno',
      time: dto.fecha_resolucion
        ? new Date(dto.fecha_resolucion).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
        : 'Resuelta',
      text: dto.nota_resolucion || 'Incidencia resuelta y protocolo completado satisfactoriamente.'
    })
  }

  // Identificar sensor y nombre legible
  let sensorType = 'DS18B20'
  let sensorName = 'Sonda Térmica Central'
  const rawType = (dto.sensor_tipo || dto.tipo_alerta || '').toUpperCase()
  if (rawType.includes('MPU') || rawType.includes('BRIX') || rawType.includes('TILT')) {
    sensorType = 'MPU-6050'
    sensorName = 'Inclinómetro Giroscopio'
  } else if (rawType.includes('PH')) {
    sensorType = 'PH-4502C'
    sensorName = 'Sonda de pH Analógica'
  }

  const valueDetected = dto.met_dispar ? `Disparo: ${dto.met_dispar}` : 'Desvío enológico registrado'
  const thresholdRule = 'Límite de Perfil de Fermentación'

  return {
    id: dto.id,
    cubaId: dto.cuba_id ? String(dto.cuba_id) : '1',
    cubaCode: dto.cuba_codigo || (dto.cuba_id ? `CB-0${dto.cuba_id}` : 'General'),
    cubaName: dto.cuba_nombre || `Cuba ${dto.cuba_codigo || 'General'}`,
    variety: dto.variedad || 'Fermentación Activa',
    sensorType,
    sensorName,
    sensorDisabled: false,
    severity,
    severityBackend: dto.severidad,
    severityLabel,
    title: dto.titulo || `Alerta: ${dto.tipo_alerta || 'Incidencia'}`,
    description: dto.descripcion,
    valueDetected,
    thresholdRule,
    timestamp: formatTimeAgo(dto.timestamp),
    dateIso: dto.timestamp ? new Date(dto.timestamp).toLocaleString('es-CL') : '',
    status,
    statusBackend: dto.estado,
    statusLabel,
    assignedTo: dto.operador_nombre || 'Sin asignar',
    notes,
    manualCheck: null,
    raw: dto
  }
}

// ==========================================
// CONSULTA A LA API REST (FastAPI)
// ==========================================
async function loadAlerts(silent = false) {
  if (!silent) isLoading.value = true
  fetchError.value = null
  try {
    const params = {}

    // 1. Filtro por Estado hacia el backend
    if (filterStatus.value !== 'all') {
      if (filterStatus.value === 'active' || filterStatus.value === 'pendiente') {
        params.estado = 'pendiente'
      } else if (filterStatus.value === 'in_progress' || filterStatus.value === 'atendida') {
        params.estado = 'atendida'
      } else if (filterStatus.value === 'resolved' || filterStatus.value === 'resuelta') {
        params.estado = 'resuelta'
      }
    }

    // 2. Filtro por Severidad hacia el backend
    if (filterSeverity.value !== 'all') {
      if (filterSeverity.value === 'danger') {
        params.severidad = 'critica'
      } else if (filterSeverity.value === 'warning') {
        params.severidad = 'media'
      } else if (filterSeverity.value === 'info') {
        params.severidad = 'baja'
      } else {
        params.severidad = filterSeverity.value
      }
    }

    // 3. Filtro por Cuba hacia el backend
    if (filterCuba.value !== 'all') {
      params.cuba_id = Number(filterCuba.value)
    }

    // Si no hay filtros aplicados, data ya representa la lista global
    const isFiltered = Object.keys(params).length > 0
    if (!isFiltered || allAlerts.value.length === 0) {
      const globalData = await alertService.listarAlertas()
      allAlerts.value = globalData.map(mapBackendAlert)
    }

    const data = isFiltered ? await alertService.listarAlertas(params) : allAlerts.value.map(a => a.raw)
    alerts.value = data.map(mapBackendAlert)
  } catch (err) {
    console.error('Error al consultar alertas:', err)
    fetchError.value = err.message || 'Error de conexión con el backend MOSTO'
  } finally {
    if (!silent) isLoading.value = false
    isRefreshing.value = false
  }
}

// Escuchar cambios reactivos en los filtros desplegables para reconsultar con query params
watch([filterSeverity, filterStatus, filterCuba], () => {
  loadAlerts(false)
})

// ==========================================
// KPIS COMPUTADOS (Calculados sobre métricas globales de la bodega)
// ==========================================
const totalActive = computed(() => {
  return allAlerts.value.filter(a => a.status === 'active' || a.statusBackend === 'pendiente').length
})

const totalCritical = computed(() => {
  return allAlerts.value.filter(
    a => (a.severity === 'danger' || a.severityBackend === 'critica' || a.severityBackend === 'alta') &&
         a.status !== 'resolved' && a.statusBackend !== 'resuelta'
  ).length
})

const totalWarning = computed(() => {
  return allAlerts.value.filter(
    a => (a.severity === 'warning' || a.severityBackend === 'media') &&
         a.status !== 'resolved' && a.statusBackend !== 'resuelta'
  ).length
})

const totalInProgress = computed(() => {
  return allAlerts.value.filter(a => a.status === 'in_progress' || a.statusBackend === 'atendida').length
})

const totalDisabledSensors = computed(() => {
  return allAlerts.value.filter(a => a.sensorDisabled).length
})

// Lista filtrada (Filtro complementario por texto en cliente)
const filteredAlerts = computed(() => {
  return alerts.value.filter(alert => {
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      const matchText =
        (alert.cubaName || '').toLowerCase().includes(q) ||
        (alert.cubaCode || '').toLowerCase().includes(q) ||
        (alert.title || '').toLowerCase().includes(q) ||
        (alert.description || '').toLowerCase().includes(q) ||
        (alert.sensorType || '').toLowerCase().includes(q) ||
        (alert.assignedTo || '').toLowerCase().includes(q)
      if (!matchText) return false
    }
    return true
  })
})

// Opciones de cubas disponibles
const cubasAvailable = computed(() => {
  const map = new Map()
  map.set('1', { id: '1', code: 'CB-01', name: 'Cuba 01 · Cabernet Sauvignon' })
  map.set('2', { id: '2', code: 'CB-02', name: 'Cuba 02 · Carménère Reserva' })
  map.set('3', { id: '3', code: 'CB-03', name: 'Cuba 03 · Sauvignon Blanc' })
  map.set('4', { id: '4', code: 'CB-04', name: 'Cuba 04 · Syrah Gran Corte' })

  allAlerts.value.forEach(a => {
    if (a.cubaId && !map.has(a.cubaId)) {
      map.set(a.cubaId, { id: a.cubaId, code: a.cubaCode, name: a.cubaName })
    }
  })
  return Array.from(map.values())
})

// ==========================================
// ACCIONES Y PROTOCOLO
// ==========================================
function showToast(msg) {
  toastMessage.value = msg
  setTimeout(() => {
    toastMessage.value = ''
  }, 4500)
}

function openProtocol(alert) {
  selectedAlert.value = alert
  newNoteText.value = ''
  manualSampleInput.value = alert.manualCheck || ''
  isProtocolModalOpen.value = true
}

function closeProtocol() {
  isProtocolModalOpen.value = false
  selectedAlert.value = null
}

function toggleSensorDisabled() {
  if (!selectedAlert.value) return
  selectedAlert.value.sensorDisabled = !selectedAlert.value.sensorDisabled

  const actionName = selectedAlert.value.sensorDisabled ? 'ANULADO (aislado)' : 'REACTIVADO'
  selectedAlert.value.notes.push({
    id: Date.now(),
    author: 'Enólogo en Turno',
    time: new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
    text: `Sensor ${selectedAlert.value.sensorType} (${selectedAlert.value.sensorName}) ${actionName} en protocolo de revisión.`
  })

  if (selectedAlert.value.sensorDisabled) {
    showToast(`Sensor ${selectedAlert.value.sensorType} de ${selectedAlert.value.cubaCode} ha sido ANULADO. Se ignoran alertas falsas.`)
  } else {
    showToast(`Sensor ${selectedAlert.value.sensorType} de ${selectedAlert.value.cubaCode} ha sido REACTIVADO para telemetría en vivo.`)
  }
}

// Conexión oficial de Atender Alerta (PATCH /api/alertas/{id}/atender)
async function attendAlert(alert, noteText = '') {
  if (!alert) return
  isAttending.value = true
  try {
    const payload = {
      usuario_id: 1, // Enólogo operador
      nota: noteText.trim() || 'Atención de incidencia iniciada por el enólogo en bodega.'
    }

    let operadorNombre = 'Operador Enología'
    if (alert.id < 1000) {
      const updatedDto = await alertService.atender(alert.id, payload)
      operadorNombre = updatedDto.operador_nombre || operadorNombre
    }

    // Actualización inmediata en la tabla reactiva y en la lista global de KPIs
    alert.status = 'in_progress'
    alert.statusBackend = 'atendida'
    alert.statusLabel = 'En Protocolo'
    alert.assignedTo = operadorNombre

    const noteObj = {
      id: Date.now(),
      author: operadorNombre,
      time: new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
      text: payload.nota
    }
    alert.notes.push(noteObj)

    // Sincronizar en allAlerts para actualizar los KPIs
    const inGlobal = allAlerts.value.find(a => a.id === alert.id)
    if (inGlobal) {
      inGlobal.status = 'in_progress'
      inGlobal.statusBackend = 'atendida'
      inGlobal.statusLabel = 'En Protocolo'
      inGlobal.assignedTo = alert.assignedTo
      inGlobal.notes.push(noteObj)
    }

    showToast(`Alerta #${alert.id} de ${alert.cubaCode} atendida e ingresada al protocolo enológico.`)
  } catch (err) {
    showToast(`Error al atender alerta: ${err.message}`)
  } finally {
    isAttending.value = false
  }
}

// Acción de atención rápida desde el botón de la fila
async function quickAttendAlert(alert) {
  await attendAlert(alert, 'Atención rápida iniciada desde la lista de alertas.')
}

// Acción de atención desde el modal de protocolo
async function attendSelectedAlert() {
  if (!selectedAlert.value) return
  await attendAlert(selectedAlert.value, newNoteText.value || 'Atención iniciada desde el protocolo de revisión.')
  newNoteText.value = ''
  closeProtocol()
}

// Acción: Guardar Nota de Terreno
async function addNote() {
  if (!newNoteText.value.trim() || !selectedAlert.value) return

  const noteContent = newNoteText.value.trim()

  // Si la alerta aún está activa/pendiente, la atendemos formalmente en el backend
  if (selectedAlert.value.status === 'active' || selectedAlert.value.statusBackend === 'pendiente') {
    await attendAlert(selectedAlert.value, noteContent)
    newNoteText.value = ''
    return
  }

  // Si ya estaba en protocolo, agregamos la nota en la ficha
  selectedAlert.value.notes.push({
    id: Date.now(),
    author: 'Enólogo en Turno',
    time: new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
    text: noteContent
  })
  newNoteText.value = ''
  showToast('Nota técnica registrada en la incidencia.')
}

// Acción: Registrar Medición Manual de Contraste
function saveManualCheck() {
  if (!manualSampleInput.value.trim() || !selectedAlert.value) return

  selectedAlert.value.manualCheck = manualSampleInput.value.trim()
  selectedAlert.value.notes.push({
    id: Date.now(),
    author: 'Enólogo en Turno',
    time: new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
    text: `Medición manual de contraste confirmada: ${manualSampleInput.value.trim()}.`
  })

  showToast('Medición manual registrada correctamente.')
}

// Acción: Marcar como Resuelta (PATCH /api/alertas/{id}/resolver)
async function resolveAlert() {
  if (!selectedAlert.value) return
  isAttending.value = true
  try {
    const payload = {
      usuario_id: 1,
      nota_resolucion: newNoteText.value.trim() || 'Incidencia cerrada y protocolo completado satisfactoriamente.'
    }
    if (selectedAlert.value.id < 1000) {
      await alertService.resolver(selectedAlert.value.id, payload)
    }

    selectedAlert.value.status = 'resolved'
    selectedAlert.value.statusBackend = 'resuelta'
    selectedAlert.value.statusLabel = 'Resuelta'
    const resolveNote = {
      id: Date.now(),
      author: 'Enólogo en Turno',
      time: new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
      text: payload.nota_resolucion
    }
    selectedAlert.value.notes.push(resolveNote)

    // Sincronizar en allAlerts para descontar de las métricas activas
    const inGlobal = allAlerts.value.find(a => a.id === selectedAlert.value.id)
    if (inGlobal) {
      inGlobal.status = 'resolved'
      inGlobal.statusBackend = 'resuelta'
      inGlobal.statusLabel = 'Resuelta'
      inGlobal.notes.push(resolveNote)
    }

    showToast(`Incidencia en ${selectedAlert.value.cubaCode} marcada como RESUELTA en Supabase.`)
    closeProtocol()
  } catch (err) {
    showToast(`Error al resolver: ${err.message}`)
  } finally {
    isAttending.value = false
  }
}

// Simular alerta nueva de prueba
function simulateNewAlert() {
  const newId = ++nextAlertId
  const simulated = {
    id: newId,
    cubaId: '2',
    cubaCode: 'CB-02',
    cubaName: 'Cuba 02 · Carménère Reserva',
    variety: 'Carménère',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Central',
    sensorDisabled: false,
    severity: 'danger',
    severityBackend: 'critica',
    severityLabel: 'Crítica',
    title: 'Variación Térmica Repentina (+2.3°C en 30m)',
    description: 'Alza brusca de temperatura detectada en Cuba 02. Revisar si la camisa de refrigeración sufrió corte de suministro.',
    valueDetected: '26.8 °C',
    thresholdRule: 'Tasa máx permitida: +1.5°C/h',
    timestamp: 'Ahora mismo',
    dateIso: new Date().toISOString(),
    status: 'active',
    statusBackend: 'pendiente',
    statusLabel: 'Pendiente',
    assignedTo: 'Sin asignar',
    notes: [
      { id: 1, author: 'Simulador IoT', time: 'Ahora', text: 'Disparo de prueba por evento térmico inesperado.' }
    ],
    manualCheck: null
  }

  alerts.value.unshift(simulated)
  allAlerts.value.unshift(simulated)
  showToast('¡Alerta simulada generada exitosamente! También puedes ejecutar "python backend/simulate_esp.py".')
}

// ==========================================
// CICLO DE VIDA Y POLLING
// ==========================================
let pollTimer = null

function handleManualRefresh() {
  isRefreshing.value = true
  loadAlerts(false)
}

onMounted(() => {
  loadAlerts(false)

  // Polling automático cada 15s para capturar anomalías del simulador
  pollTimer = setInterval(() => {
    if (!isProtocolModalOpen.value) {
      loadAlerts(true)
    }
  }, 15000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>


<template>
  <div class="view-container alerts-view">
    <!-- Toast Flotante -->
    <transition name="toast-fade">
      <div v-if="toastMessage" class="toast-popup">
        <CheckCircle2 :size="16" />
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

    <!-- Header Principal -->
    <header class="alerts-header">
      <div>
        <div class="module-tag">Módulo 3 · Alertas y Protocolo</div>
        <div class="title-with-counter">
          <h1 class="view-title">Alertas y Gestión de Incidencias</h1>
          <span class="badge-pending-header" :class="{ 'has-pending': totalActive > 0 }">
            <span v-if="totalActive > 0" class="pulse-dot"></span>
            {{ totalActive }} Pendiente{{ totalActive === 1 ? '' : 's' }}
          </span>
        </div>
        <p class="view-subtitle">
          Supervisión en tiempo real de anomalías de fermentación, fallas en sensores DS18B20 / MPU-6050 y protocolo operativo del enólogo.
        </p>
      </div>

      <div class="header-actions">
        <button
          class="btn-refresh"
          :class="{ 'is-refreshing': isRefreshing || isLoading }"
          :disabled="isLoading || isRefreshing"
          @click="handleManualRefresh"
          title="Actualizar listado de alertas desde el backend"
        >
          <RefreshCw :size="15" :class="{ 'animate-spin': isRefreshing || isLoading }" />
          <span>{{ isRefreshing || isLoading ? 'Sincronizando...' : 'Actualizar' }}</span>
        </button>
        <button class="btn-simulate" @click="simulateNewAlert" title="Genera una alerta de prueba en vivo">
          <PlusCircle :size="15" />
          <span>Simular Alerta</span>
        </button>
      </div>
    </header>

    <!-- Barra de Tarjetas KPIs -->
    <section class="kpi-grid">
      <!-- 1. Críticas -->
      <div
        class="kpi-card kpi-card--danger"
        :class="{ active: filterSeverity === 'danger' }"
        @click="filterSeverity = filterSeverity === 'danger' ? 'all' : 'danger'"
      >
        <div class="kpi-top">
          <span class="kpi-label">Alertas Críticas</span>
          <div class="kpi-icon-box kpi-icon--danger">
            <AlertOctagon :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalCritical }}</div>
        <div class="kpi-sub">
          <span>Requieren intervención inmediata</span>
        </div>
      </div>

      <!-- 2. Advertencias -->
      <div
        class="kpi-card kpi-card--warning"
        :class="{ active: filterSeverity === 'warning' }"
        @click="filterSeverity = filterSeverity === 'warning' ? 'all' : 'warning'"
      >
        <div class="kpi-top">
          <span class="kpi-label">Advertencias</span>
          <div class="kpi-icon-box kpi-icon--warning">
            <AlertTriangle :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalWarning }}</div>
        <div class="kpi-sub">
          <span>Desvíos de temperatura o flotador</span>
        </div>
      </div>

      <!-- 3. En Protocolo -->
      <div
        class="kpi-card kpi-card--progress"
        :class="{ active: filterStatus === 'in_progress' }"
        @click="filterStatus = filterStatus === 'in_progress' ? 'all' : 'in_progress'"
      >
        <div class="kpi-top">
          <span class="kpi-label">En Protocolo</span>
          <div class="kpi-icon-box kpi-icon--progress">
            <UserCheck :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalInProgress }}</div>
        <div class="kpi-sub">
          <span>Enólogo atendiendo en terreno</span>
        </div>
      </div>

      <!-- 4. Sensores Anulados -->
      <div class="kpi-card kpi-card--muted">
        <div class="kpi-top">
          <span class="kpi-label">Sensores Aislados</span>
          <div class="kpi-icon-box kpi-icon--muted">
            <Ban :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalDisabledSensors }}</div>
        <div class="kpi-sub">
          <span>Telemetría anulada por protocolo</span>
        </div>
      </div>
    </section>

    <!-- Barra de Filtros y Búsqueda -->
    <section class="filters-bar">
      <!-- Buscador -->
      <div class="search-box">
        <Search :size="16" class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar por cuba, sensor (DS18B20/MPU), tipo de alerta..."
          class="search-input"
        />
        <button v-if="searchQuery" @click="searchQuery = ''" class="clear-search-btn">
          <X :size="14" />
        </button>
      </div>

      <!-- Filtros desplegables y botones -->
      <div class="filter-controls">
        <!-- Selector Cuba -->
        <select v-model="filterCuba" class="select-filter">
          <option value="all">Todas las cubas</option>
          <option v-for="cuba in cubasAvailable" :key="cuba.id" :value="cuba.id">
            {{ cuba.code }} ({{ cuba.name.split('·')[1]?.trim() || cuba.name }})
          </option>
        </select>

        <!-- Selector Severidad -->
        <select v-model="filterSeverity" class="select-filter">
          <option value="all">Severidad: Todas</option>
          <option value="danger">Solo Críticas</option>
          <option value="warning">Solo Advertencias</option>
          <option value="info">Solo Informativas</option>
        </select>

        <!-- Selector Estado -->
        <select v-model="filterStatus" class="select-filter">
          <option value="all">Estado: Todos</option>
          <option value="active">Activas</option>
          <option value="in_progress">En Protocolo</option>
          <option value="resolved">Resueltas</option>
        </select>

        <!-- Botón Reset si hay filtros aplicados -->
        <button
          v-if="searchQuery || filterSeverity !== 'all' || filterStatus !== 'all' || filterCuba !== 'all'"
          class="btn-reset-filters"
          @click="searchQuery = ''; filterSeverity = 'all'; filterStatus = 'all'; filterCuba = 'all'"
        >
          Limpiar filtros
        </button>
      </div>
    </section>

    <!-- Lista / Tabla de Alertas -->
    <section class="alerts-table-container">
      <!-- Loading State -->
      <div v-if="isLoading && alerts.length === 0" class="state-banner loading-state">
        <RefreshCw :size="32" class="animate-spin text-wine" />
        <p>Conectando con el servidor MOSTO y consultando alertas...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="fetchError && alerts.length === 0" class="state-banner error-state">
        <AlertTriangle :size="36" class="text-danger" />
        <h3>Error al consultar alertas</h3>
        <p>{{ fetchError }}</p>
        <button class="btn-retry" @click="loadAlerts(false)">
          <RefreshCw :size="14" />
          <span>Reintentar Conexión</span>
        </button>
      </div>

      <div v-else-if="filteredAlerts.length === 0" class="empty-state">
        <CheckCircle2 :size="40" class="empty-icon" />
        <h3>No hay alertas que coincidan con los filtros</h3>
        <p>Todas las cubas y sensores operan dentro de los umbrales esperados.</p>
      </div>

      <div v-else class="alerts-list">
        <div
          v-for="alert in filteredAlerts"
          :key="alert.id"
          class="alert-row"
          :class="[
            'alert-row--' + alert.severity,
            { 'alert-row--resolved': alert.status === 'resolved' }
          ]"
        >
          <!-- Indicador lateral de severidad -->
          <div class="severity-stripe"></div>

          <!-- Contenido Principal -->
          <div class="alert-content">
            <!-- Fila superior: Cuba, Sensor, Tiempo y Severidad -->
            <div class="alert-meta-top">
              <div class="meta-left">
                <router-link
                  :to="'/cubas/' + alert.cubaId"
                  class="cuba-badge-link"
                  title="Ver detalle telemétrico de esta cuba"
                >
                  <Cylinder :size="14" />
                  <span>{{ alert.cubaCode }}</span>
                  <ExternalLink :size="12" class="link-ext-icon" />
                </router-link>

                <span class="variety-text">{{ alert.variety }}</span>

                <span class="sensor-chip" :class="{ 'sensor-chip--disabled': alert.sensorDisabled }">
                  <component :is="alert.sensorType === 'DS18B20' ? Thermometer : Compass" :size="13" />
                  <span>{{ alert.sensorType }}</span>
                  <span v-if="alert.sensorDisabled" class="tag-disabled">(Anulado)</span>
                </span>
              </div>

              <div class="meta-right">
                <span class="timestamp-label">
                  <Clock :size="12" />
                  {{ alert.timestamp }}
                </span>

                <span
                  class="badge-severity"
                  :class="'badge-severity--' + alert.severity"
                >
                  <span v-if="alert.severity === 'danger'" class="pulse-dot"></span>
                  {{ alert.severityLabel }}
                </span>

                <span
                  class="badge-status"
                  :class="'badge-status--' + alert.status"
                >
                  {{ alert.statusLabel }}
                </span>
              </div>
            </div>

            <!-- Fila media: Título y descripción de la anomalía -->
            <div class="alert-body">
              <h3 class="alert-title">{{ alert.title }}</h3>
              <p class="alert-description">{{ alert.description }}</p>
            </div>

            <!-- Fila inferior: Valores medidos, regla rota y botón de atención -->
            <div class="alert-footer">
              <div class="values-group">
                <div class="val-item">
                  <span class="val-label">Valor Detectado:</span>
                  <span class="val-value val-highlight">{{ alert.valueDetected }}</span>
                </div>
                <div class="val-item">
                  <span class="val-label">Regla de Umbral:</span>
                  <span class="val-value">{{ alert.thresholdRule }}</span>
                </div>
                <div v-if="alert.manualCheck" class="val-item val-item--manual">
                  <span class="val-label">Muestra Manual:</span>
                  <span class="val-value manual-val">{{ alert.manualCheck }}</span>
                </div>
              </div>

              <div class="actions-group">
                <button
                  v-if="alert.status === 'active' || alert.statusBackend === 'pendiente'"
                  class="btn-quick-attend"
                  :disabled="isAttending"
                  title="Atender directamente esta incidencia y pasar a protocolo"
                  @click.stop="quickAttendAlert(alert)"
                >
                  <UserCheck :size="14" />
                  <span>Atender</span>
                </button>

                <button
                  class="btn-attend"
                  :class="alert.status === 'resolved' || alert.statusBackend === 'resuelta' ? 'btn-attend--resolved' : 'btn-attend--active'"
                  @click="openProtocol(alert)"
                >
                  <component :is="alert.status === 'resolved' || alert.statusBackend === 'resuelta' ? Check : ShieldAlert" :size="15" />
                  <span>{{ alert.status === 'resolved' || alert.statusBackend === 'resuelta' ? 'Ver Bitácora' : 'Atender Incidencia' }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- MODAL / DRAWER: PROTOCOLO DE REVISIÓN DEL ENÓLOGO -->
    <div v-if="isProtocolModalOpen && selectedAlert" class="modal-backdrop" @click.self="closeProtocol">
      <div class="protocol-modal">
        <!-- Header del Modal -->
        <div class="modal-header">
          <div class="modal-title-group">
            <div
              class="modal-icon-badge"
              :class="'modal-icon--' + selectedAlert.severity"
            >
              <ShieldAlert :size="20" />
            </div>
            <div>
              <h2 class="modal-title">Protocolo de Revisión Enológica</h2>
              <p class="modal-sub">
                {{ selectedAlert.cubaName }} · Sensor {{ selectedAlert.sensorType }} ({{ selectedAlert.sensorName }})
              </p>
            </div>
          </div>

          <button class="modal-close-btn" @click="closeProtocol">
            <X :size="18" />
          </button>
        </div>

        <!-- Cuerpo del Modal -->
        <div class="modal-body">
          <!-- Resumen de la Alerta -->
          <div class="incident-summary-box">
            <div class="summary-header">
              <span class="summary-tag">Detalle de la Incidencia</span>
              <span class="summary-time">{{ selectedAlert.timestamp }} ({{ selectedAlert.dateIso }})</span>
            </div>
            <h4 class="summary-title">{{ selectedAlert.title }}</h4>
            <p class="summary-desc">{{ selectedAlert.description }}</p>

            <div class="summary-metrics">
              <div class="metric-chip">
                <span>Lectura Telemétrica:</span>
                <strong>{{ selectedAlert.valueDetected }}</strong>
              </div>
              <div class="metric-chip">
                <span>Criterio de Disparo:</span>
                <strong>{{ selectedAlert.thresholdRule }}</strong>
              </div>
            </div>
          </div>

          <!-- Protocolo Paso 1: Ingreso de Muestra Manual de Terreno -->
          <div class="protocol-step">
            <div class="step-header">
              <span class="step-num">1</span>
              <div>
                <h4 class="step-title">Verificación Manual de Terreno</h4>
                <p class="step-desc">
                  Compara la lectura del sensor con un instrumento manual físico (termómetro analógico o refractómetro).
                </p>
              </div>
            </div>

            <div class="manual-check-form">
              <input
                v-model="manualSampleInput"
                type="text"
                placeholder="Ej: 24.2 °C con termómetro manual / 13.0 °Bx"
                class="input-manual"
              />
              <button class="btn-save-manual" @click="saveManualCheck">
                Registrar Muestra
              </button>
            </div>
            <div v-if="selectedAlert.manualCheck" class="current-manual-badge">
              <CheckCircle2 :size="14" />
              <span>Muestra registrada: <strong>{{ selectedAlert.manualCheck }}</strong></span>
            </div>
          </div>

          <!-- Protocolo Paso 2: Acción Operativa sobre el Sensor -->
          <div class="protocol-step">
            <div class="step-header">
              <span class="step-num">2</span>
              <div>
                <h4 class="step-title">Acción Técnica: Aislamiento del Sensor IoT</h4>
                <p class="step-desc">
                  Si el sensor está descalibrado, averiado o durante maniobras de bodega, puedes anularlo temporalmente para que no emita falsas alarmas ni afecte los promedios.
                </p>
              </div>
            </div>

            <div class="sensor-toggle-box" :class="{ 'sensor-box--disabled': selectedAlert.sensorDisabled }">
              <div class="sensor-info-text">
                <strong>Sensor {{ selectedAlert.sensorType }} ({{ selectedAlert.sensorName }})</strong>
                <p>
                  Estado actual:
                  <span v-if="selectedAlert.sensorDisabled" class="status-off">ANULADO (Telemetría pausada)</span>
                  <span v-else class="status-on">OPERATIVO (Transmitiendo en vivo)</span>
                </p>
              </div>

              <button
                class="btn-toggle-sensor"
                :class="selectedAlert.sensorDisabled ? 'btn-toggle--enable' : 'btn-toggle--disable'"
                @click="toggleSensorDisabled"
              >
                <Ban v-if="!selectedAlert.sensorDisabled" :size="15" />
                <Check v-else :size="15" />
                <span>{{ selectedAlert.sensorDisabled ? 'Reactivar Sensor' : 'Anular Sensor Defectuoso' }}</span>
              </button>
            </div>
          </div>

          <!-- Protocolo Paso 3: Registro de Observaciones del Enólogo -->
          <div class="protocol-step">
            <div class="step-header">
              <span class="step-num">3</span>
              <div>
                <h4 class="step-title">Notas Técnicas y Registro de Bitácora</h4>
                <p class="step-desc">
                  Documenta las causas del desvío y las medidas correctivas aplicadas en la cuba.
                </p>
              </div>
            </div>

            <!-- Historial de notas acumuladas -->
            <div class="notes-timeline">
              <div v-for="n in selectedAlert.notes" :key="n.id" class="note-item">
                <div class="note-meta">
                  <span class="note-author">{{ n.author }}</span>
                  <span class="note-time">{{ n.time }}</span>
                </div>
                <p class="note-text">{{ n.text }}</p>
              </div>
            </div>

            <!-- Input nueva nota -->
            <div class="add-note-box">
              <textarea
                v-model="newNoteText"
                rows="2"
                placeholder="Escribe una observación técnica (ej: Se aumentó el caudal de glicol; se limpió sonda de impurezas)..."
                class="textarea-note"
              ></textarea>
              <button
                class="btn-add-note"
                :disabled="!newNoteText.trim()"
                @click="addNote"
              >
                Agregar Nota
              </button>
            </div>
          </div>
        </div>

        <!-- Footer del Modal con Acciones de Cierre -->
        <div class="modal-footer">
          <button class="btn-modal-cancel" @click="closeProtocol">
            Cerrar sin cambiar estado
          </button>

          <div class="modal-footer-actions">
            <button
              v-if="selectedAlert.status !== 'in_progress' && selectedAlert.status !== 'resolved' && selectedAlert.statusBackend !== 'atendida' && selectedAlert.statusBackend !== 'resuelta'"
              class="btn-modal-progress"
              :disabled="isAttending"
              @click="attendSelectedAlert"
            >
              <UserCheck :size="15" />
              <span>{{ isAttending ? 'Registrando...' : 'Atender e Iniciar Protocolo' }}</span>
            </button>

            <button
              v-if="selectedAlert.status !== 'resolved'"
              class="btn-modal-resolve"
              @click="resolveAlert"
            >
              <CheckCircle2 :size="16" />
              <span>Marcar Incidencia Resuelta</span>
            </button>

            <span v-else class="resolved-label">
              <CheckCircle2 :size="16" />
              Incidencia cerrada en bitácora
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* =========================================
   ESTILOS DE ALERTAS Y GESTIÓN DE INCIDENCIAS
   ========================================= */
.alerts-view {
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
.alerts-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.module-tag {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--wine-700);
  margin-bottom: 0.25rem;
}

.view-title {
  font-family: var(--font-serif);
  font-size: 2.1rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1.15;
  margin-bottom: 0.4rem;
}

.view-subtitle {
  font-size: 0.88rem;
  color: var(--text-secondary);
  max-width: 720px;
  line-height: 1.45;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.btn-simulate {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--wine-100);
  color: var(--wine-800);
  border: 1px solid var(--border-color);
  padding: 0.55rem 0.95rem;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  font-weight: 600;
  transition: all 0.15s ease;
}

.btn-simulate:hover {
  background-color: var(--wine-700);
  color: #FFFFFF;
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
  box-shadow: var(--shadow-subtle);
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(35, 22, 28, 0.08);
}

.kpi-card.active {
  border-color: var(--wine-700);
  background-color: var(--wine-50);
}

.kpi-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
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

.kpi-icon--danger {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
}

.kpi-icon--warning {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
}

.kpi-icon--progress {
  background-color: #E8F4FD;
  color: #1565C0;
}

.kpi-icon--muted {
  background-color: var(--bg-subtle);
  color: var(--text-muted);
}

.kpi-number {
  font-family: var(--font-mono);
  font-size: 2.1rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1;
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
  position: relative;
  flex: 1;
  min-width: 260px;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 0.85rem;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.5rem 2rem 0.5rem 2.3rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
  font-family: inherit;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
  outline: none;
}

.search-input:focus {
  border-color: var(--wine-700);
  background-color: #FFFFFF;
}

.clear-search-btn {
  position: absolute;
  right: 0.65rem;
  color: var(--text-muted);
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
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  font-family: inherit;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.select-filter:focus {
  border-color: var(--wine-700);
}

.btn-reset-filters {
  font-size: 0.76rem;
  color: var(--wine-700);
  font-weight: 600;
  text-decoration: underline;
  padding: 0.35rem 0.5rem;
}

/* 3. Lista de Alertas */
.alerts-table-container {
  display: flex;
  flex-direction: column;
}

.empty-state {
  background-color: var(--bg-surface);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 3.5rem 2rem;
  text-align: center;
}

.empty-icon {
  color: var(--status-good);
  margin-bottom: 0.75rem;
}

.empty-state h3 {
  font-family: var(--font-serif);
  font-size: 1.35rem;
  color: var(--wine-900);
}

.empty-state p {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.alert-row {
  display: flex;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-subtle);
  overflow: hidden;
  transition: all 0.15s ease;
}

.alert-row:hover {
  border-color: #D3C3BE;
  box-shadow: 0 3px 10px rgba(35, 22, 28, 0.06);
}

.severity-stripe {
  width: 6px;
  flex-shrink: 0;
}

.alert-row--danger .severity-stripe {
  background-color: var(--status-danger);
}

.alert-row--warning .severity-stripe {
  background-color: var(--status-warn);
}

.alert-row--info .severity-stripe {
  background-color: #1565C0;
}

.alert-row--resolved {
  opacity: 0.75;
  background-color: #FCFAFA;
}
.alert-row--resolved .severity-stripe {
  background-color: var(--status-good);
}

.alert-content {
  flex: 1;
  padding: 1.15rem 1.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

/* Meta Top */
.alert-meta-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.meta-left {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.cuba-badge-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background-color: var(--wine-100);
  color: var(--wine-800);
  padding: 0.25rem 0.55rem;
  border-radius: var(--radius-sm);
  font-weight: 700;
  font-size: 0.78rem;
  border: 1px solid var(--border-color);
  transition: background-color 0.15s ease;
}

.cuba-badge-link:hover {
  background-color: var(--wine-700);
  color: #FFFFFF;
}

.link-ext-icon {
  opacity: 0.6;
}

.variety-text {
  font-size: 0.78rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.sensor-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  padding: 0.2rem 0.5rem;
  border-radius: var(--radius-sm);
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

.sensor-chip--disabled {
  background-color: var(--bg-subtle);
  color: var(--status-danger);
  border-color: var(--status-danger-border);
}

.tag-disabled {
  font-weight: 700;
}

.meta-right {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.timestamp-label {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.74rem;
  color: var(--text-muted);
}

.badge-severity {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.2rem 0.6rem;
  border-radius: var(--radius-full);
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

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--status-danger);
  animation: pulse-dot 1.4s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.3; transform: scale(0.85); }
}

.badge-status {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-sm);
}

.badge-status--active {
  background-color: #FDF4E7;
  color: #B25E09;
}

.badge-status--in_progress {
  background-color: #E8F4FD;
  color: #1565C0;
}

.badge-status--resolved {
  background-color: var(--status-good-bg);
  color: var(--status-good);
}

/* Body */
.alert-body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.alert-title {
  font-family: var(--font-serif);
  font-size: 1.18rem;
  font-weight: 700;
  color: var(--wine-900);
}

.alert-description {
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

/* Footer */
.alert-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  padding-top: 0.65rem;
  border-top: 1px solid var(--border-subtle);
}

.values-group {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.val-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
}

.val-label {
  color: var(--text-muted);
}

.val-value {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
}

.val-highlight {
  color: var(--wine-800);
  background-color: var(--wine-50);
  padding: 0.15rem 0.4rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.val-item--manual {
  background-color: #F0FDF4;
  border: 1px solid #DCFCE7;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
}

.manual-val {
  color: #15803D;
}

.actions-group {
  display: flex;
  align-items: center;
}

.btn-attend {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.95rem;
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  font-weight: 600;
  transition: all 0.15s ease;
}

.btn-attend--active {
  background-color: var(--wine-700);
  color: #FFFFFF;
}

.btn-attend--active:hover {
  background-color: var(--wine-800);
}

.btn-attend--resolved {
  background-color: var(--bg-canvas);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-attend--resolved:hover {
  background-color: var(--bg-hover);
}

/* =========================================
   MODAL DE PROTOCOLO DE REVISIÓN
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

.protocol-modal {
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
  align-items: center;
}

.modal-title-group {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.modal-icon-badge {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-icon--danger {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
}

.modal-icon--warning {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
}

.modal-icon--info {
  background-color: #E8F4FD;
  color: #1565C0;
}

.modal-title {
  font-family: var(--font-serif);
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--wine-900);
}

.modal-sub {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.modal-close-btn {
  color: var(--text-muted);
  padding: 0.4rem;
  border-radius: var(--radius-sm);
  transition: color 0.15s ease;
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
  gap: 1.5rem;
}

/* Incidente Summary */
.incident-summary-box {
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1rem 1.2rem;
}

.summary-header {
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.summary-tag {
  font-weight: 700;
  text-transform: uppercase;
  color: var(--wine-700);
}

.summary-title {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wine-900);
  margin-bottom: 0.25rem;
}

.summary-desc {
  font-size: 0.82rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.summary-metrics {
  display: flex;
  gap: 1.5rem;
  margin-top: 0.75rem;
  padding-top: 0.65rem;
  border-top: 1px solid var(--border-subtle);
  font-size: 0.76rem;
}

.metric-chip {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.metric-chip span {
  color: var(--text-muted);
}

.metric-chip strong {
  font-family: var(--font-mono);
  color: var(--wine-900);
}

/* Pasos del Protocolo */
.protocol-step {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
}

.protocol-step:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.step-header {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.step-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background-color: var(--wine-700);
  color: #FFFFFF;
  font-size: 0.75rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 0.15rem;
}

.step-title {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--wine-900);
}

.step-desc {
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.35;
  margin-top: 0.15rem;
}

/* Paso 1: Manual Check Form */
.manual-check-form {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.35rem;
}

.input-manual {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  outline: none;
}

.input-manual:focus {
  border-color: var(--wine-700);
}

.btn-save-manual {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.5rem 0.85rem;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.btn-save-manual:hover {
  background-color: var(--bg-hover);
  border-color: var(--wine-600);
}

.current-manual-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.78rem;
  color: #15803D;
  background-color: #F0FDF4;
  border: 1px solid #BBF7D0;
  padding: 0.3rem 0.65rem;
  border-radius: var(--radius-sm);
  align-self: flex-start;
}

/* Paso 2: Toggle Sensor */
.sensor-toggle-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.85rem 1rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.sensor-box--disabled {
  background-color: var(--status-danger-bg);
  border-color: var(--status-danger-border);
}

.sensor-info-text strong {
  display: block;
  font-size: 0.84rem;
  color: var(--text-primary);
}

.sensor-info-text p {
  font-size: 0.76rem;
  color: var(--text-secondary);
  margin-top: 0.15rem;
}

.status-on {
  color: var(--status-good);
  font-weight: 600;
}

.status-off {
  color: var(--status-danger);
  font-weight: 700;
}

.btn-toggle-sensor {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.85rem;
  border-radius: var(--radius-sm);
  font-size: 0.78rem;
  font-weight: 600;
  transition: all 0.15s ease;
}

.btn-toggle--disable {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border: 1px solid var(--status-danger-border);
}

.btn-toggle--disable:hover {
  background-color: var(--status-danger);
  color: #FFFFFF;
}

.btn-toggle--enable {
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border: 1px solid var(--status-good-border);
}

.btn-toggle--enable:hover {
  background-color: var(--status-good);
  color: #FFFFFF;
}

/* Paso 3: Notas */
.notes-timeline {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  max-height: 160px;
  overflow-y: auto;
  padding-right: 0.3rem;
}

.note-item {
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 0.6rem 0.75rem;
}

.note-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-bottom: 0.2rem;
}

.note-author {
  font-weight: 600;
  color: var(--wine-800);
}

.note-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.35;
}

.add-note-box {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-items: flex-end;
}

.textarea-note {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  font-family: inherit;
  resize: vertical;
  outline: none;
}

.textarea-note:focus {
  border-color: var(--wine-700);
}

.btn-add-note {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--wine-800);
  font-size: 0.78rem;
  font-weight: 600;
  padding: 0.35rem 0.85rem;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.btn-add-note:hover:not(:disabled) {
  background-color: var(--wine-700);
  color: #FFFFFF;
}

.btn-add-note:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Footer Modal */
.modal-footer {
  padding: 1.15rem 1.5rem;
  border-top: 1px solid var(--border-subtle);
  background-color: var(--bg-canvas);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.btn-modal-cancel {
  font-size: 0.82rem;
  color: var(--text-muted);
  font-weight: 500;
  transition: color 0.15s ease;
}

.btn-modal-cancel:hover {
  color: var(--text-primary);
}

.modal-footer-actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.btn-modal-progress {
  background-color: #E8F4FD;
  color: #1565C0;
  border: 1px solid #BBDEFB;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.5rem 0.95rem;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.btn-modal-progress:hover {
  background-color: #1565C0;
  color: #FFFFFF;
}

.btn-modal-resolve {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background-color: var(--wine-700);
  color: #FFFFFF;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.btn-modal-resolve:hover {
  background-color: var(--wine-800);
}

.resolved-label {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--status-good);
  font-weight: 600;
  font-size: 0.82rem;
}

/* =========================================
   ESTILOS NUEVOS DE INTEGRACION API
   ========================================= */
.title-with-counter {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex-wrap: wrap;
}

.badge-pending-header {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.25rem 0.75rem;
  font-size: 0.78rem;
  font-weight: 700;
  border-radius: var(--radius-full);
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border: 1px solid var(--status-danger-border);
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 1rem;
  border-radius: var(--radius-sm);
  background-color: var(--wine-900);
  color: #FFFFFF;
  border: 1px solid var(--wine-700);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-refresh:hover:not(:disabled) {
  background-color: var(--wine-800);
  transform: translateY(-1px);
}

.btn-refresh:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.btn-quick-attend {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.8rem;
  border-radius: var(--radius-sm);
  background-color: #E8F4FD;
  color: #1565C0;
  border: 1px solid #BBDEFB;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-right: 0.5rem;
}

.btn-quick-attend:hover:not(:disabled) {
  background-color: #D0E8FC;
  border-color: #90CAF9;
}

.state-banner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.8rem;
  padding: 4rem 2rem;
  background-color: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  text-align: center;
}

.text-wine {
  color: var(--wine-700);
}

.text-danger {
  color: var(--status-danger);
}

.btn-retry {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-sm);
  background-color: var(--wine-800);
  color: #FFFFFF;
  border: none;
  font-weight: 600;
  font-size: 0.84rem;
  cursor: pointer;
}

.badge-severity--critica,
.badge-severity--alta {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border: 1px solid var(--status-danger-border);
}

.badge-severity--media {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
  border: 1px solid var(--status-warn-border);
}

.badge-severity--baja {
  background-color: #E8F4FD;
  color: #1565C0;
  border: 1px solid #BBDEFB;
}

.badge-status--pendiente {
  background-color: #FDF4E7;
  color: #B25E09;
}

.badge-status--atendida {
  background-color: #E8F4FD;
  color: #1565C0;
}

.badge-status--resuelta {
  background-color: var(--status-good-bg);
  color: var(--status-good);
}

</style>
