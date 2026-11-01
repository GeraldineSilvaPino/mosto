<script setup>
/**
 * 📋 05. [FRONT - VUE] Pantalla de Alertas y Gestión de Incidencias
 * Módulo 3: Alertas y Protocolo
 *
 * Características implementadas:
 * 1. KPIs de resumen en vivo: Críticas, Advertencias, En Protocolo y Sensores Anulados.
 * 2. Tabla interactiva de alertas clasificadas por severidad (Crítica, Advertencia, Info).
 * 3. Filtros reactivos por severidad, estado, búsqueda libre y selector de cuba.
 * 4. Modal de Protocolo de Revisión del Enólogo:
 *    - Registro de notas de inspección técnica.
 *    - Acción operativa de anular/aislar el sensor defectuoso (DS18B20 / MPU-6050).
 *    - Ingreso de medición manual de contraste.
 *    - Resolución o mitigación de la incidencia con trazabilidad.
 * 5. 100% Frontend autónomo con datos mock reactivos.
 */
import { ref, computed } from 'vue'
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

// ==========================================
// ESTADO REACTIVO DE ALERTAS MOCK
// ==========================================
let nextAlertId = 100

const alerts = ref([
  {
    id: 1,
    cubaId: '02',
    cubaCode: 'CB-02',
    cubaName: 'Cuba 02 · Carménère Reserva',
    variety: 'Carménère',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Central',
    sensorDisabled: false,
    severity: 'danger', // danger (crítica) | warning (advertencia) | info (informativa)
    severityLabel: 'Crítica',
    title: 'Caída brusca de temperatura (-3.2°C en 2h)',
    description: 'La temperatura descendió de 20.7°C a 17.5°C sin intervención de enfriamiento. Riesgo inminente de parada de fermentación.',
    valueDetected: '17.5 °C',
    thresholdRule: 'Caída > 2.0°C / 2h (Mínimo: 20.0°C)',
    timestamp: 'Hace 15 min',
    dateIso: '2026-11-01 15:30',
    status: 'active', // active | in_progress | resolved
    statusLabel: 'Activa',
    assignedTo: 'Carlos Cartes',
    notes: [
      { id: 1, author: 'Sistema Telemetría', time: '15:30', text: 'Alerta generada automáticamente por sensor DS18B20.' }
    ],
    manualCheck: null
  },
  {
    id: 2,
    cubaId: '04',
    cubaCode: 'CB-04',
    cubaName: 'Cuba 04 · Syrah Gran Corte',
    variety: 'Syrah',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Central',
    sensorDisabled: false,
    severity: 'danger',
    severityLabel: 'Crítica',
    title: 'Sobrecalentamiento en pico fermentativo',
    description: 'La temperatura superó el umbral crítico de 28°C alcanzando 29.8°C. Levaduras en riesgo de desvitalización.',
    valueDetected: '29.8 °C',
    thresholdRule: 'Límite Máximo: 28.0 °C',
    timestamp: 'Hace 42 min',
    dateIso: '2026-11-01 15:02',
    status: 'in_progress',
    statusLabel: 'En Protocolo',
    assignedTo: 'Geraldine Silva',
    notes: [
      { id: 1, author: 'Sistema Telemetría', time: '15:02', text: 'Disparo por sobrepasar 28.0°C.' },
      { id: 2, author: 'Geraldine Silva', time: '15:12', text: 'Inspeccionada en terreno. Se incrementó caudal de camisa de enfriamiento.' }
    ],
    manualCheck: '29.4 °C (Termómetro manual)'
  },
  {
    id: 3,
    cubaId: '01',
    cubaCode: 'CB-01',
    cubaName: 'Cuba 01 · Cabernet Sauvignon',
    variety: 'Cabernet Sauvignon',
    sensorType: 'MPU-6050',
    sensorName: 'Cápsula Flotante Inclinómetro',
    sensorDisabled: false,
    severity: 'warning',
    severityLabel: 'Advertencia',
    title: 'Lectura de ángulo atípica / Posible bloqueo',
    description: 'El sensor registra una inclinación de 86° sostenida por 45 minutos. Posible retención del flotador en el sombrero de hollejos.',
    valueDetected: '86.2° (Brix incoherente)',
    thresholdRule: 'Rango físico esperado: 10° a 70°',
    timestamp: 'Hace 1 hora',
    dateIso: '2026-11-01 14:40',
    status: 'active',
    statusLabel: 'Activa',
    assignedTo: 'Sin asignar',
    notes: [
      { id: 1, author: 'Sistema Telemetría', time: '14:40', text: 'Inclinación fuera de los límites cinemáticos del hidrómetro.' }
    ],
    manualCheck: null
  },
  {
    id: 4,
    cubaId: '03',
    cubaCode: 'CB-03',
    cubaName: 'Cuba 03 · Sauvignon Blanc',
    variety: 'Sauvignon Blanc',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Estanco',
    sensorDisabled: false,
    severity: 'warning',
    severityLabel: 'Advertencia',
    title: 'Desvío hacia límite superior de fermentación en frío',
    description: 'La temperatura alcanzó 17.6°C en perfil blanco aromático (límite recomendado 17.0°C). Pérdida potencial de aromas volátiles.',
    valueDetected: '17.6 °C',
    thresholdRule: 'Banda recomendada: 13.0°C - 17.0°C',
    timestamp: 'Hace 3 horas',
    dateIso: '2026-11-01 12:45',
    status: 'active',
    statusLabel: 'Activa',
    assignedTo: 'Matias González',
    notes: [
      { id: 1, author: 'Sistema Telemetría', time: '12:45', text: 'Alerta preventiva emitida por desvío de perfil.' }
    ],
    manualCheck: null
  },
  {
    id: 5,
    cubaId: '02',
    cubaCode: 'CB-02',
    cubaName: 'Cuba 02 · Carménère Reserva',
    variety: 'Carménère',
    sensorType: 'MPU-6050',
    sensorName: 'Cápsula Flotante Inclinómetro',
    sensorDisabled: true, // Sensor anulado previamente
    severity: 'warning',
    severityLabel: 'Advertencia',
    title: 'Sensor flotador anulado por mantención de sombrero',
    description: 'El sensor fue aislado temporalmente por el enólogo para evitar falsas lecturas durante el remontado.',
    valueDetected: 'Sensor Anulado',
    thresholdRule: 'Aislamiento operativo',
    timestamp: 'Hace 4 horas',
    dateIso: '2026-11-01 11:20',
    status: 'in_progress',
    statusLabel: 'En Protocolo',
    assignedTo: 'Carlos Cartes',
    notes: [
      { id: 1, author: 'Carlos Cartes', time: '11:20', text: 'Se anula telemetría del flotador durante remontado con aireación.' }
    ],
    manualCheck: '18.4 °Bx (Refractómetro de mano)'
  },
  {
    id: 6,
    cubaId: '01',
    cubaCode: 'CB-01',
    cubaName: 'Cuba 01 · Cabernet Sauvignon',
    variety: 'Cabernet Sauvignon',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Central',
    sensorDisabled: false,
    severity: 'info',
    severityLabel: 'Informativa',
    title: 'Recuperación de temperatura tras remontado',
    description: 'La cuba regresó al rango óptimo de 24.5°C luego de la homogeneización matutina.',
    valueDetected: '24.5 °C',
    thresholdRule: 'Rango: 22.0°C - 28.0°C',
    timestamp: 'Hace 6 horas',
    dateIso: '2026-11-01 09:30',
    status: 'resolved',
    statusLabel: 'Resuelta',
    assignedTo: 'Geraldine Silva',
    notes: [
      { id: 1, author: 'Geraldine Silva', time: '09:35', text: 'Verificado. Parámetros estables.' }
    ],
    manualCheck: '24.5 °C'
  }
])

