<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { AlertTriangle, BookOpen, ChevronDown, ChevronRight, ClipboardList, FileText, FlaskConical, PenLine, Search, Settings, SlidersHorizontal, Thermometer, X } from 'lucide-vue-next'
import binnacleService from '../services/binnacleService'
import cubaService from '../services/cubaService'
import authService from '../services/authService'

const types = {
  nota: { label: 'Nota', icon: FileText },
  alerta: { label: 'Alerta', icon: AlertTriangle },
  config: { label: 'Configuración', icon: Settings },
  lectura: { label: 'Lectura', icon: Thermometer },
  intervencion: { label: 'Intervención', icon: ClipboardList },
  medicion_manual: { label: 'Medición manual', icon: FlaskConical },
  ajuste_perfil: { label: 'Ajuste de perfil', icon: SlidersHorizontal }
}
const writableTypes = ['nota', 'alerta', 'config', 'lectura']
const typeLabel = key => types[key]?.label || String(key || 'Entrada').replaceAll('_', ' ')
const entries = ref([])
const tanks = ref([])
const loading = ref(true)
const loadError = ref('')
const tankError = ref('')
const search = ref('')
const typeFilter = ref('')
const chosenDay = ref('')
const writing = ref(false)
const saving = ref(false)
const saveError = ref('')
const confirmation = ref('')
const writeButton = ref(null)
const messageField = ref(null)
const author = authService.obtenerUsuarioSesion()?.name
const draft = ref({ type: 'nota', cuba: 'general', message: '' })

async function loadEntries() {
  loading.value = true
  loadError.value = ''
  try {
    entries.value = await binnacleService.listarEntradas()
  } catch (err) {
    loadError.value = err.message || 'No se pudo cargar la bitácora.'
  } finally {
    loading.value = false
  }
}
async function loadTanks() {
  tankError.value = ''
  try {
    tanks.value = await cubaService.listarCubas()
  } catch {
    tankError.value = 'No se pudieron cargar las cubas.'
  }
}
onMounted(() => { loadEntries(); loadTanks() })

// El servicio devuelve un código de cuba o el identificador «cuba-NN».
const tankNames = computed(() => {
  const names = new Map([['general', 'General']])
  for (const tank of tanks.value) {
    const label = tank.nombre || tank.codigo_cuba || `Cuba ${tank.id}`
    names.set(`cuba-${String(tank.id).padStart(2, '0')}`, label)
    if (tank.codigo_cuba) names.set(tank.codigo_cuba.toLowerCase().replace(/^cb-?/, 'cuba-'), label)
  }
  return names
})
const tankLabel = id => tankNames.value.get(id) || id || 'General'
const fold = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const typeCounts = computed(() => {
  const counts = new Map(writableTypes.map(key => [key, 0]))
  for (const entry of entries.value) counts.set(entry.type, (counts.get(entry.type) || 0) + 1)
  return counts
})

