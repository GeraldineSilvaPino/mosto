<script setup>
/**
 * 📋 06. [FRONT - VUE] Pantalla de Dispositivos IoT
 * Módulo 4: Hardware y Configuración Operativa
 *
 * Características implementadas:
 * 1. KPIs de estado de red IoT: Dispositivos Online, Offline, Batería Baja y Cubas Monitoreadas.
 * 2. Cuadrícula de tarjetas de hardware ESP32 con estado en vivo, nivel de señal (dBm), batería/alimentación y última transmisión.
 * 3. Identificación clara de sensores: DS18B20 (sonda de temperatura) y MPU-6050 (inclinómetro de densidad/Brix).
 * 4. Modal interactivo de emparejamiento para registrar y asignar nuevos dispositivos a cubas.
 * 5. Acciones simuladas sobre hardware: Ping de diagnóstico, reinicio remoto y desvinculación/reasignación de cuba.
 * 6. 100% Frontend autónomo con datos mock reactivos y validaciones.
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import {
  Cpu,
  Wifi,
  WifiOff,
  Battery,
  BatteryCharging,
  BatteryMedium,
  BatteryWarning,
  RadioTower,
  Thermometer,
  Compass,
  RefreshCw,
  Plus,
  Search,
  X,
  CheckCircle2,
  AlertTriangle,
  Cylinder,
  Clock,
  Zap,
  Sliders,
  Unlink,
  Link,
  RotateCcw,
  Check,
  Signal,
  SignalMedium,
  SignalLow,
  SignalZero,
  Activity,
  Layers,
  FlaskConical
} from 'lucide-vue-next'
import deviceService from '../services/deviceService.js'
import cubaService from '../services/cubaService.js'

// ==========================================
// DATASETS MOCK DE DISPOSITIVOS ESP32
// ==========================================
let nextDeviceId = 20

const devices = ref([
  {
    id: 1,
    code: 'ESP32-CB01-TEMP',
    name: 'Nodo Térmico Cuba 01',
    mac: '24:6F:28:B4:9C:12',
    model: 'ESP32-WROOM-32D',
    sensorType: 'DS18B20',
    sensorLabel: 'Sonda Térmica Estanco DS18B20',
    assignedCubaId: '01',
    assignedCubaName: 'Cuba 01 · Cabernet Sauvignon',
    status: 'online', // online | offline | maintenance
    statusLabel: 'En Línea',
    signalRssi: -58, // dBm
    signalQuality: 'excellent', // excellent | good | weak | none
    powerSource: 'mains', // mains (red eléctrica 220V) | battery
    batteryLevel: 100,
    firmware: 'v2.4.1-ota',
    lastTelemetry: 'Hace 8 seg',
    lastReadingValue: '24.6 °C',
    samplingInterval: '1 min',
    ipAddress: '192.168.10.41',
    notes: 'Sonda sumergida a 1.8m de profundidad en el centro del tanque.'
  },
  {
    id: 2,
    code: 'ESP32-CB01-TILT',
    name: 'Cápsula Flotante Cuba 01',
    mac: '3C:71:BF:12:44:88',
    model: 'ESP32-C3-Mini',
    sensorType: 'MPU-6050',
    sensorLabel: 'Inclinómetro Giroscopio MPU-6050',
    assignedCubaId: '01',
    assignedCubaName: 'Cuba 01 · Cabernet Sauvignon',
    status: 'online',
    statusLabel: 'En Línea',
    signalRssi: -66,
    signalQuality: 'good',
    powerSource: 'battery',
    batteryLevel: 82,
    firmware: 'v2.3.0',
    lastTelemetry: 'Hace 15 seg',
    lastReadingValue: '42.5° (13.2 °Bx)',
    samplingInterval: '2 min',
    ipAddress: '192.168.10.42',
    notes: 'Flotador hermético tipo hidrómetro con batería Li-Po de 2000mAh.'
  },
  {
    id: 3,
    code: 'ESP32-CB02-TEMP',
    name: 'Nodo Térmico Cuba 02',
    mac: '24:6F:28:C8:11:50',
    model: 'ESP32-WROOM-32D',
    sensorType: 'DS18B20',
    sensorLabel: 'Sonda Térmica Estanco DS18B20',
    assignedCubaId: '02',
    assignedCubaName: 'Cuba 02 · Carménère Reserva',
    status: 'online',
    statusLabel: 'En Línea',
    signalRssi: -62,
    signalQuality: 'good',
    powerSource: 'mains',
    batteryLevel: 100,
    firmware: 'v2.4.1-ota',
    lastTelemetry: 'Hace 5 seg',
    lastReadingValue: '17.5 °C',
    samplingInterval: '1 min',
    ipAddress: '192.168.10.43',
    notes: 'Disparó alerta por gradiente térmico negativo pronunciado.'
  },
  {
    id: 4,
    code: 'ESP32-CB02-TILT',
    name: 'Cápsula Flotante Cuba 02',
    mac: '3C:71:BF:88:20:94',
    model: 'ESP32-C3-Mini',
    sensorType: 'MPU-6050',
    sensorLabel: 'Inclinómetro Giroscopio MPU-6050',
    assignedCubaId: '02',
    assignedCubaName: 'Cuba 02 · Carménère Reserva',
    status: 'maintenance',
    statusLabel: 'En Mantención (Aislado)',
    signalRssi: -72,
    signalQuality: 'good',
    powerSource: 'battery',
    batteryLevel: 14, // Batería baja
    firmware: 'v2.3.0',
    lastTelemetry: 'Hace 18 min',
    lastReadingValue: '58.2° (18.4 °Bx)',
    samplingInterval: '5 min',
    ipAddress: '192.168.10.44',
    notes: 'Anulado temporalmente por enólogo para recarga de batería.'
  },
  {
    id: 5,
    code: 'ESP32-CB03-DUAL',
    name: 'Nodo Compacto Cuba 03',
    mac: '24:6F:28:FE:33:09',
    model: 'ESP32-S3-DevKit',
    sensorType: 'DUAL',
    sensorLabel: 'Combo Dual (DS18B20 + MPU-6050)',
    assignedCubaId: '03',
    assignedCubaName: 'Cuba 03 · Sauvignon Blanc',
    status: 'online',
    statusLabel: 'En Línea',
    signalRssi: -54,
    signalQuality: 'excellent',
    powerSource: 'mains',
    batteryLevel: 100,
    firmware: 'v2.5.0-beta',
    lastTelemetry: 'Hace 12 seg',
    lastReadingValue: '15.2 °C · 6.8 °Bx',
    samplingInterval: '1 min',
    ipAddress: '192.168.10.45',
    notes: 'Instalado en cuba de blanco con camisa de enfriamiento permanente.'
  },
  {
    id: 6,
    code: 'ESP32-CB04-TEMP',
    name: 'Nodo Térmico Cuba 04',
    mac: '24:6F:28:90:AA:BC',
    model: 'ESP32-WROOM-32D',
    sensorType: 'DS18B20',
    sensorLabel: 'Sonda Térmica Estanco DS18B20',
    assignedCubaId: '04',
    assignedCubaName: 'Cuba 04 · Syrah Gran Corte',
    status: 'offline',
    statusLabel: 'Desconectado',
    signalRssi: -90,
    signalQuality: 'none',
    powerSource: 'mains',
    batteryLevel: 0,
    firmware: 'v2.4.0',
    lastTelemetry: 'Hace 2 horas',
    lastReadingValue: '26.8 °C (Última)',
    samplingInterval: '1 min',
    ipAddress: '192.168.10.46',
    notes: 'Sin respuesta a solicitudes de ping. Verificar bornera de alimentación.'
  },
  {
    id: 7,
    code: 'ESP32-SPARE-01',
    name: 'Nodo Móvil de Repuesto',
    mac: '24:6F:28:11:44:00',
    model: 'ESP32-WROOM-32D',
    sensorType: 'DS18B20',
    sensorLabel: 'Sonda Térmica Estanco DS18B20',
    assignedCubaId: null,
    assignedCubaName: 'Sin Asignar (Bodega de Repuestos)',
    status: 'online',
    statusLabel: 'En Reserva',
    signalRssi: -60,
    signalQuality: 'good',
    powerSource: 'battery',
    batteryLevel: 95,
    firmware: 'v2.4.1-ota',
    lastTelemetry: 'Hace 1 min',
    lastReadingValue: '20.1 °C (Ambiente)',
    samplingInterval: '5 min',
    ipAddress: '192.168.10.99',
    notes: 'Dispositivo configurado listo para reemplazo rápido en caso de avería.'
  }
])

// ==========================================
// CUBAS DISPONIBLES PARA EMPAREJAR (REACTIVO)
// ==========================================
const availableCubas = ref([
  { id: '1', code: 'CB-01', name: 'Cuba 01 · Cabernet Sauvignon' },
  { id: '2', code: 'CB-02', name: 'Cuba 02 · Carménère Reserva' },
  { id: '3', code: 'CB-03', name: 'Cuba 03 · Sauvignon Blanc' },
  { id: '4', code: 'CB-04', name: 'Cuba 04 · Syrah Gran Corte' },
  { id: '5', code: 'CB-05', name: 'Cuba 05 · Chardonnay' },
  { id: '6', code: 'CB-06', name: 'Cuba 06 · Malbec' }
])

// ==========================================
// FILTROS Y ESTADO REACTIVO
// ==========================================
const searchQuery = ref('')
const filterStatus = ref('all') // all | online | offline | maintenance
const filterSensor = ref('all') // all | DS18B20 | MPU-6050 | PH-4502C | DUAL
const filterCuba = ref('all')

const toastMessage = ref('')
const isScanning = ref(false)
const isLoading = ref(false)
const errorMessage = ref(null)

// Modal de Emparejamiento
const isPairModalOpen = ref(false)
const newDevice = ref({
  code: '',
  name: '',
  mac: '',
  model: 'ESP32-WROOM-32D',
  sensorType: 'DS18B20',
  cubaId: '1',
  powerSource: 'mains',
  samplingInterval: '1 min',
  notes: ''
})

// Modal de Diagnóstico / Ping
const pingResult = ref(null)
const isPinging = ref(false)

// ==========================================
// KPIS COMPUTADOS (ESTADO EN VIVO)
// ==========================================
const totalOnline = computed(() => {
  return devices.value.filter(d => d.status === 'online').length
})

const totalOffline = computed(() => {
  return devices.value.filter(d => d.status === 'offline').length
})

const totalLowBattery = computed(() => {
  return devices.value.filter(d => d.batteryLevel !== null && d.batteryLevel !== undefined && d.batteryLevel < 20).length
})

const totalMonitoredCubas = computed(() => {
  const set = new Set()
  devices.value.forEach(d => {
    if (d.assignedCubaId && d.status === 'online') {
      set.add(String(d.assignedCubaId))
    }
  })
  return set.size
})

// Lista filtrada reactiva
const filteredDevices = computed(() => {
  return devices.value.filter(d => {
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      const matchText =
        (d.code && d.code.toLowerCase().includes(q)) ||
        (d.name && d.name.toLowerCase().includes(q)) ||
        (d.mac && d.mac.toLowerCase().includes(q)) ||
        (d.assignedCubaName && d.assignedCubaName.toLowerCase().includes(q)) ||
        (d.sensorType && d.sensorType.toLowerCase().includes(q)) ||
        (d.ipAddress && d.ipAddress.includes(q))
      if (!matchText) return false
    }

    if (filterStatus.value !== 'all' && d.status !== filterStatus.value) {
      return false
    }

    if (filterSensor.value !== 'all' && d.sensorType !== filterSensor.value) {
      return false
    }

    if (filterCuba.value !== 'all') {
      if (filterCuba.value === 'none' && d.assignedCubaId !== null) return false
      if (filterCuba.value !== 'none' && String(d.assignedCubaId) !== String(filterCuba.value)) return false
    }

    return true
  })
})

// ==========================================
// CONEXIÓN AL BACKEND & POLLING
// ==========================================
function mapBackendDevice(d) {
  const ipAddress = d.ipAddress || (d.id ? `192.168.10.${40 + (d.id % 50)}` : '192.168.10.x')

  let lastReadingValue = d.lastReadingValue
  if (!lastReadingValue) {
    if (d.sensorType === 'DS18B20') {
      lastReadingValue = d.status === 'online' ? '21.5 °C' : 'Último dato'
    } else if (d.sensorType === 'MPU-6050') {
      lastReadingValue = d.status === 'online' ? '42.0° (13.5 °Bx)' : 'Último dato'
    } else if (d.sensorType === 'PH-4502C') {
      lastReadingValue = d.status === 'online' ? '3.42 pH' : 'Último dato'
    } else {
      lastReadingValue = d.status === 'online' ? 'Telemetría activa' : 'Sin señal'
    }
  }

  const samplingInterval = d.samplingInterval || (d.powerSource === 'battery' ? '2 min' : '1 min')
  const notes = d.notes || (d.assignedCubaName
    ? `Asignado operativamente a ${d.assignedCubaName}. Sincronizado con broker IoT.`
    : 'Dispositivo disponible en inventario técnico.')

  return {
    ...d,
    assignedCubaId: d.assignedCubaId !== null && d.assignedCubaId !== undefined ? String(d.assignedCubaId) : null,
    assignedCubaName: d.assignedCubaName || (d.assignedCubaCode ? `Cuba ${d.assignedCubaCode}` : 'Sin Asignar (Reserva)'),
    lastReadingValue,
    samplingInterval,
    ipAddress,
    notes
  }
}

async function loadDevices(isManual = false) {
  if (isManual) isLoading.value = true
  errorMessage.value = null
  try {
    const data = await deviceService.listarDispositivos()
    if (Array.isArray(data) && data.length > 0) {
      devices.value = data.map(mapBackendDevice)
    }

    try {
      const cubasData = await cubaService.listarCubas()
      if (Array.isArray(cubasData) && cubasData.length > 0) {
        availableCubas.value = cubasData.map(c => ({
          id: String(c.id),
          code: c.codigo_cuba || `CB-${String(c.id).padStart(2, '0')}`,
          name: c.nombre || `Cuba ${c.codigo_cuba || c.id}`
        }))
      }
    } catch {
      // Ignorar fallo de cubas silenciosamente
    }
  } catch (err) {
    console.error('Error al conectar con GET /api/dispositivos:', err)
    errorMessage.value = err.message || 'Error de conexión con el Device Hub'
  } finally {
    if (isManual) isLoading.value = false
  }
}

let pollInterval = null

onMounted(() => {
  loadDevices(true)
  // Refresco cada 15 segundos para reflejar dispositivos que se desconectan o reconectan
  pollInterval = setInterval(() => {
    if (!isPairModalOpen.value && !isAssignModalOpen.value && !isUnlinkModalOpen.value && !isScanning.value) {
      loadDevices(false)
    }
  }, 15000)
})

onBeforeUnmount(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
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

async function triggerScan() {
  isScanning.value = true
  try {
    await loadDevices(true)
    showToast(`Escaneo completado: ${devices.value.length} dispositivos IoT sincronizados con el servidor.`)
  } catch {
    showToast('Aviso: Escaneo completado con datos locales.')
  } finally {
    isScanning.value = false
  }
}

// Abrir modal de emparejar
function openPairModal() {
  // Generar código y MAC aleatoria realista
  const randomHex = () => Math.floor(Math.random() * 256).toString(16).padStart(2, '0').toUpperCase()
  const randNum = Math.floor(Math.random() * 90) + 10

  newDevice.value = {
    code: `ESP32-CB0${randNum}-TEMP`,
    name: `Nodo Térmico Nuevo #${randNum}`,
    mac: `24:6F:28:${randomHex()}:${randomHex()}:${randomHex()}`,
    model: 'ESP32-WROOM-32D',
    sensorType: 'DS18B20',
    cubaId: '1',
    powerSource: 'mains',
    samplingInterval: '1 min',
    notes: 'Emparejado mediante asistente web de bodega.'
  }
  isPairModalOpen.value = true
}

function closePairModal() {
  isPairModalOpen.value = false
}

// Guardar nuevo dispositivo con persistencia en Supabase PostgreSQL
async function handleSaveNewDevice() {
  if (!newDevice.value.code || !newDevice.value.mac) return

  try {
    const created = await deviceService.registrarDispositivo({
      code: newDevice.value.code.toUpperCase(),
      name: newDevice.value.name,
      mac: newDevice.value.mac.toUpperCase(),
      model: newDevice.value.model,
      sensorType: newDevice.value.sensorType,
      cubaId: newDevice.value.cubaId,
      powerSource: newDevice.value.powerSource,
      samplingInterval: newDevice.value.samplingInterval,
      notes: newDevice.value.notes
    })

    const mapped = mapBackendDevice(created)
    devices.value.unshift(mapped)
    isPairModalOpen.value = false
    showToast(`¡Dispositivo ${mapped.code || newDevice.value.code} registrado y persistido en la base de datos!`)
  } catch (err) {
    alert(err.message || 'Error al registrar el dispositivo en el servidor.')
  }
}

// Simular Ping a dispositivo
function handlePing(device) {
  isPinging.value = true
  pingResult.value = { deviceId: device.id, status: 'loading' }

  setTimeout(() => {
    isPinging.value = false
    if (device.status === 'offline') {
      pingResult.value = {
        deviceId: device.id,
        status: 'error',
        msg: `Fallo de ping a ${device.ipAddress} (${device.code}): Tiempo de espera agotado (Timeout 2000ms).`
      }
      showToast(`Error: ${device.code} no respondió al ping ICMP.`)
    } else {
      const ms = Math.floor(Math.random() * 25) + 18
      pingResult.value = {
        deviceId: device.id,
        status: 'success',
        msg: `Ping exitoso a ${device.ipAddress} (${device.code}): Tiempo de respuesta ${ms} ms · Paquetes 4/4 (0% pérdida).`
      }
      showToast(`Ping OK: ${device.code} respondió en ${ms} ms.`)
    }

    setTimeout(() => {
      pingResult.value = null
    }, 5000)
  }, 700)
}

// Simular Reinicio de dispositivo
function handleRestart(device) {
  showToast(`Enviando señal de reinicio (Soft Reset) a ${device.code}...`)
  device.status = 'maintenance'
  device.statusLabel = 'Reiniciando...'

  setTimeout(() => {
    device.status = 'online'
    device.statusLabel = 'En Línea'
    device.lastTelemetry = 'Ahora mismo'
    showToast(`Dispositivo ${device.code} reiniciado y reconectado al broker MQTT.`)
  }, 1800)
}

// ==========================================
// MODAL DE ASIGNACIÓN / VINCULACIÓN A CUBA
// ==========================================
const isAssignModalOpen = ref(false)
const selectedDeviceToAssign = ref(null)
const selectedCubaId = ref('')
const isAssigning = ref(false)
const assignError = ref(null)

function openAssignModal(device) {
  selectedDeviceToAssign.value = device
  assignError.value = null
  if (device.assignedCubaId) {
    selectedCubaId.value = String(device.assignedCubaId)
  } else if (availableCubas.value.length > 0) {
    selectedCubaId.value = String(availableCubas.value[0].id)
  } else {
    selectedCubaId.value = ''
  }
  isAssignModalOpen.value = true
}

function closeAssignModal() {
  if (isAssigning.value) return
  isAssignModalOpen.value = false
  selectedDeviceToAssign.value = null
  assignError.value = null
}

async function handleAssignCuba() {
  if (!selectedDeviceToAssign.value || !selectedCubaId.value) return
  isAssigning.value = true
  assignError.value = null

  try {
    const updatedDevice = await deviceService.vincular({
      dispositivo_id: selectedDeviceToAssign.value.id,
      cuba_id: Number(selectedCubaId.value)
    })

    const idx = devices.value.findIndex(d => d.id === selectedDeviceToAssign.value.id)
    if (idx !== -1) {
      const mapped = mapBackendDevice(updatedDevice)
      devices.value[idx] = { ...devices.value[idx], ...mapped }
    }

    const assignedCuba = availableCubas.value.find(c => String(c.id) === String(selectedCubaId.value))
    const cubaLabel = assignedCuba ? `${assignedCuba.code} (${assignedCuba.name})` : `Cuba ID ${selectedCubaId.value}`
    showToast(`Sensor ${selectedDeviceToAssign.value.code} vinculado exitosamente a ${cubaLabel}.`)
    closeAssignModal()
  } catch (err) {
    console.error('Error al vincular dispositivo:', err)
    // Manejo de errores de negocio devueltos por el backend (ej: inconsistencia de bodega/empresa)
    assignError.value = err.message || 'Error de negocio al vincular el sensor a la cuba seleccionada.'
  } finally {
    isAssigning.value = false
  }
}

// ==========================================
// MODAL DE CONFIRMACIÓN DE DESVINCULACIÓN
// ==========================================
const isUnlinkModalOpen = ref(false)
const deviceToUnlink = ref(null)
const isUnlinking = ref(false)
const unlinkError = ref(null)

function openUnlinkModal(device) {
  if (!device.assignedCubaId) return
  deviceToUnlink.value = device
  unlinkError.value = null
  isUnlinkModalOpen.value = true
}

function closeUnlinkModal() {
  if (isUnlinking.value) return
  isUnlinkModalOpen.value = false
  deviceToUnlink.value = null
  unlinkError.value = null
}

async function handleConfirmUnlink() {
  if (!deviceToUnlink.value) return
  isUnlinking.value = true
  unlinkError.value = null

  try {
    const updatedDevice = await deviceService.desvincular({
      dispositivo_id: deviceToUnlink.value.id
    })

    const idx = devices.value.findIndex(d => d.id === deviceToUnlink.value.id)
    if (idx !== -1) {
      const mapped = mapBackendDevice(updatedDevice)
      devices.value[idx] = { ...devices.value[idx], ...mapped }
    }

    const devCode = deviceToUnlink.value.code
    showToast(`Sensor ${devCode} desvinculado exitosamente. Ahora figura como "Sin Asignar".`)
    closeUnlinkModal()
  } catch (err) {
    console.error('Error al desvincular dispositivo:', err)
    unlinkError.value = err.message || 'Error de negocio al desvincular el dispositivo.'
  } finally {
    isUnlinking.value = false
  }
}
</script>

<template>
  <div class="view-container devices-view">
    <!-- Toast Flotante -->
    <transition name="toast-fade">
      <div v-if="toastMessage" class="toast-popup">
        <CheckCircle2 :size="16" />
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

    <!-- Header Principal -->
    <header class="devices-header">
      <div>
        <div class="module-tag">Módulo 4 · Hardware y Configuración Operativa</div>
        <h1 class="view-title">Dispositivos IoT y Sensores de Bodega</h1>
        <p class="view-subtitle">
          Administración de microcontroladores ESP32, estado de telemetría de sondas DS18B20 e inclinómetros MPU-6050 y emparejamiento con cubas.
        </p>
      </div>

      <div class="header-actions">
        <button
          class="btn-scan"
          :class="{ 'btn-scan--loading': isScanning || isLoading }"
          :disabled="isScanning || isLoading"
          @click="triggerScan"
        >
          <RefreshCw :size="15" :class="{ 'spin-icon': isScanning || isLoading }" />
          <span>{{ isScanning || isLoading ? 'Sincronizando...' : 'Escanear Red' }}</span>
        </button>

        <button class="btn-primary" @click="openPairModal">
          <Plus :size="16" />
          <span>Emparejar Dispositivo</span>
        </button>
      </div>
    </header>

    <!-- Banner de Diagnóstico / Ping Activo -->
    <transition name="toast-fade">
      <div
        v-if="pingResult"
        class="ping-banner"
        :class="pingResult.status === 'success' ? 'ping-banner--success' : 'ping-banner--error'"
      >
        <component :is="pingResult.status === 'success' ? CheckCircle2 : AlertTriangle" :size="18" />
        <span>{{ pingResult.msg }}</span>
      </div>
    </transition>

    <!-- Tarjetas KPIs de Hardware -->
    <section class="kpi-grid">
      <!-- 1. En Línea -->
      <div
        class="kpi-card kpi-card--online"
        :class="{ active: filterStatus === 'online' }"
        @click="filterStatus = filterStatus === 'online' ? 'all' : 'online'"
      >
        <div class="kpi-top">
          <span class="kpi-label">Dispositivos en Línea</span>
          <div class="kpi-icon-box kpi-icon--online">
            <RadioTower :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalOnline }}</div>
        <div class="kpi-sub">
          <span>Transmitiendo telemetría en tiempo real</span>
        </div>
      </div>

      <!-- 2. Desconectados -->
      <div
        class="kpi-card kpi-card--offline"
        :class="{ active: filterStatus === 'offline' }"
        @click="filterStatus = filterStatus === 'offline' ? 'all' : 'offline'"
      >
        <div class="kpi-top">
          <span class="kpi-label">Desconectados</span>
          <div class="kpi-icon-box kpi-icon--offline">
            <WifiOff :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalOffline }}</div>
        <div class="kpi-sub">
          <span>Sin señal o corte de suministro</span>
        </div>
      </div>

      <!-- 3. Batería Baja -->
      <div class="kpi-card kpi-card--battery">
        <div class="kpi-top">
          <span class="kpi-label">Batería Crítica (&lt; 20%)</span>
          <div class="kpi-icon-box kpi-icon--battery">
            <BatteryWarning :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalLowBattery }}</div>
        <div class="kpi-sub">
          <span>Cápsulas flotantes que requieren recarga</span>
        </div>
      </div>

      <!-- 4. Cubas Monitoreadas -->
      <div class="kpi-card kpi-card--cubas">
        <div class="kpi-top">
          <span class="kpi-label">Cubas con Cobertura</span>
          <div class="kpi-icon-box kpi-icon--cubas">
            <Cylinder :size="18" />
          </div>
        </div>
        <div class="kpi-number">{{ totalMonitoredCubas }} / {{ availableCubas.length || 6 }}</div>
        <div class="kpi-sub">
          <span>Tanques con sensores activos</span>
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
          placeholder="Buscar por código (ESP32), dirección MAC, cuba o IP..."
          class="search-input"
        />
        <button v-if="searchQuery" @click="searchQuery = ''" class="clear-search-btn">
          <X :size="14" />
        </button>
      </div>

      <!-- Desplegables -->
      <div class="filter-controls">
        <!-- Tipo de Sensor -->
        <select v-model="filterSensor" class="select-filter">
          <option value="all">Tipo de Sensor: Todos</option>
          <option value="DS18B20">Solo Sonda Térmica (DS18B20)</option>
          <option value="MPU-6050">Solo Hidrómetro Flotante (MPU-6050)</option>
          <option value="PH-4502C">Solo Sonda de pH (PH-4502C)</option>
          <option value="DUAL">Nodos Duales (Ambos)</option>
        </select>

        <!-- Estado de Conexión -->
        <select v-model="filterStatus" class="select-filter">
          <option value="all">Estado: Todos</option>
          <option value="online">Solo En Línea</option>
          <option value="offline">Solo Desconectados</option>
          <option value="maintenance">En Mantención / Reserva</option>
        </select>

        <!-- Cuba Asignada -->
        <select v-model="filterCuba" class="select-filter">
          <option value="all">Asignación: Todas</option>
          <option v-for="cuba in availableCubas" :key="cuba.id" :value="cuba.id">
            {{ cuba.code }} ({{ cuba.name.split('·')[1]?.trim() || cuba.name }})
          </option>
          <option value="none">Sin Cuba (En Reserva)</option>
        </select>

        <!-- Reset -->
        <button
          v-if="searchQuery || filterSensor !== 'all' || filterStatus !== 'all' || filterCuba !== 'all'"
          class="btn-reset-filters"
          @click="searchQuery = ''; filterSensor = 'all'; filterStatus = 'all'; filterCuba = 'all'"
        >
          Limpiar filtros
        </button>
      </div>
    </section>

    <!-- Cuadrícula de Tarjetas de Dispositivos -->
    <section class="devices-grid">
      <div v-if="filteredDevices.length === 0" class="empty-state">
        <Cpu :size="40" class="empty-icon" />
        <h3>No se encontraron dispositivos IoT con los filtros aplicados</h3>
        <p>Prueba limpiando los filtros o empareja un nuevo microcontrolador ESP32.</p>
      </div>

      <div
        v-for="device in filteredDevices"
        :key="device.id"
        class="device-card"
        :class="[
          'device-card--' + device.status,
          { 'device-card--low-battery': device.powerSource === 'battery' && device.batteryLevel < 20 }
        ]"
      >
        <!-- Top de la Tarjeta -->
        <div class="device-card-header">
          <div class="device-identity">
            <div
              class="device-icon-box"
              :class="'device-icon--' + (device.sensorType ? device.sensorType.toLowerCase() : 'ds18b20')"
            >
              <Thermometer v-if="device.sensorType === 'DS18B20'" :size="20" />
              <Compass v-else-if="device.sensorType === 'MPU-6050'" :size="20" />
              <FlaskConical v-else-if="device.sensorType === 'PH-4502C'" :size="20" />
              <Layers v-else :size="20" />
            </div>

            <div>
              <div class="device-code-row">
                <h3 class="device-code">{{ device.code }}</h3>
                <span class="device-model-tag">{{ device.model }}</span>
              </div>
              <p class="device-mac">{{ device.mac }} · IP: {{ device.ipAddress }}</p>
            </div>
          </div>

          <!-- Badge de Estado -->
          <div class="device-status-pill" :class="'status-pill--' + device.status">
            <span v-if="device.status === 'online'" class="pulse-dot"></span>
            <span>{{ device.statusLabel }}</span>
          </div>
        </div>

        <!-- Cuba Vinculada -->
        <div class="device-cuba-banner" :class="{ 'device-cuba-banner--unassigned': !device.assignedCubaId }">
          <div class="cuba-info">
            <Cylinder :size="15" class="cuba-icon" />
            <span class="cuba-name">{{ device.assignedCubaName }}</span>
          </div>
          <div class="cuba-banner-actions">
            <router-link
              v-if="device.assignedCubaId"
              :to="'/cubas/' + device.assignedCubaId"
              class="cuba-link-btn"
              title="Ir al detalle de la cuba"
            >
              Ver Telemetría
            </router-link>
            <button
              v-else
              class="cuba-link-btn cuba-link-btn--assign"
              @click="openAssignModal(device)"
              title="Asignar sensor a una cuba física"
            >
              <Link :size="12" />
              <span>Vincular Cuba</span>
            </button>
          </div>
        </div>

        <!-- Métricas de Hardware: Señal, Energía y Lectura -->
        <div class="device-metrics-row">
          <!-- Calidad de Señal Wi-Fi -->
          <div class="metric-item">
            <span class="metric-item-label">Señal Wi-Fi</span>
            <div class="signal-indicator">
              <Signal v-if="device.signalQuality === 'excellent'" :size="16" class="signal-icon signal-excellent" />
              <SignalMedium v-else-if="device.signalQuality === 'good'" :size="16" class="signal-icon signal-good" />
              <SignalLow v-else-if="device.signalQuality === 'weak'" :size="16" class="signal-icon signal-weak" />
              <SignalZero v-else :size="16" class="signal-icon signal-none" />
              <span class="signal-rssi">{{ device.signalRssi }} dBm</span>
            </div>
          </div>

          <!-- Batería / Alimentación -->
          <div class="metric-item">
            <span class="metric-item-label">Alimentación</span>
            <div class="power-indicator">
              <Zap v-if="device.powerSource === 'mains'" :size="15" class="power-icon mains-icon" />
              <component
                v-else
                :is="device.batteryLevel < 20 ? BatteryWarning : BatteryMedium"
                :size="16"
                class="power-icon"
                :class="device.batteryLevel < 20 ? 'battery-low' : 'battery-normal'"
              />
              <span class="power-text">
                {{ device.powerSource === 'mains' ? 'Red 220V' : `${device.batteryLevel}%` }}
              </span>
            </div>
          </div>

          <!-- Última Lectura -->
          <div class="metric-item">
            <span class="metric-item-label">Último Dato</span>
            <div class="reading-indicator">
              <span class="reading-val">{{ device.lastReadingValue }}</span>
            </div>
          </div>
        </div>

        <!-- Notas técnicas y tiempo -->
        <div class="device-notes-box">
          <p class="notes-text">{{ device.notes }}</p>
          <div class="telemetry-time">
            <Clock :size="12" />
            <span>Última trama: {{ device.lastTelemetry }} · Frecuencia: {{ device.samplingInterval }}</span>
          </div>
        </div>

        <!-- Botones de Acción sobre el Dispositivo -->
        <div class="device-actions-footer">
          <button
            class="btn-device-action"
            :disabled="isPinging"
            @click="handlePing(device)"
            title="Envía un paquete ICMP de prueba para medir latencia"
          >
            <Activity :size="13" />
            <span>Ping</span>
          </button>

          <button
            class="btn-device-action"
            @click="handleRestart(device)"
            title="Envía comando de reinicio remoto al microcontrolador"
          >
            <RotateCcw :size="13" />
            <span>Reiniciar</span>
          </button>

          <!-- Acción Asignar o Reasignar a Cuba -->
          <button
            v-if="!device.assignedCubaId"
            class="btn-device-action btn-device-action--primary"
            @click="openAssignModal(device)"
            title="Asignar este sensor a una cuba de fermentación"
          >
            <Link :size="13" />
            <span>Asignar</span>
          </button>

          <button
            v-else
            class="btn-device-action"
            @click="openAssignModal(device)"
            title="Cambiar o reasignar cuba"
          >
            <Link :size="13" />
            <span>Reasignar</span>
          </button>

          <!-- Acción Desvincular con confirmación previa -->
          <button
            v-if="device.assignedCubaId"
            class="btn-device-action btn-device-action--danger"
            @click="openUnlinkModal(device)"
            title="Desvincula el sensor de esta cuba previa confirmación"
          >
            <Unlink :size="13" />
            <span>Desvincular</span>
          </button>
        </div>
      </div>
    </section>

    <!-- MODAL: EMPAREJAR NUEVO DISPOSITIVO IOT -->
    <div v-if="isPairModalOpen" class="modal-backdrop" @click.self="closePairModal">
      <div class="pair-modal">
        <!-- Header Modal -->
        <div class="modal-header">
          <div class="modal-title-group">
            <div class="modal-icon-badge">
              <RadioTower :size="20" />
            </div>
            <div>
              <h2 class="modal-title">Emparejar Nuevo Dispositivo IoT</h2>
              <p class="modal-sub">
                Registra un microcontrolador ESP32 y asígnalo a una cuba de fermentación.
              </p>
            </div>
          </div>

          <button class="modal-close-btn" @click="closePairModal">
            <X :size="18" />
          </button>
        </div>

        <!-- Cuerpo Modal -->
        <form @submit.prevent="handleSaveNewDevice" class="modal-form">
          <div class="form-grid">
            <!-- Código Identificador -->
            <div class="form-group">
              <label class="form-label">Código del Dispositivo *</label>
              <input
                v-model="newDevice.code"
                type="text"
                required
                placeholder="Ej: ESP32-CB05-TEMP"
                class="form-input"
              />
              <span class="form-hint">Etiqueta impresa en la carcasa estanca.</span>
            </div>

            <!-- Dirección MAC -->
            <div class="form-group">
              <label class="form-label">Dirección MAC (Hardware) *</label>
              <input
                v-model="newDevice.mac"
                type="text"
                required
                placeholder="Ej: 24:6F:28:XX:YY:ZZ"
                class="form-input form-input--mono"
              />
              <span class="form-hint">Identificador físico del chip Wi-Fi/BLE.</span>
            </div>

            <!-- Modelo del Chip -->
            <div class="form-group">
              <label class="form-label">Modelo del Microcontrolador</label>
              <select v-model="newDevice.model" class="form-select">
                <option value="ESP32-WROOM-32D">ESP32-WROOM-32D (Nodo fijo de pared)</option>
                <option value="ESP32-C3-Mini">ESP32-C3-Mini (Cápsula flotante RISC-V)</option>
                <option value="ESP32-S3-DevKit">ESP32-S3-DevKit (Nodo avanzado)</option>
              </select>
            </div>

            <!-- Tipo de Sensor -->
            <div class="form-group">
              <label class="form-label">Sensor Físico Conectado *</label>
              <select v-model="newDevice.sensorType" class="form-select">
                <option value="DS18B20">Sonda Térmica Estanco (Sensor DS18B20)</option>
                <option value="MPU-6050">Hidrómetro Flotante Inclinómetro (Sensor MPU-6050)</option>
                <option value="PH-4502C">Sonda de pH Analógica (Sensor PH-4502C)</option>
                <option value="DUAL">Nodo Dual Combinado (DS18B20 + MPU-6050)</option>
              </select>
            </div>

            <!-- Cuba a Vincular -->
            <div class="form-group">
              <label class="form-label">Cuba Asignada *</label>
              <select v-model="newDevice.cubaId" class="form-select">
                <option v-for="cuba in availableCubas" :key="cuba.id" :value="cuba.id">
                  {{ cuba.code }} — {{ cuba.name }}
                </option>
                <option :value="null">Dejar sin asignar (Reserva de Bodega)</option>
              </select>
              <span class="form-hint">Cuba donde se sumergirá o fijará el sensor.</span>
            </div>

            <!-- Fuente de Energía -->
            <div class="form-group">
              <label class="form-label">Alimentación Eléctrica</label>
              <select v-model="newDevice.powerSource" class="form-select">
                <option value="mains">Red Eléctrica 220V / Fuente DC (Nodo Fijo)</option>
                <option value="battery">Batería Li-Po Recargable (Cápsula Flotante)</option>
              </select>
            </div>

            <!-- Frecuencia de Muestreo -->
            <div class="form-group">
              <label class="form-label">Intervalo de Transmisión de Telemetría</label>
              <select v-model="newDevice.samplingInterval" class="form-select">
                <option value="30 seg">Cada 30 segundos (Pico de fermentación)</option>
                <option value="1 min">Cada 1 minuto (Recomendado estándar)</option>
                <option value="5 min">Cada 5 minutos (Ahorro de batería)</option>
                <option value="15 min">Cada 15 minutos (Guarda / Post-fermentación)</option>
              </select>
            </div>

            <!-- Nombre Descriptivo -->
            <div class="form-group">
              <label class="form-label">Nombre o Alias del Dispositivo</label>
              <input
                v-model="newDevice.name"
                type="text"
                placeholder="Ej: Sonda Central Cuba 05"
                class="form-input"
              />
            </div>
          </div>

          <!-- Observaciones -->
          <div class="form-group form-group--full">
            <label class="form-label">Notas Técnicas de Instalación</label>
            <textarea
              v-model="newDevice.notes"
              rows="2"
              placeholder="Ej: Longitud del cable 2.5m, instalada en brida superior de la cuba..."
              class="form-textarea"
            ></textarea>
          </div>

          <!-- Footer Modal -->
          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="closePairModal">
              Cancelar
            </button>
            <button type="submit" class="btn-primary">
              <Check :size="16" />
              <span>Vincular y Guardar Dispositivo</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- MODAL: ASIGNAR SENSOR A CUBA -->
    <div v-if="isAssignModalOpen && selectedDeviceToAssign" class="modal-backdrop" @click.self="closeAssignModal">
      <div class="assign-modal">
        <!-- Header Modal -->
        <div class="modal-header">
          <div class="modal-title-group">
            <div class="modal-icon-badge">
              <Link :size="20" />
            </div>
            <div>
              <h2 class="modal-title">Asignar Sensor a Cuba Física</h2>
              <p class="modal-sub">
                Asocia el nodo {{ selectedDeviceToAssign.code }} a una cuba para registrar su telemetría.
              </p>
            </div>
          </div>

          <button class="modal-close-btn" :disabled="isAssigning" @click="closeAssignModal">
            <X :size="18" />
          </button>
        </div>

        <!-- Formulario de Asignación -->
        <form @submit.prevent="handleAssignCuba" class="modal-form">
          <!-- Banner de Error de Negocio -->
          <div v-if="assignError" class="modal-error-banner">
            <AlertTriangle :size="16" class="error-banner-icon" />
            <div class="error-banner-content">
              <strong>Error en la asignación:</strong>
              <p>{{ assignError }}</p>
            </div>
          </div>

          <!-- Ficha Resumen del Dispositivo -->
          <div class="device-summary-card">
            <div class="summary-top">
              <span class="summary-code">{{ selectedDeviceToAssign.code }}</span>
              <span class="summary-model">{{ selectedDeviceToAssign.model }}</span>
              <span class="summary-status" :class="'status--' + selectedDeviceToAssign.status">
                {{ selectedDeviceToAssign.statusLabel }}
              </span>
            </div>
            <div class="summary-grid">
              <div class="summary-field">
                <span class="field-label">Sensor:</span>
                <span class="field-value">{{ selectedDeviceToAssign.sensorLabel }}</span>
              </div>
              <div class="summary-field">
                <span class="field-label">Dirección MAC:</span>
                <span class="field-value font-mono">{{ selectedDeviceToAssign.mac }}</span>
              </div>
              <div class="summary-field">
                <span class="field-label">Asignación Actual:</span>
                <span class="field-value">{{ selectedDeviceToAssign.assignedCubaName || 'Sin Asignar (Reserva)' }}</span>
              </div>
              <div class="summary-field">
                <span class="field-label">Fuente de Energía:</span>
                <span class="field-value">{{ selectedDeviceToAssign.powerSource === 'mains' ? 'Red Eléctrica (220V)' : 'Batería (' + selectedDeviceToAssign.batteryLevel + '%)' }}</span>
              </div>
            </div>
          </div>

          <!-- Selección de Cuba -->
          <div class="form-group">
            <label class="form-label">Seleccionar Cuba de Fermentación *</label>
            <select v-model="selectedCubaId" class="form-select" required :disabled="isAssigning">
              <option value="" disabled>Seleccione una cuba de la lista...</option>
              <option v-for="cuba in availableCubas" :key="cuba.id" :value="cuba.id">
                {{ cuba.code }} — {{ cuba.name }}
              </option>
            </select>
            <span class="form-hint">
              Solo se listan cubas registradas en la bodega autorizada para este sensor.
            </span>
          </div>

          <!-- Footer Modal -->
          <div class="modal-footer">
            <button type="button" class="btn-secondary" :disabled="isAssigning" @click="closeAssignModal">
              Cancelar
            </button>
            <button type="submit" class="btn-primary" :disabled="isAssigning || !selectedCubaId">
              <RefreshCw v-if="isAssigning" :size="16" class="spin-icon" />
              <Check v-else :size="16" />
              <span>{{ isAssigning ? 'Vinculando en Servidor...' : 'Confirmar Asignación' }}</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- MODAL: CONFIRMAR DESVINCULACIÓN DE SENSOR -->
    <div v-if="isUnlinkModalOpen && deviceToUnlink" class="modal-backdrop" @click.self="closeUnlinkModal">
      <div class="confirm-modal">
        <!-- Header Modal -->
        <div class="modal-header">
          <div class="modal-title-group">
            <div class="modal-icon-badge modal-icon-badge--danger">
              <Unlink :size="20" />
            </div>
            <div>
              <h2 class="modal-title">Confirmar Desvinculación</h2>
              <p class="modal-sub">Liberar sensor IoT al stock de reserva</p>
            </div>
          </div>

          <button class="modal-close-btn" :disabled="isUnlinking" @click="closeUnlinkModal">
            <X :size="18" />
          </button>
        </div>

        <div class="modal-body-confirm">
          <!-- Banner de Error de Negocio -->
          <div v-if="unlinkError" class="modal-error-banner">
            <AlertTriangle :size="16" class="error-banner-icon" />
            <div class="error-banner-content">
              <strong>Error en la desvinculación:</strong>
              <p>{{ unlinkError }}</p>
            </div>
          </div>

          <div class="confirm-warning-box">
            <AlertTriangle :size="20" class="warning-icon" />
            <div class="warning-text">
              <p>
                ¿Estás seguro de que deseas desvincular el sensor <strong>{{ deviceToUnlink.code }}</strong> de la <strong>{{ deviceToUnlink.assignedCubaName }}</strong>?
              </p>
            </div>
          </div>

          <div class="unlink-details">
            <div class="unlink-detail-row">
              <span class="detail-label">Dispositivo:</span>
              <span class="detail-val font-mono">{{ deviceToUnlink.code }} ({{ deviceToUnlink.mac }})</span>
            </div>
            <div class="unlink-detail-row">
              <span class="detail-label">Tipo Sensor:</span>
              <span class="detail-val">{{ deviceToUnlink.sensorLabel }}</span>
            </div>
            <div class="unlink-detail-row">
              <span class="detail-label">Destino:</span>
              <span class="detail-val highlight-val">Stock de Reserva (Sin Asignar)</span>
            </div>
          </div>

          <p class="confirm-footnote">
            Al confirmar, el sensor dejará de reportar variables fisicoquímicas para esta cuba y pasará al estado disponible para nuevas asignaciones.
          </p>

          <!-- Footer Confirmación -->
          <div class="modal-footer">
            <button type="button" class="btn-secondary" :disabled="isUnlinking" @click="closeUnlinkModal">
              Cancelar
            </button>
            <button
              type="button"
              class="btn-danger-confirm"
              :disabled="isUnlinking"
              @click="handleConfirmUnlink"
            >
              <RefreshCw v-if="isUnlinking" :size="16" class="spin-icon" />
              <Unlink v-else :size="16" />
              <span>{{ isUnlinking ? 'Desvinculando...' : 'Sí, Desvincular Sensor' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* =========================================
   ESTILOS DE DISPOSITIVOS IOT
   ========================================= */