// ==========================================
// FILTROS Y ESTADO REACTIVO
// ==========================================
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
// KPIS COMPUTADOS
// ==========================================
const totalActive = computed(() => {
  return alerts.value.filter(a => a.status === 'active').length
})

const totalCritical = computed(() => {
  return alerts.value.filter(a => a.severity === 'danger' && a.status !== 'resolved').length
})

const totalWarning = computed(() => {
  return alerts.value.filter(a => a.severity === 'warning' && a.status !== 'resolved').length
})

const totalInProgress = computed(() => {
  return alerts.value.filter(a => a.status === 'in_progress').length
})

const totalDisabledSensors = computed(() => {
  return alerts.value.filter(a => a.sensorDisabled).length
})

// Lista filtrada
const filteredAlerts = computed(() => {
  return alerts.value.filter(alert => {
    // Filtro por texto
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      const matchText =
        alert.cubaName.toLowerCase().includes(q) ||
        alert.cubaCode.toLowerCase().includes(q) ||
        alert.title.toLowerCase().includes(q) ||
        alert.description.toLowerCase().includes(q) ||
        alert.sensorType.toLowerCase().includes(q) ||
        alert.assignedTo.toLowerCase().includes(q)
      if (!matchText) return false
    }

    // Filtro por severidad
    if (filterSeverity.value !== 'all' && alert.severity !== filterSeverity.value) {
      return false
    }

    // Filtro por estado
    if (filterStatus.value !== 'all' && alert.status !== filterStatus.value) {
      return false
    }

    // Filtro por cuba
    if (filterCuba.value !== 'all' && alert.cubaId !== filterCuba.value) {
      return false
    }

    return true
  })
})

