<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ChevronDown, ChevronRight, Cylinder, Pencil, Plus, RefreshCw, Thermometer, X } from 'lucide-vue-next'
import profileService from '../services/profileService'
import cubaService from '../services/cubaService'
import masterService from '../services/masterService'
import ProfileHistory from '../components/ProfileHistory.vue'

const profiles = ref([])
const selectedId = ref(null)
const selected = computed(() => profiles.value.find(item => item.id === selectedId.value))
const tanks = ref([])
const grapes = ref([])
const wineries = ref([])
const loading = ref(false)
const errors = ref({})
const message = ref('')
const historyKey = ref(0)
const linked = computed(() => tanks.value.filter(t => t.proceso_activo_id && t.perfil_activo_id === selectedId.value))
const fmt = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 })
const number = value => value == null ? '—' : fmt.format(value)
const fields = [
  { key: 'temp_min', label: 'Temperatura mínima (°C)', required: true },
  { key: 'temp_max', label: 'Temperatura máxima (°C)', required: true },
  { key: 'ph_min', label: 'pH mínimo', min: 0, max: 14 },
  { key: 'ph_max', label: 'pH máximo', min: 0, max: 14 },
  { key: 'brix_caida_min_dia', label: 'Descenso mínimo diario (°Bx/día)' }
]
// La escala abarca los límites críticos y la banda configurada que devuelve el servidor.
const thermalBand = computed(() => {
  if (!selected.value) return null
  const { crit_min: low, temp_min: from, temp_max: to, crit_max: high } = selected.value
  if (![low, from, to, high].every(Number.isFinite) || high <= low || from < low || to < from || to > high) return null
  return { left: (from-low)/(high-low)*100 + '%', width: (to-from)/(high-low)*100 + '%' }
})

async function load() {
  if (loading.value) return
  loading.value = true
  const results = await Promise.allSettled([
    profileService.listarPerfiles({ activo: true }), cubaService.listarCubas({ incluirPrediccion: false }),
    masterService.listarCepas(), masterService.listarBodegas()
  ])
  const nextErrors = {}
  const sources = [
    ['perfiles', profiles], ['cubas', tanks], ['cepas', grapes], ['bodegas', wineries]
  ]
  sources.forEach(([key, list], index) => {
    if (results[index].status === 'fulfilled') list.value = results[index].value
    else nextErrors[key] = true
  })
  errors.value = nextErrors
  if (!selected.value) selectedId.value = profiles.value[0]?.id ?? null
  historyKey.value++
  loading.value = false
}
onMounted(load)

const dialog = ref(null)
const mode = ref('')
const busy = ref(false)
const formError = ref('')
const draft = ref({})
const canCreate = computed(() => wineries.value.length > 0 && grapes.value.length > 0 && !errors.value.bodegas && !errors.value.cepas)
const dialogTitle = computed(() => ({ create: 'Nuevo perfil', edit: 'Editar umbrales', archive: 'Desactivar perfil' })[mode.value])