const shortDate = new Intl.DateTimeFormat('es-CL', { day: 'numeric', month: 'short', year: 'numeric' })
const weekday = new Intl.DateTimeFormat('es-CL', { weekday: 'long' })
const hour = new Intl.DateTimeFormat('es-CL', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
function dayKey(date) {
  return [date.getFullYear(), String(date.getMonth()+1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
}
const today = new Date()
const days = computed(() => {
  const groups = new Map()
  const q = fold(search.value.trim())
  const sorted = [...entries.value].sort((a,b) => Date.parse(b.timestamp) - Date.parse(a.timestamp) || b.id - a.id)
  for (const entry of sorted) {
    if (typeFilter.value && entry.type !== typeFilter.value) continue
    if (q && ![entry.message, entry.author, tankLabel(entry.cuba), entry.cuba, typeLabel(entry.type)].some(value => fold(value).includes(q))) continue
    const date = new Date(entry.timestamp)
    const key = dayKey(date)
    if (!groups.has(key)) groups.set(key, { key, date, items: [] })
    groups.get(key).items.push(entry)
  }
  return [...groups.values()]
})
const currentDay = computed(() => days.value.find(day => day.key === chosenDay.value) || days.value[0])
const hasFilters = computed(() => Boolean(typeFilter.value || search.value.trim()))
function resetFilters() {
  typeFilter.value = ''
  search.value = ''
}
async function openWriter() {
  writing.value = true
  confirmation.value = saveError.value = ''
  await nextTick()
  messageField.value?.focus()
}
async function closeWriter() {
  if (saving.value) return
  writing.value = false
  saveError.value = ''
  draft.value = { type: 'nota', cuba: 'general', message: '' }
  await nextTick()
  writeButton.value?.focus()
}
async function saveEntry() {
  const message = draft.value.message.trim()
  if (message.length < 2 || saving.value || loading.value) return
  saving.value = true
  saveError.value = ''
  try {
    const saved = await binnacleService.registrarEntrada({ ...draft.value, message })
    entries.value = [saved, ...entries.value.filter(entry => entry.id !== saved.id)]
    chosenDay.value = dayKey(new Date(saved.timestamp))
    resetFilters()
    confirmation.value = 'Entrada registrada.'
    saving.value = false
    await closeWriter()
    if (loadError.value) await loadEntries()
  } catch (err) {
    saveError.value = err.message || 'No se pudo registrar la entrada.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="binnacle">
    <header class="page-head">
      <div><h1>Bitácora de bodega</h1><p>Observaciones e intervenciones por jornada</p></div>
      <button ref="writeButton" type="button" class="wine-button" :aria-expanded="writing" @click="openWriter">
        <PenLine :size="16" aria-hidden="true"/>Nueva entrada
      </button>
    </header>

    <form v-if="writing" class="writer" @submit.prevent="saveEntry" @keydown.esc.prevent="closeWriter">
      <header><h2>Nueva entrada</h2><button type="button" aria-label="Cerrar formulario" :disabled="saving" @click="closeWriter"><X :size="18"/></button></header>
      <div class="fields">
        <div class="field">
          <label for="entry-kind">Tipo de entrada</label>
          <span class="select-wrap">
            <select id="entry-kind" v-model="draft.type" :disabled="saving">
              <option v-for="key in writableTypes" :key="key" :value="key">{{ typeLabel(key) }}</option>
            </select>
            <ChevronDown :size="15" aria-hidden="true"/>
          </span>
        </div>
        <div class="field">
          <label for="entry-tank">Cuba</label>
          <span class="select-wrap">
            <select id="entry-tank" v-model="draft.cuba" :disabled="saving">
              <option value="general">General</option>
              <option v-for="tank in tanks" :key="tank.id" :value="String(tank.id)">{{ tank.nombre || tank.codigo_cuba || tank.id }}</option>
            </select>
            <ChevronDown :size="15" aria-hidden="true"/>
          </span>
        </div>
      </div>
      <p v-if="tankError" role="alert">{{ tankError }} <button type="button" class="text-action" @click="loadTanks">Reintentar</button></p>
      <label>Observación<textarea ref="messageField" v-model="draft.message" rows="3" required minlength="2" :disabled="saving" @keydown.ctrl.enter.prevent="saveEntry" @keydown.meta.enter.prevent="saveEntry"/></label>
      <p v-if="saveError" role="alert">{{ saveError }}</p>
      <footer><span>{{ author ? 'Firma · ' + author : 'Se registra con tu usuario' }}</span><div><button class="plain-button" type="button" :disabled="saving" @click="closeWriter">Cancelar</button><button class="wine-button" :disabled="saving || loading || draft.message.trim().length < 2">{{ saving ? 'Guardando…' : 'Registrar entrada' }}</button></div></footer>
    </form>
    <p v-if="confirmation" class="confirmation" role="status">{{ confirmation }}</p>

    <div class="notebook">
      <aside class="index" aria-labelledby="day-index">
        <div class="index-title"><BookOpen :size="21" :stroke-width="1.5" aria-hidden="true"/><h2 id="day-index">Jornadas</h2></div>
        <ul v-if="days.length" class="day-list">
          <li v-for="day in days" :key="day.key">
            <button type="button" :aria-current="day.key === currentDay.key ? 'date' : undefined" @click="chosenDay = day.key">
              <span><b>{{ shortDate.format(day.date) }}</b><small>{{ day.items.length }} {{ day.items.length === 1 ? 'entrada' : 'entradas' }}</small></span><ChevronRight :size="15" aria-hidden="true"/>
            </button>
          </li>
        </ul>
        <label v-if="days.length" class="mobile-days select-wrap"><select aria-label="Elegir jornada" :value="currentDay.key" @change="chosenDay = $event.target.value"><option v-for="day in days" :key="day.key" :value="day.key">{{ shortDate.format(day.date) }} ({{ day.items.length }})</option></select><ChevronDown :size="15"/></label>
        <p v-else class="index-empty">{{ loading ? 'Cargando jornadas…' : loadError ? 'Índice no disponible' : hasFilters ? 'Sin coincidencias' : 'Sin jornadas registradas' }}</p>
      </aside>

      <section class="sheet" aria-label="Registro de la jornada">
        <div class="tools">
          <label class="search"><Search :size="16" aria-hidden="true"/><input v-model="search" type="search" aria-label="Buscar en todas las jornadas" placeholder="Buscar por texto, autor o cuba"/></label>
          <span class="select-wrap"><select v-model="typeFilter" aria-label="Filtrar por tipo de entrada"><option value="">Todos los tipos</option><option v-for="[key, count] in typeCounts" :key="key" :value="key">{{ typeLabel(key) }} ({{ count }})</option></select><ChevronDown :size="15"/></span>
        </div>
        <p v-if="loadError" class="notice" role="alert">{{ loadError }} <button type="button" class="text-action" @click="loadEntries">Reintentar</button></p>
        <div v-if="loading" class="notice" role="status">Consultando entradas…</div>
        <template v-else-if="currentDay || (!loadError && !hasFilters)">
          <header class="date-head">
            <time class="date-number" :datetime="currentDay?.key || dayKey(today)">{{ (currentDay?.date || today).getDate() }}</time>
            <div><h2>{{ (currentDay?.date || today).toLocaleDateString('es-CL', {month:'long', year:'numeric'}) }}</h2><p>{{ weekday.format(currentDay?.date || today) }} · {{ currentDay?.items.length || 0 }} {{ currentDay?.items.length === 1 ? 'entrada' : 'entradas' }}</p></div>
          </header>
          <ol v-if="currentDay" class="records">
            <li v-for="entry in currentDay.items" :key="entry.id">
              <time :datetime="entry.timestamp">{{ hour.format(new Date(entry.timestamp)) }}</time>
              <div class="record-body">
                <div class="record-meta"><span class="kind"><component :is="types[entry.type]?.icon || FileText" :size="15" aria-hidden="true"/>{{ typeLabel(entry.type) }}</span><span>{{ tankLabel(entry.cuba) }}</span></div>
                <p class="observation">{{ entry.message }}</p>
                <small v-if="entry.dosis">Dosis · {{ entry.dosis }}</small>
                <p class="byline">{{ entry.author }}</p>
              </div>
            </li>
          </ol>
          <div v-else class="empty"><h3>La primera página está en blanco</h3><p>Registra una observación para abrir la jornada.</p><button type="button" class="text-action" @click="openWriter">Escribir la primera entrada</button></div>
        </template>
        <div v-else-if="!loadError" class="empty"><h3>Sin entradas para esta búsqueda</h3><button type="button" class="text-action" @click="resetFilters">Limpiar filtros</button></div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.binnacle {
  --paper: #fffdf9;
  --ink: #30232a;
  --muted: #685b61;
  --rule: #dbd2c9;
  --wine: #763c51;
  --display: 'Instrument Serif', Georgia, serif;
  max-width: 1540px;
  margin-inline: auto;
  color: var(--ink);
}
.page-head, .writer header, .writer footer, .writer footer div, .tools, .index-title, .record-meta, .date-head { display: flex; align-items: center; }
.page-head, .writer header, .writer footer { justify-content: space-between; gap: 12px; }
.page-head { margin-bottom: 20px; flex-wrap: wrap; }
h1, h2, h3, .date-number { font-family: var(--display); font-weight: 400; line-height: 1.08; }
h1 { font-size: clamp(2.5rem, 4vw, 3.25rem); letter-spacing: -.025em; }
.page-head p, .empty p { color: var(--muted); font-size: .86rem; margin-top: 6px; }
.wine-button, .plain-button {
  display: inline-flex; justify-content: center; align-items: center; gap: 8px;
  min-height: 38px; padding: 8px 14px; border: 1px solid transparent; border-radius: 7px;
  font: 600 .84rem/1.4 var(--font-sans);
}
.wine-button { color: #fffaf6; background: var(--wine); }
.wine-button:hover:enabled { background: #603044; }
.plain-button { border-color: var(--rule); background: var(--paper); color: var(--ink); }
button:disabled { opacity: .6; cursor: default; }
.binnacle :focus-visible { outline: 2px solid var(--wine); outline-offset: 3px; }
.binnacle ::selection { color: var(--ink); background: #ead3db; }
.notebook {
  display: grid; grid-template-columns: clamp(200px, 21%, 280px) minmax(0, 1fr);
  background: var(--paper); border: 1px solid var(--rule); border-radius: 12px; overflow: clip;
}
.index { padding: 23px 18px; background: #32232d; color: #fbf4ea; min-width: 0; }
.index-title { gap: 10px; margin-bottom: 17px; }
.index-title svg { color: #debdc6; }
.index-title h2 { font-size: 1.85rem; }
.index-empty, .day-list { border-top: 1px solid #67515d; }
.index-empty { padding-top: 15px; color: #deced4; font-size: .81rem; }
.day-list { list-style: none; max-height: 65vh; overflow-y: auto; scrollbar-color: #8a6c79 #32232d; }
.day-list li { border-bottom: 1px solid #59434e; }
.day-list button {
  display: flex; align-items: center; justify-content: space-between; text-align: left; width: 100%;
  gap: 6px; padding: 12px 9px; color: inherit;
}
.day-list b { display: block; font-size: .83rem; font-weight: 600; }
.day-list small { display: block; font-size: .75rem; margin-top: 4px; }
.day-list button:hover { background: #493640; }
.day-list [aria-current] { background: #543e4a; }
.index :focus-visible { outline-color: #e6c4ce; outline-offset: -3px; }
.sheet { padding: 0 clamp(18px, 3vw, 42px) 28px; min-width: 0; }
.tools { justify-content: space-between; flex-wrap: wrap; gap: 5px 16px; padding: 13px 0; border-bottom: 1px solid var(--rule); }
.search { flex: 1 1 200px; display: flex; align-items: center; gap: 9px; color: var(--muted); }
.search input { width: 100%; min-width: 0; padding: 8px 0; font: inherit; font-size: .84rem; color: var(--ink); border: 0; background: transparent; }
.search input::placeholder { color: var(--muted); }
.select-wrap { position: relative; display: inline-flex; min-width: 0; }
.select-wrap svg { position: absolute; right: 3px; top: 50%; transform: translateY(-50%); pointer-events: none; }
.select-wrap select {
  width: 100%; appearance: none; cursor: pointer; padding: 7px 22px 7px 3px; font: 600 .82rem/1.5 var(--font-sans);
  color: var(--wine); border: 0; border-bottom: 1px solid #bfa5af; background: transparent; border-radius: 0;
}
.tools .select-wrap { max-width: 100%; color: var(--wine); }
.mobile-days { display: none; }
.date-head { gap: 17px; padding: 23px 0 19px; border-bottom: 1px solid var(--rule); }
.date-number { font-size: clamp(3.8rem, 6vw, 5.2rem); line-height: .96; color: var(--wine); }
.date-head h2 { font-size: clamp(1.45rem, 2.5vw, 2.25rem); }
.date-head h2::first-letter, .date-head p::first-letter { text-transform: uppercase; }
.date-head p { color: var(--muted); font-size: .82rem; margin-top: 4px; }
.records { list-style: none; }
.records li { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 14px; padding: 19px 0; border-bottom: 1px solid var(--rule); }
.records li:last-child { border-bottom: 0; }
.records time { font-variant-numeric: tabular-nums; font-size: .88rem; color: var(--muted); }
.record-body { overflow-wrap: anywhere; }
.record-meta { gap: 8px 12px; flex-wrap: wrap; font-size: .8rem; color: var(--muted); }
.kind { display: inline-flex; align-items: center; gap: 5px; color: var(--wine); font-weight: 650; }
.observation { max-width: 70ch; margin: 7px 0; font-size: .97rem; line-height: 1.62; white-space: pre-wrap; }
.byline, .record-body small, .writer footer span { color: var(--muted); font-size: .79rem; }
.empty { padding: 28px 0 18px; }
.empty h3 { font-size: 1.7rem; }
.empty .text-action { margin-top: 14px; }
.text-action { color: var(--wine); font: 600 .84rem/1.5 var(--font-sans); text-decoration: underline; text-underline-offset: 4px; }
.writer { display: grid; gap: 16px; margin-bottom: 18px; padding: 20px clamp(16px, 2vw, 28px); border-radius: 12px; background: #efe8de; }
.writer h2 { font-size: 2rem; }
.writer header button { display: grid; place-items: center; min-width: 36px; min-height: 36px; color: var(--muted); }
.fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.field { display: grid; gap: 6px; min-width: 0; }
.writer label { display: grid; gap: 6px; font-size: .82rem; font-weight: 600; }
.writer select, .writer textarea { width: 100%; padding: 9px 12px; font: 400 .9rem/1.5 var(--font-sans); background: var(--paper); color: var(--ink); border: 1px solid #bcaea5; border-radius: 6px; }
.writer select { padding-right: 28px; }
.writer .select-wrap svg { right: 10px; }
.writer textarea { min-height: 80px; resize: vertical; }
.writer footer, .writer footer div { flex-wrap: wrap; gap: 8px; }
.notice, .confirmation, .writer [role=alert] { padding-block: 12px; font-size: .85rem; }
[role=alert] { color: #852d40; }
.confirmation { color: var(--wine); }
@media (max-width: 820px) {
  .notebook { grid-template-columns: minmax(0, 1fr); }
  .index { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px 12px; padding: 12px 16px; }
  .index-title { gap: 7px; margin: 0; }
  .index h2 { font-size: 1.5rem; }
  .index-empty { padding: 0; border: 0; }
  .day-list { display: none; }
  .mobile-days { display: inline-flex; max-width: 100%; }
  .mobile-days select { color: #fff6ef; border-color: #a58c98; }
  .mobile-days option { background: #32232d; }
}
@media (max-width: 520px) {
  .page-head { align-items: flex-start; margin-bottom: 14px; }
  .sheet { padding: 0 14px 14px; }
  .tools { padding: 8px 0; }
  .tools .search { flex-basis: 100%; }
  .date-head { gap: 11px; padding-block: 17px; }
  .records li { gap: 8px; grid-template-columns: 42px minmax(0, 1fr); }
  .records time { font-size: .78rem; }
  .fields { grid-template-columns: minmax(0, 1fr); }
}
</style>
