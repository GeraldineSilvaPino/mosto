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
import cubaService from '../services/cubaService'

// ==========================================
// REGISTROS HISTÓRICOS DE AUDITORÍA MOCK (FALLBACK RESILIENTE)
// ==========================================
const initialMockAuditLogs = [
  {
    id: 'INC-1048',
    rawId: 1048,
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
    detectedAtRaw: '2026-11-01T15:30:00Z',
    resolvedAt: '2026-11-01 15:52',
    resolvedAtRaw: '2026-11-01T15:52:00Z',
    resolutionTimeMin: 22,
    status: 'resolved',
    statusBackend: 'resuelta',
    resolutionType: 'mitigated',
    resolutionLabel: 'Mitigada en Terreno',
    resolvedBy: 'Carlos Cartes',
    role: 'Enólogo de Turno',
    summaryResolution: 'Ajuste de camisa térmica y adición de nutrientes para prevenir parada.',
    nota_resolucion: 'Ajuste de camisa térmica y adición de nutrientes para prevenir parada.',
    timeline: [
      { time: '15:30', author: 'Sistema Telemetría', text: 'Disparo automático de alerta por gradiente térmico negativo brusco.' },
      { time: '15:38', author: 'Carlos Cartes', text: 'Inspección física en bodega. Medición manual confirma 17.6°C con termómetro analógico.' },
      { time: '15:45', author: 'Carlos Cartes', text: 'Se cerró válvula de glicol de la camisa exterior para permitir atemperamiento natural.' },
      { time: '15:52', author: 'Carlos Cartes', text: 'Temperatura estabilizada en 18.2°C. Incidencia mitigada y bajo observación.' }
    ]
  },
  {
    id: 'INC-1047',
    rawId: 1047,
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
    detectedAtRaw: '2026-11-01T15:02:00Z',
    resolvedAt: '2026-11-01 15:36',
    resolvedAtRaw: '2026-11-01T15:36:00Z',
    resolutionTimeMin: 34,
    status: 'resolved',
    statusBackend: 'resuelta',
    resolutionType: 'resolved',
    resolutionLabel: 'Resuelta',
    resolvedBy: 'Geraldine Silva',
    role: 'Enóloga Asistente',
    summaryResolution: 'Aumento de caudal de refrigeración y remontado cerrado para homogenizar.',
    nota_resolucion: 'Aumento de caudal de refrigeración y remontado cerrado para homogenizar.',
    timeline: [
      { time: '15:02', author: 'Sistema Telemetría', text: 'Temperatura supera los 28.0°C alcanzando 29.8°C.' },
      { time: '15:12', author: 'Geraldine Silva', text: 'Apertura manual al 100% de electroválvula de enfriamiento.' },
      { time: '15:25', author: 'Geraldine Silva', text: 'Remontado de 15 minutos para disipar bolsa de calor del sombrero.' },
      { time: '15:36', author: 'Geraldine Silva', text: 'Temperatura estabilizada en 26.5°C. Incidencia cerrada.' }
    ]
  },
  {
    id: 'INC-1046',
    rawId: 1046,
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
    detectedAtRaw: '2026-11-01T14:40:00Z',
    resolvedAt: '2026-11-01 15:05',
    resolvedAtRaw: '2026-11-01T15:05:00Z',
    resolutionTimeMin: 25,
    status: 'resolved',
    statusBackend: 'resuelta',
    resolutionType: 'false_alarm',
    resolutionLabel: 'Sensor Descalibrado / Aislado',
    resolvedBy: 'Matias González',
    role: 'Técnico de Bodega',
    summaryResolution: 'Flotador trabado en hollejos. Se liberó manualmente y se limpió cápsula.',
    nota_resolucion: 'Flotador trabado en hollejos. Se liberó manualmente y se limpió cápsula.',
    timeline: [
      { time: '14:40', author: 'Sistema Telemetría', text: 'Inclinación angular anormal de 86.2° reportada sostenidamente.' },
      { time: '14:50', author: 'Matias González', text: 'Inspección ocular: Cápsula atrapada en el sombrero tras pisado.' },
      { time: '15:00', author: 'Matias González', text: 'Sensor reposicionado libremente en el mosto líquido.' },
      { time: '15:05', author: 'Matias González', text: 'Ángulo normalizado a 42.5° (13.2 °Bx). Caso cerrado como falso positivo.' }
    ]
  },
  {
    id: 'INC-1045',
    rawId: 1045,
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
    detectedAtRaw: '2026-10-31T09:15:00Z',
    resolvedAt: '2026-10-31 09:40',
    resolvedAtRaw: '2026-10-31T09:40:00Z',
    resolutionTimeMin: 25,
    status: 'resolved',
    statusBackend: 'resuelta',
    resolutionType: 'resolved',
    resolutionLabel: 'Resuelta',
    resolvedBy: 'Carlos Cartes',
    role: 'Enólogo de Turno',
    summaryResolution: 'Activación de camisa de frío auxiliar a 12°C. Temperatura recuperada a 15.1°C.',
    nota_resolucion: 'Activación de camisa de frío auxiliar a 12°C. Temperatura recuperada a 15.1°C.',
    timeline: [
      { time: '09:15', author: 'Sistema Telemetría', text: 'Alerta por rebase térmico en vino blanco.' },
      { time: '09:22', author: 'Carlos Cartes', text: 'Ajuste de consigna de chiller de bodega.' },
      { time: '09:40', author: 'Carlos Cartes', text: 'Cuba operando en 15.1°C óptimo.' }
    ]
  },
  {
    id: 'INC-1044',
    rawId: 1044,
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
    detectedAtRaw: '2026-10-30T22:10:00Z',
    resolvedAt: '2026-10-31 01:15',
    resolvedAtRaw: '2026-10-31T01:15:00Z',
    resolutionTimeMin: 185,
    status: 'resolved',
    statusBackend: 'resuelta',
    resolutionType: 'mitigated',
    resolutionLabel: 'Mitigada en Terreno',
    resolvedBy: 'Carlos Cartes',
    role: 'Enólogo de Turno',
    summaryResolution: 'Inoculación de levaduras reactivadas y aireación suave del mosto.',
    nota_resolucion: 'Inoculación de levaduras reactivadas y aireación suave del mosto.',
    timeline: [
      { time: '22:10', author: 'Sistema Telemetría', text: 'Curva de Brix plana por 14 horas consecutivas.' },
      { time: '23:00', author: 'Carlos Cartes', text: 'Toma de muestra de laboratorio: Azúcares reductores confirmados en 18.4 °Bx.' },
      { time: '00:15', author: 'Carlos Cartes', text: 'Pie de cuba añadido para resembrar fermentación.' },
      { time: '01:15', author: 'Carlos Cartes', text: 'Comienza reinicio de desprendimiento de CO₂.' }
    ]
  },
  {
    id: 'INC-1043',
    rawId: 1043,
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
    detectedAtRaw: '2026-10-29T11:00:00Z',
    resolvedAt: '2026-10-29 11:30',
    resolvedAtRaw: '2026-10-29T11:30:00Z',
    resolutionTimeMin: 30,
    status: 'resolved',
    statusBackend: 'resuelta',
    resolutionType: 'resolved',
    resolutionLabel: 'Resuelta',
    resolvedBy: 'Matias González',
    role: 'Técnico de Bodega',
    summaryResolution: 'Reemplazo de cápsula por unidad de repuesto de bodega y puesta a cargar.',
    nota_resolucion: 'Reemplazo de cápsula por unidad de repuesto de bodega y puesta a cargar.',
    timeline: [
      { time: '11:00', author: 'Sistema Telemetría', text: 'Nivel de batería en 14%.' },
      { time: '11:20', author: 'Matias González', text: 'Se extrae cápsula flotante y se coloca nodo de repuesto ESP32-SPARE-01.' },
      { time: '11:30', author: 'Matias González', text: 'Calibración OK y telemetría restablecida.' }
    ]
  },
  {
    id: 'INC-1042',
    rawId: 1042,
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
    detectedAtRaw: '2026-10-28T17:00:00Z',
    resolvedAt: '2026-10-28 17:18',
    resolvedAtRaw: '2026-10-28T17:18:00Z',
    resolutionTimeMin: 18,
    status: 'resolved',
    statusBackend: 'resuelta',
    resolutionType: 'resolved',
    resolutionLabel: 'Resuelta',
    resolvedBy: 'Geraldine Silva',
    role: 'Enóloga Asistente',
    summaryResolution: 'Normalización automática al finalizar la recirculación de la bomba.',
    nota_resolucion: 'Normalización automática al finalizar la recirculación de la bomba.',
    timeline: [
      { time: '17:00', author: 'Sistema Telemetría', text: 'Incremento de 0.8°C durante operación de bombeo.' },
      { time: '17:18', author: 'Geraldine Silva', text: 'Masa térmica equilibrada tras homogeneización.' }
    ]
  }
]