async function openForm(action) {
  if (busy.value || loading.value) return
  mode.value = action
  message.value = formError.value = ''
  draft.value = action === 'create' ? {
    nomb_perfil: '', cepa_id: grapes.value[0]?.id, bodega_id: selected.value?.bodega_id || wineries.value[0]?.id,
    temp_min: 18, temp_max: 26, ph_min: 3.2, ph_max: 3.8, brix_caida_min_dia: 1.5
  } : { ...selected.value }
  await nextTick()
  dialog.value.showModal()
}
function closeForm() {
  if (busy.value) return
  dialog.value?.close()
  mode.value = ''
}
async function save() {
  if (busy.value) return
  const p = draft.value
  const action = mode.value
  formError.value = ''
  const values = {}
  if (action !== 'archive') {
    for (const { key } of fields) values[key] = p[key] === '' || p[key] == null ? null : Number(p[key])
    if (values.temp_min > values.temp_max) {
      formError.value = 'La temperatura mínima debe ser igual o menor que la máxima.'
      return
    }
    if (values.ph_min != null && values.ph_max != null && values.ph_min > values.ph_max) {
      formError.value = 'El pH mínimo debe ser igual o menor que el máximo.'
      return
    }
    if (action === 'create' && p.nomb_perfil.trim().length < 2) {
      formError.value = 'Escribe un nombre de al menos dos caracteres.'
      return
    }
  }
  busy.value = true
  try {
    if (action === 'archive') {
      await profileService.desactivarPerfil(p.id)
      profiles.value = profiles.value.filter(item => item.id !== p.id)
      selectedId.value = profiles.value[0]?.id ?? null
      message.value = 'Perfil desactivado.'
    } else if (action === 'create') {
      const saved = await profileService.crearPerfil({ ...values, nomb_perfil: p.nomb_perfil.trim(), cepa_id: p.cepa_id, bodega_id: p.bodega_id, activo: true })
      profiles.value.push(saved)
      selectedId.value = saved.id
      message.value = 'Perfil creado.'
    } else {
      const saved = await profileService.actualizarPerfil(p.id, { ...values, expected_revision: p.revision })
      profiles.value = profiles.value.map(item => item.id === saved.id ? saved : item)
      message.value = 'Umbrales guardados.'
    }
    busy.value = false
    closeForm()
  } catch (err) {
    formError.value = err.message || 'No se pudo guardar el cambio. Inténtalo de nuevo.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="thresholds">
    <header class="page-head">
      <h1>Perfil y umbrales</h1>
      <div class="actions">
        <button class="button" :disabled="loading" @click="load"><RefreshCw :size="15"/>{{ loading ? 'Actualizando…' : 'Actualizar' }}</button>
        <button class="button primary" :disabled="loading || !canCreate" @click="openForm('create')"><Plus :size="16"/>Nuevo perfil</button>
      </div>
    </header>
    <p v-if="Object.keys(errors).length" class="notice error" role="alert">No se pudo actualizar la consulta de {{ Object.keys(errors).join(', ') }}. <button class="text-button" @click="load">Reintentar</button></p>
    <p v-else-if="!loading && !canCreate" class="notice">Para crear un perfil se necesitan una bodega y una cepa disponibles.</p>
    <p v-if="message" class="notice" role="status">{{ message }}</p>
    <template v-if="selected">
      <div class="profile-line">
        <div class="picker">
          <label for="active-profile">Perfil activo</label>
          <span><select id="active-profile" v-model="selectedId" @change="message = ''">
            <option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.nomb_perfil }}</option>
          </select><ChevronDown :size="16" aria-hidden="true"/></span>
        </div>
        <p>{{ [selected.cepa_nombre, selected.bodega_nombre].filter(Boolean).join(' · ') }}</p>
      </div>
      <div class="dossier">
        <section class="limits" aria-labelledby="limits-title">
          <header class="section-head"><h2 id="limits-title">Límites vigentes</h2><span>Versión {{ selected.revision }}</span></header>
          <div class="temperature">
            <span><Thermometer :size="16" aria-hidden="true"/>Banda de temperatura</span>
            <strong>{{ number(selected.temp_min) }} – {{ number(selected.temp_max) }} <small>°C</small></strong>
          </div>
          <div v-if="thermalBand" class="ruler" aria-hidden="true"><i :style="thermalBand"></i></div>
          <div class="ends">
            <span>Mín. crítico <b>{{ number(selected.crit_min) }} °C</b></span>
            <span>Máx. crítico <b>{{ number(selected.crit_max) }} °C</b></span>
          </div>
          <dl class="secondary">
            <div><dt>Rango de pH</dt><dd>{{ number(selected.ph_min) }} – {{ number(selected.ph_max) }}</dd></div>
            <div><dt>Descenso mínimo diario</dt><dd>{{ number(selected.brix_caida_min_dia) }} <small>°Bx/día</small></dd></div>
          </dl>
          <button class="edit" :disabled="loading" @click="openForm('edit')"><Pencil :size="14"/>Editar umbrales</button>
        </section>
        <section class="tanks" aria-labelledby="tank-title">
          <header class="section-head"><h2 id="tank-title">Cubas con este perfil</h2><Cylinder :size="19" aria-hidden="true"/></header>
          <p v-if="errors.cubas">Consulta de cubas pendiente de actualización.</p>
          <ul v-if="linked.length">
            <li v-for="tank in linked" :key="tank.id">
              <RouterLink :to="'/cubas/' + tank.id">
                <span><b>{{ tank.nombre || tank.codigo_cuba }}</b><small>{{ tank.lote || ('Proceso #' + tank.proceso_activo_id) }}</small></span>
                <span class="reading">{{ tank.ultima_temperatura == null ? 'Sin lectura' : number(tank.ultima_temperatura) + ' °C' }}</span>
                <ChevronRight :size="16" aria-hidden="true"/>
              </RouterLink>
            </li>
          </ul>
          <p v-else-if="!errors.cubas">Ninguna fermentación activa usa este perfil.</p>
        </section>
      </div>
      <ProfileHistory :key="historyKey" :profile-id="selected.id" :revision="selected.revision"/>
      <button class="text-button archive" :disabled="loading" @click="openForm('archive')">Desactivar este perfil</button>
    </template>
    <p v-else class="notice">{{ loading ? 'Consultando perfiles…' : errors.perfiles ? 'Catálogo de perfiles no disponible.' : 'Todavía no hay perfiles activos.' }}</p>
    <dialog ref="dialog" aria-labelledby="form-title" @cancel.prevent="closeForm" @click.self="closeForm">
      <div class="dialog-content">
        <header class="section-head"><h2 id="form-title">{{ dialogTitle }}</h2><button type="button" aria-label="Cerrar formulario" class="close" :disabled="busy" @click="closeForm"><X :size="18"/></button></header>
        <form v-if="mode" @submit.prevent="save">
          <p v-if="mode === 'archive'">¿Desactivar <b>{{ draft.nomb_perfil }}</b>? El perfil dejará de estar disponible para nuevas fermentaciones.</p>
          <template v-else>
            <div v-if="mode === 'create'" class="field-grid">
              <label class="wide">Nombre del perfil<input v-model.trim="draft.nomb_perfil" required minlength="2" maxlength="100" :disabled="busy"/></label>
              <div class="field"><label for="profile-variety">Cepa</label><select id="profile-variety" v-model="draft.cepa_id" required :disabled="busy"><option v-for="g in grapes" :key="g.id" :value="g.id">{{ g.name }}</option></select></div>
              <div class="field"><label for="profile-winery">Bodega</label><select id="profile-winery" v-model="draft.bodega_id" required :disabled="busy"><option v-for="w in wineries" :key="w.id" :value="w.id">{{ w.nombre }}</option></select></div>
            </div>
            <p v-else><b>{{ draft.nomb_perfil }}</b> · Versión {{ draft.revision }}</p>
            <div class="field-grid">
              <label v-for="f in fields" :key="f.key" :class="{wide: f.key === 'brix_caida_min_dia'}">
                {{ f.label }}<input v-model.number="draft[f.key]" type="number" step="0.01" :min="f.min" :max="f.max" :required="f.required || (mode === 'edit' && selected?.[f.key] != null)" :disabled="busy"/>
              </label>
            </div>
            <p v-if="mode === 'edit'" class="hint">Guardar cambios crea una nueva versión. Los procesos que fijaron sus parámetros al inicio conservan esa configuración.</p>
          </template>
          <p v-if="formError" role="alert" class="error">{{ formError }}</p>
          <footer class="actions"><button type="button" class="button" :disabled="busy" @click="closeForm">Cancelar</button><button class="button primary" :disabled="busy">{{ busy ? 'Guardando…' : mode === 'archive' ? 'Confirmar desactivación' : mode === 'edit' ? 'Guardar cambios' : 'Crear perfil' }}</button></footer>
        </form>
      </div>
    </dialog>
  </div>
