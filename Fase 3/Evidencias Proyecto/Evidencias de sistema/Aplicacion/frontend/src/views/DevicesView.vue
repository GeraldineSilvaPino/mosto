<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowRight, BatteryWarning, ChevronDown, ChevronLeft, ChevronRight, Cylinder, Link, Plus, RadioTower, RefreshCw, Search, SignalLow, Unlink, WifiOff, Wrench, X } from 'lucide-vue-next'
import deviceService from '../services/deviceService'
import cubaService from '../services/cubaService'

const devices = ref([])
const tanks = ref([])
const ready = ref(false)
const tanksReady = ref(false)
const loading = ref(false)
const loadError = ref('')
const tankError = ref('')
const feedback = ref('')
const query = ref('')
const sensor = ref('')
const state = ref('')
const tankFilter = ref('')
const register = ref(null)
const page = ref(0)
const pageSize = 4
const sensorNames = { DS18B20: 'Temperatura', 'MPU-6050': 'Inclinómetro', 'PH-4502C': 'pH', DUAL: 'Sensor dual' }
const states = { online: 'En línea', offline: 'Desconectado', maintenance: 'En mantención' }
const stateName = d => states[d.status] || d.statusLabel || 'Sin estado'
const location = d => d.assignedCubaName || d.assignedCubaCode || 'Sin cuba asignada'
const origin = d => ({ fisico: 'Físico', simulado: 'Simulado' })[d.source] || 'Sin aprovisionar'
const battery = d => d.batteryLevel != null ? `${d.batteryLevel} %` : d.powerSource === 'mains' ? 'Red eléctrica' : 'Sin dato'
function conditions(d) {
  const reasons = []
  if (d.status === 'offline' && d.assignedCubaId != null) reasons.push({ rank: 0, text: d.ultima_conexion ? 'Desconectado' : 'Sin transmisiones', icon: WifiOff })
  if (d.batteryLevel != null && d.batteryLevel < 20) reasons.push({ rank: 1, text: 'Batería al ' + battery(d), icon: BatteryWarning })
  if (d.status === 'online' && d.signalRssi != null && d.signalRssi !== 0 && ['weak', 'none'].includes(d.signalQuality)) reasons.push({ rank: 2, text: 'Señal débil', icon: SignalLow })
  if (d.status === 'maintenance') reasons.push({ rank: 3, text: 'En mantención', icon: Wrench })
  return reasons
}
const queue = computed(() => devices.value.map(device => ({ device, reasons: conditions(device) }))
  .filter(row => row.reasons.length)
  .sort((a,b) => a.reasons[0].rank - b.reasons[0].rank || location(a.device).localeCompare(location(b.device), 'es', { numeric: true }) || a.device.id - b.device.id))
const pages = computed(() => Math.ceil(queue.value.length / pageSize))
watch(pages, count => { page.value = Math.min(page.value, Math.max(0, count - 1)) })
const visibleQueue = computed(() => queue.value.slice(page.value * pageSize, (page.value + 1) * pageSize))
const coverage = computed(() => tanks.value.map(tank => {
  const nodes = devices.value.filter(d => d.assignedCubaId != null && String(d.assignedCubaId) === String(tank.id))
  return { id: tank.id, code: tank.codigo_cuba || tank.nombre, nodes, online: nodes.filter(d => d.status === 'online').length }
}).sort((a,b) => a.online - b.online || a.code.localeCompare(b.code, 'es', { numeric: true })))
const onlineCount = computed(() => devices.value.filter(d => d.status === 'online').length)
const disconnectedCount = computed(() => devices.value.filter(d => d.status === 'offline').length)
const lowBatteryCount = computed(() => devices.value.filter(d => d.batteryLevel != null && d.batteryLevel < 20).length)
const filtersActive = computed(() => Boolean(query.value || sensor.value || state.value || tankFilter.value))
const filtered = computed(() => devices.value.filter(d => {
  const needle = query.value.trim().toLowerCase()
  if (sensor.value && sensor.value !== d.sensorType) return false
  if (state.value && state.value !== d.status) return false
  if (tankFilter.value && tankFilter.value !== String(d.assignedCubaId ?? 'none')) return false
  return !needle || [d.code,d.name,d.mac,d.ipAddress,d.sensorType,location(d)].some(v => v?.toLowerCase().includes(needle))
}))
function resetFilters() { query.value = sensor.value = state.value = tankFilter.value = '' }
async function filterTank(id) {
  resetFilters()
  tankFilter.value = String(id)
  await nextTick()
  register.value?.focus()
}