// ==========================================
// ESTADO REACTIVO
// ==========================================
const auditLogs = ref([...initialMockAuditLogs])
const cubasList = ref([])
const isLoading = ref(false)
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
  mttr_promedio_minutos: 0,
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
  let resolutionTimeMin = 0
  if (dto.timestamp && dto.fecha_resolucion) {
    const diffMs = new Date(dto.fecha_resolucion) - new Date(dto.timestamp)
    resolutionTimeMin = Math.max(1, Math.round(diffMs / 60000))
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
      author: dto.operador_nombre || 'Operador Enológico Principal',
      text: dto.nota_atencion || 'Atención técnica iniciada e inspección de cuba.'
    })
  }
  if (dto.fecha_resolucion || dto.nota_resolucion) {
    timeline.push({
      time: dto.fecha_resolucion
        ? new Date(dto.fecha_resolucion).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })
        : 'Resuelta',
      author: dto.operador_nombre || 'Operador Enológico Principal',
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
    variety: dto.variedad || 'Cabernet Sauvignon',
    lot: `Lote ${cubaCode}-2026`,
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
    resolvedBy: dto.operador_nombre || (status === 'resolved' ? 'Operador Enológico Principal' : 'Sin asignar'),
    role: dto.operador_nombre ? 'Operador de Bodega' : (status === 'resolved' ? 'Enólogo de Turno' : 'Pendiente'),
    summaryResolution: dto.nota_resolucion || dto.nota_atencion || (status === 'resolved' ? 'Incidencia resuelta.' : 'Incidencia activa.'),
    nota_resolucion: dto.nota_resolucion || '',
    timeline
  }
}