</template>

<style scoped>
.thresholds {
  --ink: #30232a; --muted: #695d61; --wine: #763c51; --rule: #dbd2ca; --paper: #fffdf9;
  --display: 'Instrument Serif', Georgia, serif;
  color: var(--ink); max-width: 1540px; margin-inline: auto;
}
h1, h2, .temperature strong, .secondary dd { font: 400 2rem/1.1 var(--display); letter-spacing: -.02em; }
h1 { font-size: clamp(2.5rem, 4vw, 3.25rem); }
.page-head, .actions, .section-head, .profile-line, .picker, .button, .edit, .temperature > span, .ends { display: flex; align-items: center; gap: 9px; }
.page-head, .section-head, .ends { justify-content: space-between; }
.page-head, .actions, .profile-line, .picker, .ends { flex-wrap: wrap; }
.page-head { margin-bottom: 18px; }
.button, .edit { min-height: 38px; padding: 8px 13px; border: 1px solid var(--rule); border-radius: 7px; font: 600 .83rem/1.4 var(--font-sans); }
.button { background: var(--paper); color: var(--ink); }
.button:hover:enabled { border-color: var(--wine); }
.primary { color: var(--paper); background: var(--wine); border-color: var(--wine); }
.primary:hover:enabled { background: #603044; }
button:disabled { opacity: .55; cursor: default; }
.thresholds :focus-visible { outline: 2px solid var(--wine); outline-offset: 3px; }
.profile-line { margin-bottom: 14px; justify-content: space-between; border-top: 1px solid var(--rule); padding-top: 13px; }
.picker { min-width: 0; max-width: 100%; color: var(--muted); font-size: .84rem; }
.picker > span { position: relative; display: inline-flex; max-width: 100%; }
.picker svg { position: absolute; right: 1px; top: 50%; transform: translateY(-50%); pointer-events: none; color: var(--wine); }
.picker select { appearance: none; min-width: 0; max-width: 100%; cursor: pointer; padding: 7px 22px 7px 1px; color: var(--wine); border: 0; border-bottom: 1px solid #ad929f; border-radius: 0; background: transparent; font: 650 .93rem var(--font-sans); }
.profile-line p, .notice, .tanks p, .hint { font-size: .84rem; color: var(--muted); }
.dossier { display: grid; grid-template-columns: minmax(0,1.1fr) minmax(0,1fr); background: #efe8de; border-radius: 14px; overflow: hidden; }
.limits, .tanks { padding: clamp(18px,2vw,30px); }
.limits { background: #32232d; color: #fff6ee; }
.section-head h2 { font-size: clamp(1.65rem,2.8vw,2.1rem); }
.section-head > span { font-size: .79rem; color: #e1cbd3; }
.temperature { margin: 20px 0 12px; }
.temperature > span, .secondary dt { font-size: .81rem; color: #e1cbd3; }
.temperature strong { display: block; margin-top: 3px; font-size: clamp(2.75rem,5vw,4.5rem); }
.temperature small { font-size: .45em; }
.ruler { height: 7px; position: relative; background: #765b69; border-radius: 2px; }
.ruler i { position: absolute; top: -2px; height: 11px; min-width: 2px; background: #efb6ad; border-inline: 2px solid #fff3df; }
.ends { margin-top: 9px; color: #e1cbd3; font-size: .73rem; }
.ends b { color: #fff3e9; font-weight: 600; }
.secondary { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 9px; margin: 19px 0 14px; padding-top: 12px; border-top: 1px solid #69515e; }
.secondary dd { margin: 4px 0 0; font-size: 1.9rem; }
.secondary small { font: 500 .85rem var(--font-sans); }
.edit { color: #fff6ee; background: transparent; border-color: #927382; }
.edit:hover { background: #513946; }
.limits :focus-visible { outline-color: #f2c6d1; }
.tanks ul { list-style: none; margin-top: 12px; }
.tanks li { border-top: 1px solid #d4c7bd; }
.tanks a { display: grid; align-items: center; grid-template-columns: minmax(0,1fr) auto 16px; gap: 12px; padding: 10px 2px; color: var(--ink); text-decoration: none; }
.tanks a:hover { background: #e7ded4; }
.tanks b, .reading { font-size: .85rem; }
.tanks small { display: block; margin-top: 2px; font-size: .76rem; color: var(--muted); }
.reading { font-variant-numeric: tabular-nums; }
.tanks svg, .text-button { color: var(--wine); }
.tanks p { margin-top: 14px; }
.text-button { font-size: .81rem; text-decoration: underline; text-underline-offset: 3px; }
.archive { margin-top: 12px; }
.notice { padding-block: 9px; }
.error { color: #882f40; }
dialog { margin: auto; padding: 0; width: min(490px,calc(100% - 24px)); max-height: 90dvh; overflow: auto; background: var(--paper); color: var(--ink); border: 0; border-radius: 12px; }
dialog::backdrop { background: rgba(40,25,34,.55); }
.dialog-content > header { padding: 16px 20px; background: #efe8de; }
.close { display: grid; place-items: center; width: 34px; height: 34px; color: var(--wine); }
form { display: grid; gap: 15px; padding: 18px 20px; }
form p { font-size: .85rem; line-height: 1.55; }
.field-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }
.field, form label { display: grid; gap: 5px; font-size: .82rem; font-weight: 600; }
.wide { grid-column: 1/-1; }
form input, form select { width: 100%; min-width: 0; box-sizing: border-box; padding: 9px; font: 400 .88rem/1.5 var(--font-sans); border: 1px solid #bbaea5; border-radius: 6px; background: var(--paper); color: var(--ink); }
form footer { justify-content: flex-end; border-top: 1px solid var(--rule); padding-top: 12px; }
@media(max-width:800px) {
  .dossier { grid-template-columns: minmax(0,1fr); }
  .limits, .tanks { padding: 16px; }
  .temperature { margin: 12px 0 8px; }
  .secondary { margin-block: 12px; padding-top: 8px; }
  .page-head { gap: 12px; }
}
@media(max-width:460px) {
  .field-grid { grid-template-columns: minmax(0,1fr); }
  .dialog-content > header, form { padding: 14px; }
}
</style>