let generation = 0
let timer
async function load() {
  const current = ++generation
  loading.value = true
  const [inventory, catalog] = await Promise.allSettled([deviceService.listarDispositivos(), cubaService.listarCubas()])
  if (current !== generation) return
  loadError.value = inventory.status === 'rejected' ? 'No se pudo actualizar el inventario.' : ''
  tankError.value = catalog.status === 'rejected' ? 'No se pudo actualizar la lista de cubas.' : ''
  if (!loadError.value) { devices.value = inventory.value; ready.value = true }
  if (!tankError.value) { tanks.value = catalog.value; tanksReady.value = true }
  loading.value = false
}
onMounted(() => {
  load()
  timer = setInterval(() => { if (!mode.value && !loading.value) load() }, 15000)
})
onBeforeUnmount(() => { clearInterval(timer); generation++ })

const modal = ref(null)
const mode = ref('')
const activeId = ref(null)
const active = computed(() => devices.value.find(d => d.id === activeId.value))
const saving = ref(false)
const formError = ref('')
const freshDraft = () => ({ mac: '', model: 'ESP32-WROOM-32D', sensorType: 'DS18B20', cubaId: '' })
const draft = ref(freshDraft())
const destination = ref('')
const modalTitle = computed(() => ({ detail: active.value?.code, pair: 'Registrar dispositivo', assign: active.value?.assignedCubaId ? 'Reasignar cuba' : 'Asignar cuba', unlink: 'Desvincular dispositivo' })[mode.value])
function changeMode(next) {
  formError.value = ''
  mode.value = next
  if (next === 'assign') destination.value = String(active.value?.assignedCubaId ?? '')
}
async function openDialog(next, device) {
  activeId.value = device?.id ?? null
  draft.value = freshDraft()
  feedback.value = ''
  changeMode(next)
  await nextTick()
  modal.value?.showModal()
}
function closeDialog() {
  if (saving.value) return
  modal.value?.close()
  mode.value = ''
  activeId.value = null
}
async function submit() {
  if (saving.value) return
  saving.value = true
  formError.value = ''
  try {
    let updated
    if (mode.value === 'pair') {
      const mac = draft.value.mac.trim().toUpperCase()
      // El servidor asigna código y nombre; el contrato de alta aún exige ambos campos.
      updated = await deviceService.registrarDispositivo({ ...draft.value, mac, code: mac, name: draft.value.sensorType, cubaId: draft.value.cubaId || null })
      feedback.value = 'Dispositivo registrado.'
    } else if (mode.value === 'assign') {
      updated = await deviceService.vincular(activeId.value, Number(destination.value))
      feedback.value = 'Asignación actualizada.'
    } else {
      updated = await deviceService.desvincular(activeId.value)
      feedback.value = 'Dispositivo desvinculado.'
    }
    generation++
    loading.value = false
    const index = devices.value.findIndex(d => d.id === updated.id)
    if (index < 0) devices.value.unshift(updated)
    else devices.value[index] = updated
    activeId.value = updated.id
    changeMode('detail')
  } catch (err) {
    formError.value = err.message || 'No se pudo guardar el cambio. Inténtalo de nuevo.'
  } finally { saving.value = false }
}
</script>

