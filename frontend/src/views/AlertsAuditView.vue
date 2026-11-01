<script setup>
/**
 * 📋 11. [FRONT - VUE] Pantalla de Historial de Alertas / Auditoría
 * Módulo 5: Administración SaaS y Gestión de Empresa
 *
 * Características implementadas:
 * 1. Métricas clave de auditoría (MTTR, tasa de resolución, falsas alarmas, total archivadas).
 * 2. Tabla de auditoría con ordenación y trazabilidad enológica completa.
 * 3. Filtros reactivos por rango de fechas (7 días, 30 días, Vendimia 2026 o selector libre), severidad, estado y cuba.
 * 4. Modal interactivo de ficha de auditoría con la cronología de intervención del enólogo.
 * 5. Función de exportación real a archivo CSV descargable en el navegador.
 * 6. 100% Frontend autónomo con datos mock enriquecidos.
 */
import { ref, computed } from 'vue'
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
  ArrowUpDown
} from 'lucide-vue-next'

// ==========================================
// REGISTROS HISTÓRICOS DE AUDITORÍA MOCK
// ==========================================
const auditLogs = ref([
  {
    id: 'INC-1048',
    cubaId: '02',
    cubaCode: 'CB-02',
    cubaName: 'Cuba 02 · Carménère Reserva',
    variety: 'Carménère',
    lot: 'Lote CM-2026-B',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Central',
    severity: 'danger',
    severityLabel: 'Crítica',
    title: 'Caída brusca de temperatura (-3.2°C en 2h)',
    triggerValue: '17.5 °C',
    thresholdRule: 'Caída > 2.0°C / 2h (Mín. 20.0°C)',
    detectedAt: '2026-11-01 15:30',
    resolvedAt: '2026-11-01 15:52',
    resolutionTimeMin: 22,
    resolutionType: 'mitigated',
    resolutionLabel: 'Mitigada en Terreno',
    resolvedBy: 'Carlos Cartes',
    role: 'Enólogo de Turno',
    summaryResolution: 'Ajuste de camisa térmica y adición de nutrientes para prevenir parada.',
    timeline: [
      { time: '15:30', author: 'Sistema Telemetría', text: 'Disparo automático de alerta por gradiente térmico negativo brusco.' },
      { time: '15:38', author: 'Carlos Cartes', text: 'Inspección física en bodega. Medición manual confirma 17.6°C con termómetro analógico.' },
      { time: '15:45', author: 'Carlos Cartes', text: 'Se cerró válvula de glicol de la camisa exterior para permitir atemperamiento natural.' },
      { time: '15:52', author: 'Carlos Cartes', text: 'Temperatura estabilizada en 18.2°C. Incidencia mitigada y bajo observación.' }
    ]
  },
  {
    id: 'INC-1047',
    cubaId: '04',
    cubaCode: 'CB-04',
    cubaName: 'Cuba 04 · Syrah Gran Corte',
    variety: 'Syrah',
    lot: 'Lote SY-2026-C',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Central',
    severity: 'danger',
    severityLabel: 'Crítica',
    title: 'Sobrecalentamiento en pico fermentativo',
    triggerValue: '29.8 °C',
    thresholdRule: 'Límite Máximo: 28.0 °C',
    detectedAt: '2026-11-01 15:02',
    resolvedAt: '2026-11-01 15:36',
    resolutionTimeMin: 34,
    resolutionType: 'resolved',
    resolutionLabel: 'Resuelta',
    resolvedBy: 'Geraldine Silva',
    role: 'Enóloga Asistente',
    summaryResolution: 'Aumento de caudal de refrigeración y remontado cerrado para homogenizar.',
    timeline: [
      { time: '15:02', author: 'Sistema Telemetría', text: 'Temperatura supera los 28.0°C alcanzando 29.8°C.' },
      { time: '15:12', author: 'Geraldine Silva', text: 'Apertura manual al 100% de electroválvula de enfriamiento.' },
      { time: '15:25', author: 'Geraldine Silva', text: 'Remontado de 15 minutos para disipar bolsa de calor del sombrero.' },
      { time: '15:36', author: 'Geraldine Silva', text: 'Temperatura estabilizada en 26.5°C. Incidencia cerrada.' }
    ]
  },
  {
    id: 'INC-1046',
    cubaId: '01',
    cubaCode: 'CB-01',
    cubaName: 'Cuba 01 · Cabernet Sauvignon',
    variety: 'Cabernet Sauvignon',
    lot: 'Lote CS-2026-A',
    sensorType: 'MPU-6050',
    sensorName: 'Cápsula Flotante Inclinómetro',
    severity: 'warning',
    severityLabel: 'Advertencia',
    title: 'Lectura de ángulo atípica / Sensor retenido',
    triggerValue: '86.2° (Fuera de rango)',
    thresholdRule: 'Rango cinemático: 10° a 70°',
    detectedAt: '2026-11-01 14:40',
    resolvedAt: '2026-11-01 15:05',
    resolutionTimeMin: 25,
    resolutionType: 'false_alarm',
    resolutionLabel: 'Sensor Descalibrado / Aislado',
    resolvedBy: 'Matias González',
    role: 'Técnico de Bodega',
    summaryResolution: 'Flotador trabado en hollejos. Se liberó manualmente y se limpió cápsula.',
    timeline: [
      { time: '14:40', author: 'Sistema Telemetría', text: 'Inclinación angular anormal de 86.2° reportada sostenidamente.' },
      { time: '14:50', author: 'Matias González', text: 'Inspección ocular: Cápsula atrapada en el sombrero tras pisado.' },
      { time: '15:00', author: 'Matias González', text: 'Sensor reposicionado libremente en el mosto líquido.' },
      { time: '15:05', author: 'Matias González', text: 'Ángulo normalizado a 42.5° (13.2 °Bx). Caso cerrado como falso positivo.' }
    ]
  },
  {
    id: 'INC-1045',
    cubaId: '03',
    cubaCode: 'CB-03',
    cubaName: 'Cuba 03 · Sauvignon Blanc',
    variety: 'Sauvignon Blanc',
    lot: 'Lote SB-2026-F',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Estanco',
    severity: 'warning',
    severityLabel: 'Advertencia',
    title: 'Desvío hacia límite superior de blanco aromático',
    triggerValue: '17.6 °C',
    thresholdRule: 'Banda máxima: 17.0 °C',
    detectedAt: '2026-10-31 09:15',
    resolvedAt: '2026-10-31 09:40',
    resolutionTimeMin: 25,
    resolutionType: 'resolved',
    resolutionLabel: 'Resuelta',
    resolvedBy: 'Carlos Cartes',
    role: 'Enólogo de Turno',
    summaryResolution: 'Activación de camisa de frío auxiliar a 12°C. Temperatura recuperada a 15.1°C.',
    timeline: [
      { time: '09:15', author: 'Sistema Telemetría', text: 'Alerta por rebase térmico en vino blanco.' },
      { time: '09:22', author: 'Carlos Cartes', text: 'Ajuste de consigna de chiller de bodega.' },
      { time: '09:40', author: 'Carlos Cartes', text: 'Cuba operando en 15.1°C óptimo.' }
    ]
  },
  {
    id: 'INC-1044',
    cubaId: '02',
    cubaCode: 'CB-02',
    cubaName: 'Cuba 02 · Carménère Reserva',
    variety: 'Carménère',
    lot: 'Lote CM-2026-B',
    sensorType: 'MPU-6050',
    sensorName: 'Cápsula Flotante Inclinómetro',
    severity: 'warning',
    severityLabel: 'Advertencia',
    title: 'Estancamiento de Grados Brix prolongado (>14h)',
    triggerValue: '18.4 °Bx (Sin cambio)',
    thresholdRule: 'Horas máx. sin consumo: 12h',
    detectedAt: '2026-10-30 22:10',
    resolvedAt: '2026-10-31 01:15',
    resolutionTimeMin: 185,
    resolutionType: 'mitigated',
    resolutionLabel: 'Mitigada en Terreno',
    resolvedBy: 'Carlos Cartes',
    role: 'Enólogo de Turno',
    summaryResolution: 'Inoculación de levaduras reactivadas y aireación suave del mosto.',
    timeline: [
      { time: '22:10', author: 'Sistema Telemetría', text: 'Curva de Brix plana por 14 horas consecutivas.' },
      { time: '23:00', author: 'Carlos Cartes', text: 'Toma de muestra de laboratorio: Azúcares reductores confirmados en 18.4 °Bx.' },
      { time: '00:15', author: 'Carlos Cartes', text: 'Pie de cuba añadido para resembrar fermentación.' },
      { time: '01:15', author: 'Carlos Cartes', text: 'Comienza reinicio de desprendimiento de CO₂.' }
    ]
  },
  {
    id: 'INC-1043',
    cubaId: '05',
    cubaCode: 'CB-05',
    cubaName: 'Cuba 05 · Chardonnay Finca',
    variety: 'Chardonnay',
    lot: 'Lote CH-2026-D',
    sensorType: 'MPU-6050',
    sensorName: 'Cápsula Flotante Inclinómetro',
    severity: 'info',
    severityLabel: 'Informativa',
    title: 'Batería baja en módulo flotante IoT (< 15%)',
    triggerValue: '14% Batería',
    thresholdRule: 'Umbral de advertencia: 20%',
    detectedAt: '2026-10-29 11:00',
    resolvedAt: '2026-10-29 11:30',
    resolutionTimeMin: 30,
    resolutionType: 'resolved',
    resolutionLabel: 'Resuelta',
    resolvedBy: 'Matias González',
    role: 'Técnico de Bodega',
    summaryResolution: 'Reemplazo de cápsula por unidad de repuesto de bodega y puesta a cargar.',
    timeline: [
      { time: '11:00', author: 'Sistema Telemetría', text: 'Nivel de batería en 14%.' },
      { time: '11:20', author: 'Matias González', text: 'Se extrae cápsula flotante y se coloca nodo de repuesto ESP32-SPARE-01.' },
      { time: '11:30', author: 'Matias González', text: 'Calibración OK y telemetría restablecida.' }
    ]
  },
  {
    id: 'INC-1042',
    cubaId: '01',
    cubaCode: 'CB-01',
    cubaName: 'Cuba 01 · Cabernet Sauvignon',
    variety: 'Cabernet Sauvignon',
    lot: 'Lote CS-2026-A',
    sensorType: 'DS18B20',
    sensorName: 'Sonda Térmica Central',
    severity: 'info',
    severityLabel: 'Informativa',
    title: 'Oscilación térmica transitoria por remontado',
    triggerValue: '25.8 °C',
    thresholdRule: 'Banda: 22.0°C - 28.0°C',
    detectedAt: '2026-10-28 17:00',
    resolvedAt: '2026-10-28 17:18',
    resolutionTimeMin: 18,
    resolutionType: 'resolved',
    resolutionLabel: 'Resuelta',
    resolvedBy: 'Geraldine Silva',
    role: 'Enóloga Asistente',
    summaryResolution: 'Normalización automática al finalizar la recirculación de la bomba.',
    timeline: [
      { time: '17:00', author: 'Sistema Telemetría', text: 'Incremento de 0.8°C durante operación de bombeo.' },
      { time: '17:18', author: 'Geraldine Silva', text: 'Masa térmica equilibrada tras homogeneización.' }
    ]
  }
])