// Opciones de cubas únicas para el select
const cubasAvailable = computed(() => {
  const map = new Map()
  alerts.value.forEach(a => {
    if (!map.has(a.cubaId)) {
      map.set(a.cubaId, { id: a.cubaId, code: a.cubaCode, name: a.cubaName })
    }
  })
  return Array.from(map.values())
})

// ==========================================
// ACCIONES
// ==========================================
function showToast(msg) {
  toastMessage.value = msg
  setTimeout(() => {
    toastMessage.value = ''
  }, 4000)
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

// Acción: Anular / Reactivar Sensor
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

// Acción: Guardar Nota de Terreno
function addNote() {
  if (!newNoteText.value.trim() || !selectedAlert.value) return

  selectedAlert.value.notes.push({
    id: Date.now(),
    author: 'Enólogo en Turno',
    time: new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
    text: newNoteText.value.trim()
  })

  // Si estaba activa pasa automáticamente a en progreso
  if (selectedAlert.value.status === 'active') {
    selectedAlert.value.status = 'in_progress'
    selectedAlert.value.statusLabel = 'En Protocolo'
  }

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

// Acción: Marcar como Resuelta
function resolveAlert() {
  if (!selectedAlert.value) return

  selectedAlert.value.status = 'resolved'
  selectedAlert.value.statusLabel = 'Resuelta'
  selectedAlert.value.notes.push({
    id: Date.now(),
    author: 'Enólogo en Turno',
    time: new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
    text: 'Incidencia cerrada y protocolo completado satisfactoriamente.'
  })

  showToast(`Incidencia en ${selectedAlert.value.cubaCode} marcada como RESUELTA.`)
  closeProtocol()
}

// Acción: Dejar en Protocolo / En Observación
function keepInObservation() {
  if (!selectedAlert.value) return

  selectedAlert.value.status = 'in_progress'
  selectedAlert.value.statusLabel = 'En Protocolo'
  showToast(`Incidencia en ${selectedAlert.value.cubaCode} guardada en estado EN PROTOCOLO.`)
  closeProtocol()
}

// Simular alerta nueva de prueba
function simulateNewAlert() {
  const newId = ++nextAlertId
  const simulated = {
    id: newId,
    cubaId: '02',
    cubaCode: 'CB-02',
    cubaName: 'Cuba 02 · Carménère Reserva',
    variety: 'Carménère',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Central',
    sensorDisabled: false,
    severity: 'danger',
    severityLabel: 'Crítica',
    title: 'Variación Térmica Repentina (+2.3°C en 30m)',
    description: 'Alza brusca de temperatura detectada en Cuba 02. Revisar si la camisa de refrigeración sufrió corte de suministro.',
    valueDetected: '26.8 °C',
    thresholdRule: 'Tasa máx permitida: +1.5°C/h',
    timestamp: 'Ahora mismo',
    dateIso: new Date().toISOString(),
    status: 'active',
    statusLabel: 'Activa',
    assignedTo: 'Sin asignar',
    notes: [
      { id: 1, author: 'Simulador IoT', time: 'Ahora', text: 'Disparo de prueba por evento térmico inesperado.' }
    ],
    manualCheck: null
  }

  alerts.value.unshift(simulated)
  showToast('¡Alerta simulada generada exitosamente en Cuba 02!')
}
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
        <h1 class="view-title">Alertas y Gestión de Incidencias</h1>
        <p class="view-subtitle">
          Supervisión en tiempo real de anomalías de fermentación, fallas en sensores DS18B20 / MPU-6050 y protocolo operativo del enólogo.
        </p>
      </div>

      <div class="header-actions">
        <button class="btn-simulate" @click="simulateNewAlert" title="Genera una alerta de prueba en vivo">
          <PlusCircle :size="15" />
          <span>Simular Alerta de Prueba</span>
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
      <div v-if="filteredAlerts.length === 0" class="empty-state">
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
                  class="btn-attend"
                  :class="alert.status === 'resolved' ? 'btn-attend--resolved' : 'btn-attend--active'"
                  @click="openProtocol(alert)"
                >
                  <component :is="alert.status === 'resolved' ? Check : ShieldAlert" :size="15" />
                  <span>{{ alert.status === 'resolved' ? 'Ver Bitácora' : 'Atender Incidencia' }}</span>
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
              v-if="selectedAlert.status !== 'in_progress' && selectedAlert.status !== 'resolved'"
              class="btn-modal-progress"
              @click="keepInObservation"
            >
              Mantener en Protocolo
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
</style>