// ==========================================
// CARGA DE DATOS Y CONSUMO DE ENDPOINTS
// ==========================================
async function loadMetricas() {
  try {
    const cubaIdParam = filterCuba.value !== 'all' ? filterCuba.value : null
    const data = await alertService.obtenerMetricas(cubaIdParam)
    if (data) {
      metricas.value = {
        total_alertas: data.total_alertas ?? 0,
        alertas_activas: data.alertas_activas ?? 0,
        alertas_criticas: data.alertas_criticas ?? 0,
        total_resueltas: data.total_resueltas ?? 0,
        mttr_promedio_minutos: typeof data.mttr_promedio_minutos === 'number' ? Number(data.mttr_promedio_minutos.toFixed(1)) : 0,
        tasa_resolucion_pct: typeof data.tasa_resolucion_pct === 'number' ? Number(data.tasa_resolucion_pct.toFixed(1)) : 0
      }
    }
  } catch (err) {
    console.error('Error al cargar métricas MTTR del backend:', err)
  }
}

function calcularMetricasFallback() {
  const total = auditLogs.value.length
  const resueltas = auditLogs.value.filter(i => i.status === 'resolved' || i.resolutionType === 'resolved').length
  const activas = total - resueltas
  const criticas = auditLogs.value.filter(
    i => (i.severity === 'danger' || i.severityLabel === 'Crítica' || i.severityLabel === 'Alta') &&
         i.resolutionType !== 'resolved'
  ).length
  const sumaMin = auditLogs.value
    .filter(i => i.resolutionType === 'resolved')
    .reduce((acc, curr) => acc + (Number(curr.resolutionTimeMin) || 0), 0)
  const mttr = resueltas > 0 ? Number((sumaMin / resueltas).toFixed(1)) : 0
  const tasa = total > 0 ? Number(((resueltas / total) * 100).toFixed(1)) : 0

  metricas.value = {
    total_alertas: total,
    alertas_activas: activas,
    alertas_criticas: criticas,
    total_resueltas: resueltas,
    mttr_promedio_minutos: mttr,
    tasa_resolucion_pct: tasa
  }
}