<template>
  <div class="iot">
    <header class="head">
      <div><h1>Dispositivos IoT</h1><p>Conectividad y cobertura de las cubas</p></div>
      <div class="actions">
        <button class="button" :disabled="loading" @click="load"><RefreshCw :size="15"/>{{ loading ? 'Actualizando…' : 'Actualizar' }}</button>
        <button class="button primary" @click="openDialog('pair')"><Plus :size="16"/>Registrar dispositivo</button>
      </div>
    </header>
    <p v-if="loadError || tankError" class="error" role="alert">{{ loadError }} {{ tankError }} <button class="link" @click="load">Reintentar</button></p>

    <div class="overview">
      <section class="review" aria-labelledby="review-title">
        <header class="section-head"><h2 id="review-title">Equipos por revisar</h2><span v-if="ready" class="count">{{ queue.length }}</span></header>
        <ul v-if="visibleQueue.length" class="review-list">
          <li v-for="{device, reasons} in visibleQueue" :key="device.id">
            <button class="review-row" @click="openDialog('detail', device)">
              <component :is="reasons[0].icon" :size="18" aria-hidden="true"/>
              <span class="place"><b>{{ location(device) }}</b><small>{{ device.code }}</small></span>
              <span class="reason">{{ reasons.map(r => r.text).join(' · ') }}</span>
              <ChevronRight :size="16" aria-hidden="true"/>
            </button>
          </li>
        </ul>
        <p v-else class="notice">{{ ready ? (devices.length ? 'Ningún equipo cumple los criterios de revisión.' : 'Aún no hay equipos registrados.') : loadError ? 'Revisión no disponible.' : 'Consultando los equipos…' }}</p>
        <footer v-if="pages > 1" class="pager">
          <span aria-live="polite">{{ page * pageSize + 1 }}–{{ Math.min((page+1)*pageSize, queue.length) }} de {{ queue.length }} equipos</span>
          <button aria-label="Equipos anteriores" :disabled="page === 0" @click="page--"><ChevronLeft :size="16"/></button>
          <button aria-label="Equipos siguientes" :disabled="page + 1 >= pages" @click="page++"><ChevronRight :size="16"/></button>
        </footer>
      </section>
      <section class="coverage" aria-labelledby="coverage-title">
        <header class="section-head"><h2 id="coverage-title">Cobertura por cuba</h2><RadioTower :size="20" aria-hidden="true"/></header>
        <p v-if="ready && tanksReady">{{ coverage.filter(c => c.online).length }} de {{ coverage.length }} cubas con equipos en línea</p>
        <ul v-if="ready && coverage.length" class="coverage-list">
          <li v-for="c in coverage" :key="c.id">
            <button @click="filterTank(c.id)" :aria-label="'Ver equipos de ' + c.code + ', ' + c.online + ' de ' + c.nodes.length + ' en línea'">
              <b>{{ c.code }}</b><span class="node-marks" aria-hidden="true"><i v-for="d in c.nodes.slice(0,8)" :key="d.id" :class="{connected:d.status === 'online'}"></i></span>
              <span>{{ c.nodes.length ? c.online + ' / ' + c.nodes.length : 'Sin equipos' }}</span><ChevronRight :size="14" aria-hidden="true"/>
            </button>
          </li>
        </ul>
        <p v-else class="notice">{{ tankError || loadError ? 'Cobertura no disponible.' : loading ? 'Consultando cobertura…' : 'Sin cubas registradas.' }}</p>
      </section>
    </div>

    <section class="inventory" aria-labelledby="inventory-title">
      <header class="inventory-head">
        <h2 ref="register" id="inventory-title" tabindex="-1">Inventario de equipos</h2>
        <p v-if="ready">{{ onlineCount }} en línea · {{ disconnectedCount }} desconectados · {{ lowBatteryCount }} con batería baja</p>
      </header>
      <div class="filters">
        <label class="search"><Search :size="16" aria-hidden="true"/><input v-model="query" aria-label="Buscar dispositivos" type="search" placeholder="Buscar equipo, MAC, IP o cuba"/></label>
        <label class="select"><select v-model="sensor" aria-label="Tipo de sensor"><option value="">Todos los sensores</option><option v-for="(label,key) in sensorNames" :key="key" :value="key">{{ label }} · {{ key }}</option></select><ChevronDown :size="14"/></label>
        <label class="select"><select v-model="state" aria-label="Estado del equipo"><option value="">Todos los estados</option><option v-for="(label,key) in states" :key="key" :value="key">{{ label }}</option></select><ChevronDown :size="14"/></label>
        <label class="select"><select v-model="tankFilter" aria-label="Cuba asignada"><option value="">Todas las cubas</option><option v-for="c in tanks" :key="c.id" :value="String(c.id)">{{ c.nombre || c.codigo_cuba }}</option><option value="none">Sin asignar</option></select><ChevronDown :size="14"/></label>
        <button v-if="filtersActive" class="link" @click="resetFilters">Limpiar filtros</button>
      </div>
      <ul v-if="filtered.length" class="inventory-list">
        <li v-for="d in filtered" :key="d.id">
          <button class="inventory-row" @click="openDialog('detail',d)">
            <span class="identity"><b>{{ d.code }}</b><small>{{ d.sensorType }} · {{ origin(d) }}</small></span>
            <span class="tank">{{ location(d) }}</span>
            <span class="connection"><span class="status" :class="d.status">{{ stateName(d) }}</span><small>{{ d.lastTelemetry }}</small></span>
            <ChevronRight :size="16" aria-hidden="true"/>
          </button>
        </li>
      </ul>
      <p v-else class="notice">{{ !ready ? (loadError ? 'Inventario no disponible.' : 'Consultando inventario…') : filtersActive ? 'Sin equipos para estos filtros.' : 'Todavía no hay dispositivos registrados.' }}</p>
    </section>

    <dialog ref="modal" aria-labelledby="device-title" @cancel.prevent="closeDialog" @click.self="closeDialog">
      <div class="dialog-content">
        <header class="dialog-head"><h2 id="device-title">{{ modalTitle }}</h2><button aria-label="Cerrar ficha" :disabled="saving" @click="closeDialog"><X :size="18"/></button></header>
        <section v-if="mode === 'detail' && active" class="device-detail">
          <div class="detail-location"><Cylinder :size="18"/><strong>{{ location(active) }}</strong><RouterLink v-if="active.assignedCubaId" :to="'/cubas/' + active.assignedCubaId">Ver telemetría <ArrowRight :size="14"/></RouterLink></div>
          <p v-if="feedback" role="status" class="feedback">{{ feedback }}</p>
          <dl class="readings">
            <div><dt>Conexión</dt><dd>{{ stateName(active) }}</dd></div>
            <div><dt>Última transmisión</dt><dd>{{ active.lastTelemetry || 'Sin dato' }}</dd></div>
            <div><dt>Señal Wi-Fi</dt><dd>{{ active.signalRssi == null ? 'Sin dato' : active.signalRssi + ' dBm' }}</dd></div>
            <div><dt>Alimentación</dt><dd>{{ battery(active) }}</dd></div>
            <div class="wide"><dt>Última lectura</dt><dd>{{ active.lastReadingValue || 'Sin medición válida' }}</dd></div>
          </dl>
          <h3>Ficha técnica</h3>
          <dl class="specs">
            <div><dt>Sensor</dt><dd>{{ active.sensorLabel || active.sensorType }}</dd></div>
            <div><dt>Modelo</dt><dd>{{ active.model }}</dd></div>
            <div><dt>MAC</dt><dd>{{ active.mac }}</dd></div>
            <div><dt>Origen</dt><dd>{{ origin(active) }}</dd></div>
            <div v-if="active.firmware"><dt>Firmware</dt><dd>{{ active.firmware }}</dd></div>
            <div v-if="active.ipAddress"><dt>Dirección IP</dt><dd>{{ active.ipAddress }}</dd></div>
            <div v-if="active.samplingInterval"><dt>Intervalo</dt><dd>{{ active.samplingInterval }}</dd></div>
          </dl>
          <p v-if="active.notes">{{ active.notes }}</p>
          <footer class="actions"><button class="button primary" @click="changeMode('assign')"><Link :size="14"/>{{ active.assignedCubaId ? 'Reasignar cuba' : 'Asignar cuba' }}</button><button v-if="active.assignedCubaId" class="button" @click="changeMode('unlink')"><Unlink :size="14"/>Desvincular</button></footer>
        </section>
        <form v-else-if="mode" class="editor" @submit.prevent="submit">
          <template v-if="mode === 'pair'">
            <label>Dirección MAC<input v-model.trim="draft.mac" required placeholder="24:6F:28:00:00:01" pattern="([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}" :disabled="saving"/></label>
            <label>Modelo<select v-model="draft.model" :disabled="saving"><option>ESP32-WROOM-32D</option><option>ESP32-C3-Mini</option><option>ESP32-S3-DevKit</option></select></label>
            <label>Sensor<select v-model="draft.sensorType" :disabled="saving"><option v-for="(label,key) in sensorNames" :key="key" :value="key">{{ label }} · {{ key }}</option></select></label>
            <label>Cuba<select v-model="draft.cubaId" :disabled="saving"><option value="">Sin asignar</option><option v-for="c in tanks" :key="c.id" :value="c.id">{{ c.nombre || c.codigo_cuba }}</option></select></label>
          </template>
          <template v-if="mode === 'assign' && active">
            <p class="wide">{{ active.code }} · {{ location(active) }}</p>
            <label class="wide">Cuba de destino<select v-model="destination" required :disabled="saving"><option disabled value="">Seleccionar cuba</option><option v-for="c in tanks" :key="c.id" :value="String(c.id)">{{ c.nombre || c.codigo_cuba }}</option></select></label>
          </template>
          <p v-if="mode === 'unlink' && active" class="wide">Al desvincular <b>{{ active.code }}</b> de <b>{{ location(active) }}</b>, el equipo quedará disponible para otra cuba.</p>
          <p v-if="tankError && mode !== 'unlink'" class="error wide" role="alert">{{ tankError }} <button type="button" class="link" @click="load">Reintentar</button></p>
          <p v-if="formError" class="error wide" role="alert">{{ formError }}</p>
          <footer class="actions wide"><button type="button" :disabled="saving" class="button" @click="mode === 'pair' ? closeDialog() : changeMode('detail')">Cancelar</button><button type="submit" class="button primary" :disabled="saving || (mode === 'assign' && (!destination || destination === String(active?.assignedCubaId)))">{{ saving ? 'Guardando…' : mode === 'unlink' ? 'Confirmar desvinculación' : mode === 'assign' ? 'Confirmar asignación' : 'Registrar equipo' }}</button></footer>
        </form>
      </div>
    </dialog>
  </div>