.devices-view {
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
.devices-header {
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

.btn-scan {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 0.55rem 0.95rem;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  font-weight: 600;
  transition: all 0.15s ease;
}

.btn-scan:hover:not(:disabled) {
  background-color: var(--bg-hover);
  border-color: var(--wine-600);
}

.btn-scan--loading {
  opacity: 0.7;
  cursor: wait;
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Banner de Ping */
.ping-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1.25rem;
  border-radius: var(--radius-md);
  font-size: 0.84rem;
  font-weight: 500;
}

.ping-banner--success {
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border: 1px solid var(--status-good-border);
}

.ping-banner--error {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border: 1px solid var(--status-danger-border);
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

.kpi-icon--online {
  background-color: var(--status-good-bg);
  color: var(--status-good);
}

.kpi-icon--offline {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
}

.kpi-icon--battery {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
}

.kpi-icon--cubas {
  background-color: var(--wine-100);
  color: var(--wine-700);
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

/* 3. Cuadrícula de Dispositivos */
.devices-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1.35rem;
}

.empty-state {
  grid-column: 1 / -1;
  background-color: var(--bg-surface);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 3.5rem 2rem;
  text-align: center;
}

.empty-icon {
  color: var(--text-muted);
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

/* Tarjeta individual de dispositivo */
.device-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-subtle);
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.95rem;
  transition: all 0.15s ease;
}

.device-card:hover {
  border-color: #D3C3BE;
  box-shadow: 0 4px 14px rgba(35, 22, 28, 0.08);
}

.device-card--offline {
  border-left: 4px solid var(--status-danger);
  background-color: #FDFBFA;
}

.device-card--online {
  border-left: 4px solid var(--status-good);
}

.device-card--maintenance {
  border-left: 4px solid var(--status-warn);
}

.device-card--low-battery {
  background-color: #FFFDF9;
}

/* Header tarjeta */
.device-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
}

.device-identity {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.device-icon-box {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--border-color);
}

.device-icon--ds18b20 {
  background-color: var(--wine-100);
  color: var(--wine-700);
}

.device-icon--mpu-6050 {
  background-color: #FEF8EF;
  color: #C47F17;
}

.device-icon--ph-4502c {
  background-color: #E8F8F5;
  color: #0E6251;
}

.device-icon--dual {
  background-color: #E8F4FD;
  color: #1565C0;
}

.device-code-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.device-code {
  font-family: var(--font-mono);
  font-size: 0.98rem;
  font-weight: 700;
  color: var(--wine-900);
}

.device-model-tag {
  font-size: 0.66rem;
  font-family: var(--font-mono);
  background-color: var(--bg-subtle);
  color: var(--text-muted);
  padding: 0.1rem 0.35rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.device-mac {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--text-muted);
  margin-top: 0.15rem;
}

.device-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: var(--radius-full);
  white-space: nowrap;
}