async function loadData(showToastFeedback = false) {
  isLoading.value = true
  try {
    // 1. Cargar métricas oficiales calculadas por backend (GET /api/alertas/metricas)
    await loadMetricas()

    // 2. Cargar historial completo de alertas (GET /api/alertas)
    const alertsData = await alertService.listarAlertas()
    if (Array.isArray(alertsData) && alertsData.length > 0) {
      auditLogs.value = alertsData.map(mapBackendAlertToAudit)
    } else if (auditLogs.value.length === 0) {
      auditLogs.value = [...initialMockAuditLogs]
    }

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
    console.warn('Backend MOSTO no disponible, manteniendo datos locales:', err)
    if (auditLogs.value.length === 0) {
      auditLogs.value = [...initialMockAuditLogs]
    }
    calcularMetricasFallback()
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
      if (!item.detectedAt.includes('2026-11') && !item.detectedAt.includes('2026-10-31')) return false
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

  const nota = resolutionNoteInput.value.trim() || 'Acción correctiva aplicada en bodega. Parámetros estabilizados.'

  isResolving.value = true
  resolveError.value = null

  try {
    let updatedDto = null
    if (numericId && !isNaN(numericId)) {
      updatedDto = await alertService.resolver(numericId, {
        usuario_id: 1,
        nota_resolucion: nota
      })
    }

    // Actualizar estado del incidente localmente
    selectedIncident.value.status = 'resolved'
    selectedIncident.value.statusBackend = 'resuelta'
    selectedIncident.value.resolutionType = 'resolved'
    selectedIncident.value.resolutionLabel = 'Resuelta'
    selectedIncident.value.summaryResolution = nota
    selectedIncident.value.nota_resolucion = nota
    selectedIncident.value.resolvedBy = (updatedDto && updatedDto.operador_nombre) || 'Operador Enológico Principal'
    selectedIncident.value.role = 'Enólogo de Bodega'

    const now = new Date()
    selectedIncident.value.resolvedAt = formatDateTime(now)

    if (selectedIncident.value.detectedAtRaw) {
      const diffMin = Math.max(1, Math.round((now - new Date(selectedIncident.value.detectedAtRaw)) / 60000))
      selectedIncident.value.resolutionTimeMin = diffMin
    }

    if (!selectedIncident.value.timeline) {
      selectedIncident.value.timeline = []
    }
    selectedIncident.value.timeline.push({
      time: now.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
      author: selectedIncident.value.resolvedBy,
      text: `Incidencia resuelta: ${nota}`
    })

    // Sincronizar en la lista local auditLogs
    const targetIdx = auditLogs.value.findIndex(item => item.id === selectedIncident.value.id)
    if (targetIdx !== -1) {
      auditLogs.value[targetIdx] = { ...selectedIncident.value }
    }

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
    <header class="audit-header">
      <div>
        <div class="module-tag">Módulo 5 · Administración SaaS y Gestión de Empresa</div>
        <h1 class="view-title">Historial de Alertas y Auditoría</h1>
        <p class="view-subtitle">
          Archivo histórico consolidado de incidencias enológicas, cálculo oficial MTTR y trazabilidad de acciones correctivas de bodega.
        </p>
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
        <div class="kpi-number">{{ metricas.mttr_promedio_minutos }} <span class="kpi-unit">min</span></div>
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
                <span class="time-cell">{{ log.resolutionTimeMin ? log.resolutionTimeMin + ' min' : '-' }}</span>
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
              v-model="resolutionNoteInput"
              rows="3"
              class="resolve-textarea"
              placeholder="Describa la acción correctiva realizada (ej: purga de camisa de refrigeración, ajuste de consigna a 18°C, adición de nutrientes)..."
              :disabled="isResolving"
            ></textarea>
            <span v-if="resolveError" class="resolve-error-msg">{{ resolveError }}</span>
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