</template>

<style scoped>
.iot {
  --ink:#30232a; --muted:#695d61; --wine:#763c51; --rule:#dbd2ca; --paper:#fffdf9;
  --display:'Instrument Serif', Georgia, serif;
  max-width:1540px; margin-inline:auto; color:var(--ink);
}
h1,h2,h3 { font-family:var(--display); font-weight:400; line-height:1.1; letter-spacing:-.02em; }
h1 { font-size:clamp(2.55rem,4vw,3.25rem); }
h2 { font-size:clamp(1.65rem,2.3vw,2.05rem); }
h3 { font-size:1.5rem; }
.head,.section-head,.actions,.inventory-head,.filters,.search,.dialog-head,.detail-location,.detail-location a,.pager,.button { display:flex; align-items:center; gap:9px; }
.head,.inventory-head,.dialog-head { justify-content:space-between; flex-wrap:wrap; }
.head { margin-bottom:19px; }
.head p,.inventory-head p,.coverage p { color:var(--muted); font-size:.83rem; margin-top:5px; }
.actions,.filters,.detail-location { flex-wrap:wrap; }
.button { justify-content:center; min-height:38px; padding:8px 12px; border:1px solid var(--rule); border-radius:7px; background:var(--paper); color:var(--ink); font:600 .83rem/1.4 var(--font-sans); }
.button:hover:enabled { border-color:var(--wine); }
.button.primary { background:var(--wine); color:var(--paper); border-color:var(--wine); }
.button.primary:hover:enabled { background:#603044; }
button:disabled { opacity:.5; cursor:default; }
.iot :focus-visible { outline:2px solid var(--wine); outline-offset:2px; }
.iot ::selection { background:#ead3db; color:var(--ink); }
.overview { display:grid; grid-template-columns:minmax(0,1.75fr) minmax(250px,1fr); background:#efe8de; border-radius:14px; overflow:hidden; }
.review,.coverage { padding:20px clamp(16px,2vw,26px); min-width:0; }
.section-head { justify-content:space-between; gap:10px; margin-bottom:10px; }
.count { font:400 1.9rem/1 var(--display); color:var(--wine); }
ul { list-style:none; }
.review-list { border-top:1px solid #cdbfb6; }
.review-list li { border-bottom:1px solid #d6c9bf; }
.review-row,.inventory-row,.coverage-list button { width:100%; align-items:center; display:grid; text-align:left; color:inherit; }
.review-row { grid-template-columns:22px minmax(85px,1fr) minmax(90px,.88fr) 16px; gap:10px; padding:10px 2px; }
.review-row:hover { background:#e8ded4; }
.review-row svg,.inventory-row > svg { color:var(--wine); }
.place b,.identity b { display:block; font-size:.89rem; }
small { display:block; margin-top:2px; font-size:.75rem; color:var(--muted); }
.reason,.tank,.connection { font-size:.82rem; }
.pager { margin-top:7px; justify-content:flex-end; color:var(--muted); font-size:.76rem; }
.pager span { margin-right:auto; }
.pager button,.dialog-head button { width:32px; height:32px; display:grid; place-items:center; border:1px solid var(--rule); border-radius:5px; color:var(--wine); }
.coverage { background:#32232d; color:#fff6ee; }
.coverage .section-head { margin-bottom:0; }
.coverage p { color:#e2ced5; }
.coverage-list { max-height:225px; overflow:auto; margin-top:10px; scrollbar-color:#866b79 #32232d; }
.coverage-list li { border-top:1px solid #59454f; }
.coverage-list button { gap:8px; grid-template-columns:minmax(65px,1fr) auto auto 14px; padding:9px 1px; font-size:.8rem; }
.coverage-list button:hover { background:#48343f; }
.coverage-list button:focus-visible { outline-color:#f2c8cf; outline-offset:-2px; }
.coverage-list button span { font-variant-numeric:tabular-nums; }
.node-marks { display:flex; gap:3px; margin-right:4px; }
.node-marks i { display:block; width:5px; height:11px; border:1px solid #ae94a0; border-radius:1px; }
.node-marks i.connected { background:#e7bdba; border-color:#e7bdba; }
.inventory { margin-top:18px; border:1px solid var(--rule); border-radius:12px; background:var(--paper); overflow:hidden; }
.inventory-head,.filters { padding:16px 21px 8px; }
.inventory-head p { margin:0; }
.filters { padding-block:5px 14px; }
.select,.search { min-width:0; position:relative; }
.search { flex:1 1 195px; padding:0 9px; border:1px solid var(--rule); border-radius:6px; color:var(--muted); }
.search input { background:transparent; border:0; width:100%; min-width:0; font:inherit; font-size:.82rem; color:var(--ink); padding:9px 0; }
.search input::placeholder { color:var(--muted); }
.select select { width:100%; max-width:190px; appearance:none; border:0; border-bottom:1px solid #b79ba5; background:transparent; color:var(--wine); padding:8px 20px 8px 2px; font:600 .81rem/1.5 var(--font-sans); cursor:pointer; }
.select svg { pointer-events:none; position:absolute; right:2px; top:50%; transform:translateY(-50%); color:var(--wine); }
.link,.detail-location a { color:var(--wine); font-weight:600; font-size:.8rem; text-decoration:underline; text-underline-offset:3px; }
.inventory-list li { border-top:1px solid var(--rule); }
.inventory-row { padding:12px 21px; gap:14px; grid-template-columns:minmax(130px,1.2fr) minmax(105px,1fr) minmax(110px,.7fr) 16px; }
.inventory-row:hover { background:#f7f2eb; }
.inventory-row:focus-visible { outline-offset:-3px; }
.status { display:inline-flex; align-items:center; gap:6px; }
.status::before { content:''; width:7px; height:7px; border:1px solid currentColor; border-radius:50%; }
.status.online::before { background:#557153; border-color:#557153; }
.status.offline { color:#884053; }
.notice,.error { padding:15px 0; font-size:.85rem; }
.inventory .notice { padding:20px; }
.error { color:#882f40; }
dialog { margin:auto; padding:0; width:min(520px,calc(100% - 24px)); max-height:90dvh; overflow:auto; color:var(--ink); border:0; border-radius:12px; background:var(--paper); }
dialog::backdrop { background:rgba(40,25,34,.55); }
.dialog-head { padding:18px 22px; background:#efe8df; flex-wrap:nowrap; }
.dialog-head button { flex:none; }
.device-detail,.editor { padding:18px 22px; }
.detail-location { padding-bottom:14px; border-bottom:1px solid var(--rule); }
.detail-location a { margin-left:auto; }
.readings,.specs,.editor { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
.readings { padding:14px 0; }
dt { color:var(--muted); font-size:.76rem; }
dd { margin:4px 0 0; font-size:.89rem; overflow-wrap:anywhere; }
.wide { grid-column:1/-1; }
.specs { padding:12px 0 17px; }
.device-detail footer,.editor footer { padding-top:14px; border-top:1px solid var(--rule); }
.editor label { display:grid; gap:5px; font-size:.84rem; font-weight:600; }
.editor input,.editor select { padding:9px; min-width:0; width:100%; border:1px solid #bbaea5; border-radius:6px; font:400 .9rem/1.5 var(--font-sans); color:var(--ink); background:var(--paper); }
.editor p,.feedback { font-size:.86rem; line-height:1.6; }
.feedback { margin-top:10px; color:var(--wine); }
.editor footer { justify-content:flex-end; }
@media(max-width:850px) {
  .overview { grid-template-columns:minmax(0,1.35fr) minmax(200px,1fr); }
}
@media(max-width:700px) {
  .overview { grid-template-columns:minmax(0,1fr); }
  .review,.coverage { padding:15px; }
  .coverage-list { max-height:160px; }
  .head { gap:12px; }
  .inventory-head,.filters { padding-inline:14px; }
  .inventory-head { gap:5px; }
  .inventory-row { grid-template-columns:minmax(0,1fr) minmax(0,.8fr) 14px; gap:4px 8px; padding:12px 14px; }
  .identity { grid-column:1; }
  .tank { grid-column:1; grid-row:2; color:var(--muted); }
  .connection { grid-column:2; grid-row:1/3; }
  .inventory-row > svg { grid-column:3; grid-row:1/3; }
}
@media(max-width:480px) {
  .review-row { grid-template-columns:17px minmax(0,1fr) 14px; gap:3px 8px; }
  .review-row > svg:first-child { grid-column:1; grid-row:1; }
  .review-row > svg:last-child { grid-column:3; grid-row:1/3; }
  .reason { grid-column:2; color:var(--wine); }
  .filters { gap:5px 10px; }
  .filters .search { flex-basis:100%; }
  .select { max-width:100%; }
  .select select { max-width:154px; }
  .editor { grid-template-columns:minmax(0,1fr); }
  .device-detail,.editor,.dialog-head { padding:15px; }
}
</style>