.status-pill--online {
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border: 1px solid var(--status-good-border);
}

.status-pill--offline {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border: 1px solid var(--status-danger-border);
}

.status-pill--maintenance {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
  border: 1px solid var(--status-warn-border);
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--status-good);
  animation: pulse-dot 1.5s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.3; transform: scale(0.85); }
}

/* Banner de Cuba */
.device-cuba-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.55rem 0.75rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}

.cuba-info {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.cuba-icon {
  color: var(--wine-700);
}

.cuba-name {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
}

.cuba-link-btn {
  font-size: 0.72rem;
  color: var(--wine-700);
  font-weight: 600;
  text-decoration: underline;
}

/* Métricas del Hardware */
.device-metrics-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  background-color: var(--bg-subtle);
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius-sm);
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.metric-item-label {
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
}

.signal-indicator,
.power-indicator,
.reading-indicator {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.signal-icon {
  flex-shrink: 0;
}
.signal-excellent { color: #16A34A; }
.signal-good { color: #2563EB; }
.signal-weak { color: #D97706; }
.signal-none { color: #DC2626; }

.signal-rssi {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.power-icon {
  flex-shrink: 0;
}
.mains-icon { color: #D97706; }
.battery-normal { color: #16A34A; }
.battery-low { color: #DC2626; }

.power-text {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.reading-val {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--wine-800);
}

/* Notas y Telemetría */
.device-notes-box {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.notes-text {
  font-size: 0.76rem;
  color: var(--text-secondary);
  line-height: 1.35;
}

.telemetry-time {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.7rem;
  color: var(--text-muted);
}

/* Footer de Botones de Acción */
.device-actions-footer {
  display: flex;
  gap: 0.45rem;
  padding-top: 0.65rem;
  border-top: 1px solid var(--border-subtle);
}

.btn-device-action {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.45rem 0.5rem;
  font-size: 0.74rem;
  font-weight: 600;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.btn-device-action:hover:not(:disabled) {
  background-color: var(--bg-hover);
  border-color: var(--wine-600);
  color: var(--wine-800);
}

.btn-device-action:disabled {
  opacity: 0.5;
  cursor: wait;
}

.btn-device-action--danger:hover {
  background-color: var(--status-danger-bg) !important;
  color: var(--status-danger) !important;
  border-color: var(--status-danger-border) !important;
}

/* =========================================
   MODAL DE EMPAREJAMIENTO
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

.pair-modal {
  width: 100%;
  max-width: 660px;
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
  background-color: var(--wine-100);
  color: var(--wine-700);
  display: flex;
  align-items: center;
  justify-content: center;
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

.modal-form {
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.15rem;
}

@media (max-width: 600px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
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
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-primary);
}

.form-hint {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.form-input,
.form-select,
.form-textarea {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  font-family: inherit;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
  outline: none;
}

.form-input--mono {
  font-family: var(--font-mono);
}

.form-input:focus,
.form-select:focus,
.form-textarea:focus {
  border-color: var(--wine-700);
  background-color: #FFFFFF;
}

.form-textarea {
  resize: vertical;
}

.modal-footer {
  padding-top: 1rem;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.75rem;
}

/* Acciones en el banner de la cuba */
.cuba-banner-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.device-cuba-banner--unassigned {
  background-color: var(--bg-subtle);
  border-left-color: var(--text-muted);
}

.cuba-link-btn--assign {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background-color: var(--wine-100);
  color: var(--wine-700);
  border: 1px solid var(--wine-600);
  font-size: 0.74rem;
  font-weight: 600;
  padding: 0.25rem 0.65rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.cuba-link-btn--assign:hover {
  background-color: var(--wine-700);
  color: #FFFFFF;
}

.btn-device-action--primary {
  background-color: var(--wine-100);
  color: var(--wine-700);
  border-color: var(--wine-600);
  font-weight: 600;
}

.btn-device-action--primary:hover:not(:disabled) {
  background-color: var(--wine-700) !important;
  color: #FFFFFF !important;
  border-color: var(--wine-800) !important;
}

/* Modales de Asignación y Confirmación */
.assign-modal,
.confirm-modal {
  width: 100%;
  max-width: 580px;
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

.confirm-modal {
  max-width: 480px;
}

.modal-icon-badge--danger {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
}

.modal-body-confirm {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

.confirm-warning-box {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  padding: 0.9rem 1.1rem;
  border-radius: var(--radius-md);
  background-color: var(--status-warn-bg);
  border: 1px solid var(--status-warn-border);
  color: var(--status-warn);
}

.confirm-warning-box .warning-icon {
  flex-shrink: 0;
  margin-top: 0.15rem;
}

.warning-text p {
  font-size: 0.86rem;
  line-height: 1.45;
  color: var(--text-primary);
}

.unlink-details {
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.unlink-detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
}

.unlink-detail-row .detail-label {
  color: var(--text-muted);
  font-weight: 500;
}

.unlink-detail-row .detail-val {
  color: var(--text-primary);
  font-weight: 600;
}

.unlink-detail-row .highlight-val {
  color: var(--status-warn);
}

.confirm-footnote {
  font-size: 0.76rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.btn-danger-confirm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  background-color: var(--status-danger);
  color: #FFFFFF;
  padding: 0.55rem 1.1rem;
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
  font-weight: 600;
  transition: background-color 0.15s ease;
  cursor: pointer;
}

.btn-danger-confirm:hover:not(:disabled) {
  background-color: #7A1424;
}

.btn-danger-confirm:disabled {
  opacity: 0.6;
  cursor: wait;
}

/* Banner de error de negocio */
.modal-error-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.85rem 1.1rem;
  border-radius: var(--radius-md);
  background-color: var(--status-danger-bg);
  border: 1px solid var(--status-danger-border);
  color: var(--status-danger);
  font-size: 0.82rem;
  line-height: 1.4;
}

.error-banner-icon {
  flex-shrink: 0;
  margin-top: 0.15rem;
}

.error-banner-content strong {
  display: block;
  font-weight: 700;
  margin-bottom: 0.15rem;
}

.error-banner-content p {
  color: var(--text-primary);
  font-size: 0.8rem;
  word-break: break-word;
}

/* Ficha Resumen de Dispositivo en Asignación */
.device-summary-card {
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 1rem 1.15rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.summary-top {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
  padding-bottom: 0.6rem;
  border-bottom: 1px solid var(--border-subtle);
}

.summary-code {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--wine-900);
}

.summary-model {
  font-size: 0.72rem;
  background-color: var(--wine-100);
  color: var(--wine-700);
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-full);
  font-weight: 600;
}

.summary-status {
  font-size: 0.72rem;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-full);
  font-weight: 600;
  margin-left: auto;
}

.summary-status.status--online {
  background-color: var(--status-good-bg);
  color: var(--status-good);
}

.summary-status.status--offline {
  background-color: var(--bg-subtle);
  color: var(--text-muted);
}

.summary-status.status--maintenance {
  background-color: var(--status-warn-bg);
  color: var(--status-warn);
}

.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.65rem 1rem;
}

@media (max-width: 520px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}

.summary-field {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.summary-field .field-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-weight: 500;
}

.summary-field .field-value {
  font-size: 0.8rem;
  color: var(--text-primary);
  font-weight: 600;
}

.font-mono {
  font-family: var(--font-mono);
}
</style>