// ==========================================
// FILTROS Y ESTADO REACTIVO
// ==========================================
const searchQuery = ref('')
const datePreset = ref('all') // all | 7d | 30d | vintage
const filterSeverity = ref('all')
const filterResolution = ref('all') // all | resolved | mitigated | false_alarm
const filterCuba = ref('all')

const isAuditModalOpen = ref(false)
const selectedIncident = ref(null)
const toastMessage = ref('')

// KPIs Computados
const totalIncidents = computed(() => auditLogs.value.length)

const avgResolutionTime = computed(() => {
  const sum = auditLogs.value.reduce((acc, curr) => acc + curr.resolutionTimeMin, 0)
  return Math.round(sum / auditLogs.value.length)
})

const resolutionRate = computed(() => {
  const resolved = auditLogs.value.filter(i => i.resolutionType === 'resolved' || i.resolutionType === 'mitigated').length
  return ((resolved / auditLogs.value.length) * 100).toFixed(1)
})

const totalFalseAlarms = computed(() => {
  return auditLogs.value.filter(i => i.resolutionType === 'false_alarm').length
})

// Filtrado de auditoría
const filteredLogs = computed(() => {
  return auditLogs.value.filter(item => {
    // Buscador
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      const match =
        item.id.toLowerCase().includes(q) ||
        item.cubaName.toLowerCase().includes(q) ||
        item.cubaCode.toLowerCase().includes(q) ||
        item.title.toLowerCase().includes(q) ||
        item.resolvedBy.toLowerCase().includes(q) ||
        item.sensorType.toLowerCase().includes(q)
      if (!match) return false
    }

    // Severidad
    if (filterSeverity.value !== 'all' && item.severity !== filterSeverity.value) {
      return false
    }

    // Resolución
    if (filterResolution.value !== 'all' && item.resolutionType !== filterResolution.value) {
      return false
    }

    // Cuba
    if (filterCuba.value !== 'all' && item.cubaId !== filterCuba.value) {
      return false
    }

    // Rango de fechas (simulado por presets)
    if (datePreset.value === '7d') {
      // Filtra las más recientes (ej: 31-10 o 01-11)
      if (!item.detectedAt.includes('2026-11') && !item.detectedAt.includes('2026-10-31')) return false
    }

    return true
  })
})

