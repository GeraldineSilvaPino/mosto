<script setup>
import { computed, ref, watch } from 'vue'
import api from '../services/api'
import { Plus, RefreshCw } from 'lucide-vue-next'

const props = defineProps({ processId: { type: Number, required: true }, alertId: Number, inRegister: Boolean })
const emit = defineEmits(['changed'])
const rows = ref([]), total = ref(0), offset = ref(0), busy = ref(false), error = ref(''), message = ref('')
const context = ref(null), histories = ref({}), selected = ref(null)
const proposal = ref({ tipo: 'contraste_manual', accion: '', motivo: '', responsable_id: null })
const followup = ref({ estado: 'ejecutada', descripcion: '', respuesta: 'no_evaluable' })
const size = 10
let generation = 0
const pending = new Map()
const labels = { propuesta: 'Propuesta', ejecutada: 'Ejecución registrada', en_seguimiento: 'En seguimiento', cerrada: 'Cerrada', cancelada: 'Cancelada' }
const responses = { sin_cambio: 'Sin cambio declarado', mejora_declarada: 'Mejora declarada', empeora_declarado: 'Empeoramiento declarado', no_evaluable: 'No evaluable' }
const actions = { comprobar_sensor: 'Comprobar sensor', contraste_manual: 'Contraste manual', ajuste_termico: 'Ajuste térmico', otra: 'Otra acción' }
const choices = row => row.estado === 'propuesta' ? (context.value?.proceso_activo ? ['ejecutada', 'cancelada'] : ['cancelada']) : ['en_seguimiento', 'cerrada']
const needsResponse = computed(() => ['en_seguimiento', 'cerrada'].includes(followup.value.estado))
const date = value => new Date(value).toLocaleString('es-CL')
const person = id => context.value?.responsables.find(user => user.id === id)?.nombre || `Usuario #${id}`
const detail = err => typeof err.response?.data?.detail === 'string' ? err.response.data.detail : (err.message || 'No se pudo completar la operación. Revisa los datos y reintenta.')

async function load() {
  const token = ++generation
  busy.value = true; error.value = ''; rows.value = []; context.value = null; histories.value = {}
  try {
    const [list, metadata] = await Promise.all([
      api.get('/api/intervenciones', { params: { fermentacion_id: props.processId, alerta_id: props.alertId, limit: size, offset: offset.value } }),
      api.get(`/api/intervenciones/contexto/${props.processId}`)
    ])
    if (token !== generation) return
    rows.value = list.data.items; total.value = list.data.total; context.value = metadata.data
    if (!proposal.value.responsable_id) proposal.value.responsable_id = metadata.data.usuario_id
  } catch (err) { if (token === generation) error.value = detail(err) }
  finally { if (token === generation) busy.value = false }
}
watch(() => [props.processId, props.alertId], () => {
  offset.value = 0; selected.value = null; message.value = ''; pending.clear()
  proposal.value = { tipo: 'contraste_manual', accion: '', motivo: '', responsable_id: null }
  load()
}, { immediate: true })

async function save(path, payload, reset) {
  const token = generation
  const signature = JSON.stringify([path, payload])
  if (!pending.has(signature)) pending.set(signature, crypto.randomUUID())
  busy.value = true; error.value = ''; message.value = ''
  try {
    await api.post(path, { ...payload, request_id: pending.get(signature) })
    if (token !== generation) return
    pending.delete(signature); reset(); message.value = 'Registro guardado.'; emit('changed')
    await load()
  } catch (err) { if (token === generation) error.value = detail(err) }
  finally { if (token === generation) busy.value = false }
}
function propose() {
  return save('/api/intervenciones', { ...proposal.value, fermentacion_id: props.processId, alerta_id: props.alertId || null }, () => {
    proposal.value.accion = ''; proposal.value.motivo = ''; offset.value = 0
  })
}
function select(row) {
  selected.value = row
  followup.value = { estado: choices(row)[0], descripcion: '', respuesta: 'no_evaluable' }
}
function record() {
  return save(`/api/intervenciones/${selected.value.id}/eventos`, {
    ...followup.value, respuesta: needsResponse.value ? followup.value.respuesta : null,
    expected_revision: selected.value.revision
  }, () => { selected.value = null })
}
async function history(row, page = 0) {
  const token = generation
  busy.value = true; error.value = ''
  try {
    const result = await api.get(`/api/intervenciones/${row.id}/eventos`, { params: { offset: page, limit: size } })
    if (token === generation) histories.value[row.id] = { ...result.data, offset: page }
  } catch (err) { if (token === generation) error.value = detail(err) }
  finally { if (token === generation) busy.value = false }
}
function page(delta) { offset.value += delta; selected.value = null; load() }
</script>

<template>
  <section class="interventions" aria-label="Intervenciones y respuesta declarada">
    <header v-if="inRegister" class="register-toolbar">
      <h3>Intervenciones y seguimiento <span v-if="context">{{ total }}</span></h3>
      <button type="button" :disabled="busy" @click="selected = null; load()"><RefreshCw :size="14" />Actualizar</button>
    </header>
    <component v-else :is="alertId ? 'h4' : 'h3'" class="panel-title">Intervenciones y seguimiento</component>
    <p>Registra la acción humana y su respuesta declarada. Cerrar una intervención no resuelve la alerta ni acredita recuperación de la señal. No se envían órdenes al equipo.</p>
    <button v-if="!inRegister" type="button" class="panel-refresh" :disabled="busy" @click="selected = null; load()">Actualizar</button>
    <p v-if="busy" role="status">Procesando…</p>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="context && !context.puede_operar">Acceso de consulta para esta bodega.</p>
    <p v-if="context && !context.proceso_activo">Proceso finalizado: puedes completar el seguimiento o cancelar propuestas pendientes.</p>
    <details v-if="context?.puede_operar && context.proceso_activo">
      <summary><Plus v-if="inRegister" :size="15" aria-hidden="true" />Proponer una intervención</summary>
      <form @submit.prevent="propose">
        <label>Tipo de acción<select v-model="proposal.tipo"><option v-for="(label, key) in actions" :key="key" :value="key">{{ label }}</option></select></label>
        <label>Acción concreta<textarea v-model.trim="proposal.accion" required minlength="5" maxlength="2000" /></label>
        <label>Motivo y evidencia disponible<textarea v-model.trim="proposal.motivo" required minlength="5" maxlength="2000" /></label>
        <label>Responsable<select v-model="proposal.responsable_id" required><option v-for="user in context.responsables" :key="user.id" :value="user.id">{{ user.nombre }}</option></select></label>
        <button :disabled="busy">Guardar propuesta</button>
      </form>
    </details>
    <p v-if="context && !total" class="empty-register">Sin intervenciones registradas.</p>
    <article v-for="row in rows" :key="row.id">
      <header v-if="inRegister" class="reading-head">
        <h4>{{ actions[row.tipo] }} <small>#{{ row.id }}</small></h4>
        <span>{{ labels[row.estado] }}</span>
      </header>
      <h4 v-else>#{{ row.id }} · {{ labels[row.estado] }} · {{ actions[row.tipo] }}</h4>
      <p>{{ row.accion }}</p><p>Motivo: {{ row.motivo }}</p>
      <p>Responsable: {{ person(row.responsable_id) }} · Propuesta por {{ person(row.usuario_id) }} · {{ date(row.registrado_en) }} · Revisión {{ row.revision }}</p>
      <button type="button" :disabled="busy" @click="history(row)">Ver historial</button>
      <button v-if="context?.puede_operar && !['cerrada', 'cancelada'].includes(row.estado)" type="button" :disabled="busy" @click="select(row)">Registrar avance</button>
      <form v-if="selected?.id === row.id" @submit.prevent="record">
        <label>Nuevo estado<select v-model="followup.estado"><option v-for="state in choices(row)" :key="state" :value="state">{{ labels[state] }}</option></select></label>
        <label>Descripción y evidencia<textarea v-model.trim="followup.descripcion" required minlength="5" maxlength="2000" /></label>
        <label v-if="needsResponse">Respuesta declarada<select v-model="followup.respuesta"><option v-for="(label, key) in responses" :key="key" :value="key">{{ label }}</option></select></label>
        <button :disabled="busy">Guardar avance</button>
        <button type="button" :disabled="busy" @click="selected = null">Volver</button>
      </form>
      <div v-if="histories[row.id]">
        <ol><li v-for="event in histories[row.id].items" :key="event.id">
          <strong>{{ labels[event.estado] }}</strong> · {{ person(event.usuario_id) }} · Registrado: {{ date(event.registrado_en) }}
          <p>{{ event.descripcion }}</p><p v-if="event.respuesta">{{ responses[event.respuesta] }}</p>
        </li></ol>
        <p>{{ histories[row.id].total }} eventos · del más reciente al más antiguo</p>
        <button :disabled="busy || !histories[row.id].offset" @click="history(row, histories[row.id].offset - size)">Más recientes</button>
        <button :disabled="busy || histories[row.id].offset + size >= histories[row.id].total" @click="history(row, histories[row.id].offset + size)">Más antiguos</button>
      </div>
    </article>
    <nav v-if="total > size" aria-label="Páginas de intervenciones">
      <button :disabled="busy || offset === 0" @click="page(-size)">Anterior</button>
      <span>{{ offset + 1 }}–{{ Math.min(offset + size, total) }} de {{ total }}</span>
      <button :disabled="busy || offset + size >= total" @click="page(size)">Siguiente</button>
    </nav>
  </section>
</template>

<style scoped>
.interventions { background: #fff; border: 1px solid #d8c8ce; padding: 20px; border-radius: 12px; margin: 20px 0; color: #342832; }
h3, h4 { margin: 0 0 12px; } p, li, summary { font-size: 14px; line-height: 1.6; overflow-wrap: anywhere; } p { white-space: pre-wrap; }
article, details { border-top: 1px solid #d8c8ce; padding: 16px 0; } form { display: grid; gap: 12px; margin-top: 12px; }
label { display: grid; gap: 5px; font-size: 14px; } select, textarea { width: 100%; box-sizing: border-box; padding: 10px; border: 1px solid #8a7b85; border-radius: 6px; background: white; color: #342832; font: inherit; } textarea { min-height: 80px; resize: vertical; }
button { background: #66324c; color: white; border: 0; border-radius: 6px; padding: 9px 14px; margin: 4px 8px 4px 0; cursor: pointer; } button:disabled { opacity: .5; cursor: default; } :focus-visible { outline: 3px solid #2185a3; outline-offset: 3px; }
nav { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; } [role=alert] { color: #9a193f; }
</style>