// Cubas únicas
const cubasAvailable = computed(() => {
  const map = new Map()
  auditLogs.value.forEach(i => {
    if (!map.has(i.cubaId)) {
      map.set(i.cubaId, { id: i.cubaId, code: i.cubaCode, name: i.cubaName })
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

function openAuditModal(item) {
  selectedIncident.value = item
  isAuditModalOpen.value = true
}

function closeAuditModal() {
  isAuditModalOpen.value = false
  selectedIncident.value = null
}

// Exportación Real a CSV
function exportToCSV() {
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
    `"${i.title.replace(/"/g, '""')}"`,
    `"${i.triggerValue}"`,
    `"${i.thresholdRule}"`,
    i.resolutionTimeMin,
    i.resolutionLabel,
    `"${i.resolvedBy}"`
  ])

  const csvContent = '\uFEFF' + [headers.join(';'), ...rows.map(r => r.join(';'))].join('\r\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', `auditoria_alertas_mosto_${new Date().toISOString().slice(0, 10)}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

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
    <header class="audit-header">
      <div>
        <div class="module-tag">Módulo 5 · Administración SaaS y Gestión de Empresa</div>
        <h1 class="view-title">Historial de Alertas y Auditoría</h1>
        <p class="view-subtitle">
          Archivo histórico consolidado de incidencias enológicas, trazabilidad de protocolos aplicados y tiempos de respuesta de bodega.
        </p>
      </div>

      <div class="header-actions">
        <button class="btn-primary" @click="exportToCSV" title="Descargar informe completo en formato CSV para Excel">
          <Download :size="16" />
          <span>Exportar Informe (CSV)</span>
        </button>
      </div>
    </header>

    <!-- Tarjetas KPIs de Auditoría -->
    <section class="kpi-grid">
      <!-- 1. Total Archivadas -->
      <div class="kpi-card">
        <div class="kpi-top">
          <span class="kpi-label">Incidencias Totales</span>
          <div class="kpi-icon-box kpi-icon--neutral">
            <Layers :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalIncidents }}</div>
        <div class="kpi-sub">
          <span>Temporada Vendimia 2026</span>
        </div>
      </div>

      <!-- 2. Tiempo Medio de Respuesta -->
      <div class="kpi-card">
        <div class="kpi-top">
          <span class="kpi-label">Tiempo Medio de Respuesta</span>
          <div class="kpi-icon-box kpi-icon--time">
            <Clock :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ avgResolutionTime }} <span class="kpi-unit">min</span></div>
        <div class="kpi-sub">
          <span>MTTR promedio en terreno</span>
        </div>
      </div>

      <!-- 3. Tasa de Efectividad -->
      <div class="kpi-card">
        <div class="kpi-top">
          <span class="kpi-label">Tasa de Resolución</span>
          <div class="kpi-icon-box kpi-icon--good">
            <ShieldCheck :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ resolutionRate }}%</div>
        <div class="kpi-sub">
          <span>Incidencias resueltas o mitigadas</span>
        </div>
      </div>

      <!-- 4. Falsas Alarmas -->
      <div class="kpi-card">
        <div class="kpi-top">
          <span class="kpi-label">Sensores Descalibrados</span>
          <div class="kpi-icon-box kpi-icon--warn">
            <Compass :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalFalseAlarms }}</div>
        <div class="kpi-sub">
          <span>Falsos positivos (flotador trabado)</span>
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
          <option value="danger">Críticas</option>
          <option value="warning">Advertencias</option>
          <option value="info">Informativas</option>
        </select>

        <!-- Tipo de Resolución -->
        <select v-model="filterResolution" class="select-filter">
          <option value="all">Resolución: Todas</option>
          <option value="resolved">Resuelta</option>
          <option value="mitigated">Mitigada</option>
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
                <span class="time-cell">{{ log.resolutionTimeMin }} min</span>
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
              <strong class="meta-box-val">{{ selectedIncident.resolutionTimeMin }} minutos (Cierre: {{ selectedIncident.resolvedAt }})</strong>
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

          <!-- Dictamen Final del Enólogo -->
          <div class="summary-action-box">
            <span class="summary-action-title">Dictamen y Protocolo Aplicado:</span>
            <p class="summary-action-text">{{ selectedIncident.summaryResolution }}</p>
            <div class="signature-row">
              <span class="signature-name">Firmado por: <strong>{{ selectedIncident.resolvedBy }}</strong> ({{ selectedIncident.role }})</span>
            </div>
          </div>

          <!-- Línea de Tiempo de Intervención -->
          <div class="timeline-section">
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
          <button class="btn-secondary" @click="closeAuditModal">
            Cerrar Ficha
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
  display: flex;
  flex-direction: column;
  justify-content: space-between;
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

/* 3. Tabla de Auditoría */
.audit-table-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-subtle);
  overflow: hidden;
}

.table-header-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.15rem 1.5rem;
  border-bottom: 1px solid var(--border-subtle);
}

.table-title {
  font-family: var(--font-serif);
  font-size: 1.25rem;
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
  font-size: 0.82rem;
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
  background-color: var(--bg-canvas);
}
</style>
