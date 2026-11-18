<script setup>
import { computed, ref, watch } from 'vue'
import api from '../services/api'

const props = defineProps({ processId: { type: Number, required: true }, alertId: Number })
const emit = defineEmits(['changed'])
const rows = ref([]), total = ref(0), offset = ref(0), context = ref(null)
const interventions = ref([]), interventionTotal = ref(0), linkingBusy = ref(false), linkingError = ref('')
const interventionStates = { propuesta: 'Propuesta', ejecutada: 'Ejecutada', en_seguimiento: 'En seguimiento', cerrada: 'Cerrada', cancelada: 'Cancelada' }
const busy = ref(false), error = ref(''), message = ref(''), annulling = ref(null), reason = ref('')
const localDate = value => {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
const blank = () => ({ variable: 'brix_aparente', valor: '', metodo: 'refractometro', instrumento: '', evidencia: '', observado_en: localDate(Date.now()), intervencion_id: null })
const form = ref(blank()), size = 10
const definition = computed(() => context.value?.catalogo[form.value.variable])
const date = value => new Date(value).toLocaleString('es-CL')
const methods = { termometro: 'Termómetro', refractometro: 'Refractómetro', densimetro_brix: 'Densímetro con escala Brix', densimetro: 'Densímetro', phmetro: 'Medidor de pH' }
const pending = new Map()
let generation = 0
let linkGeneration = 0
const detail = err => typeof err.response?.data?.detail === 'string' ? err.response.data.detail : (err.message || 'No se pudo guardar o consultar. Revisa los campos y reintenta.')

async function load() {
  const token = ++generation
  busy.value = true; error.value = ''; rows.value = []; total.value = 0; context.value = null
  try {
    const [list, metadata] = await Promise.all([
      api.get('/api/mediciones-manuales', { params: { fermentacion_id: props.processId, alerta_id: props.alertId, limit: size, offset: offset.value } }),
      api.get(`/api/mediciones-manuales/contexto/${props.processId}`)
    ])
    if (token !== generation) return
    rows.value = list.data.items; total.value = list.data.total; context.value = metadata.data
  } catch (err) { if (token === generation) error.value = detail(err) }
  finally { if (token === generation) busy.value = false }
}
watch(() => [props.processId, props.alertId], () => {
  offset.value = 0; annulling.value = null; reason.value = ''; message.value = ''; form.value = blank(); pending.clear(); load()
  loadInterventions(true)
}, { immediate: true })

async function loadInterventions(reset = false) {
  const token = ++linkGeneration
  if (reset) { interventions.value = []; interventionTotal.value = 0; form.value.intervencion_id = null }
  linkingBusy.value = true; linkingError.value = ''
  try {
    const result = await api.get(`/api/mediciones-manuales/intervenciones/${props.processId}`, {
      params: { alerta_id: props.alertId, limit: 50, offset: interventions.value.length }
    })
    if (token !== linkGeneration) return
    interventions.value = [...new Map([...interventions.value, ...result.data.items].map(row => [row.id, row])).values()]
    interventionTotal.value = result.data.total
  } catch (err) { if (token === linkGeneration) linkingError.value = detail(err) }
  finally { if (token === linkGeneration) linkingBusy.value = false }
}

async function save(path, payload, reset) {
  const token = generation, signature = JSON.stringify([path, payload])
  if (!pending.has(signature)) pending.set(signature, crypto.randomUUID())
  busy.value = true; error.value = ''; message.value = ''
  try {
    await api.post(path, { ...payload, request_id: pending.get(signature) })
    if (token !== generation) return
    pending.delete(signature); reset(); message.value = 'Registro guardado.'; emit('changed'); await load()
  } catch (err) { if (token === generation) error.value = detail(err) }
  finally { if (token === generation) busy.value = false }
}
function record() {
  const observed = new Date(form.value.observado_en)
  if (!Number.isFinite(observed.getTime()) || form.value.valor === '' || !definition.value) {
    error.value = 'Introduce una fecha y un valor válidos.'; return
  }
  return save('/api/mediciones-manuales', {
    ...form.value, valor: Number(form.value.valor), observado_en: observed.toISOString(), unidad: definition.value.unidad,
    fermentacion_id: props.processId, alerta_id: props.alertId || null
  }, () => { form.value = blank(); offset.value = 0 })
}
function annul() {
  return save(`/api/mediciones-manuales/${annulling.value}/anular`, { motivo: reason.value }, () => { annulling.value = null; reason.value = '' })
}
function page(delta) { offset.value += delta; annulling.value = null; load() }
</script>

<template>
  <section class="manual-measurements" aria-label="Mediciones manuales">
    <h3>Mediciones manuales</h3>
    <p>Registra una observación de contraste con su método y evidencia. Se conserva separada de la curva automática y no cambia el estado de las alertas.</p>
    <button type="button" :disabled="busy" @click="annulling = null; load()">Actualizar mediciones</button>
    <p v-if="busy" role="status">Procesando mediciones…</p>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="context && !context.puede_operar">Acceso de consulta para esta bodega.</p>
    <p v-if="context?.fin">Proceso cerrado: solo se admiten observaciones realizadas hasta {{ date(context.fin) }}.</p>
    <details v-if="context?.puede_operar">
      <summary>Registrar medición manual</summary>
      <form @submit.prevent="record">
        <label>Variable<select v-model="form.variable" @change="form.metodo = definition.metodos[0]; form.valor = ''"><option v-for="(entry, key) in context.catalogo" :key="key" :value="key">{{ entry.nombre }}</option></select></label>
        <label>Valor ({{ definition?.unidad }})<input v-model="form.valor" type="number" step="any" :min="definition?.minimo" :max="definition?.maximo" required /></label>
        <label>Método<select v-model="form.metodo"><option v-for="method in definition?.metodos" :key="method" :value="method">{{ methods[method] }}</option></select></label>
        <p v-if="form.variable === 'brix_aparente'">Brix aparente no equivale a azúcar residual. Conserva el método: no se aplica corrección por alcohol ni conversión automática.</p>
        <label>Instrumento o referencia de equipo<input v-model.trim="form.instrumento" required minlength="3" maxlength="200" placeholder="Ej.: refractómetro REF-01" /></label>
        <label>Fecha y hora de la observación (hora local)<input v-model="form.observado_en" type="datetime-local" required :min="localDate(context.inicio)" :max="localDate(context.fin || Date.now())" /></label>
        <label>Intervención vinculada (opcional)
          <select v-model="form.intervencion_id" :disabled="busy || linkingBusy">
            <option :value="null">Sin intervención vinculada</option>
            <option v-for="item in interventions" :key="item.id" :value="item.id">#{{ item.id }} · {{ interventionStates[item.estado] || item.estado }} · {{ item.accion }}</option>
          </select>
        </label>
        <p>El vínculo documenta la evidencia; no declara ejecución, mejoría ni cierre de la intervención.</p>
        <p v-if="linkingBusy" role="status">Consultando intervenciones…</p>
        <p v-if="linkingError" role="alert">{{ linkingError }} Puedes reintentar o registrar sin vínculo.</p>
        <p v-if="!linkingBusy && !linkingError && !interventionTotal">No hay intervenciones compatibles con este proceso{{ alertId ? ' e incidente' : '' }}.</p>
        <div>
          <button type="button" :disabled="busy || linkingBusy" @click="loadInterventions(true)">Actualizar intervenciones</button>
          <button v-if="interventions.length < interventionTotal" type="button" :disabled="busy || linkingBusy" @click="loadInterventions()">Cargar más ({{ interventions.length }} de {{ interventionTotal }})</button>
          <button v-else-if="linkingError" type="button" :disabled="busy || linkingBusy" @click="loadInterventions()">Reintentar consulta</button>
        </div>
        <label>Evidencia y condiciones de la muestra<textarea v-model.trim="form.evidencia" required minlength="5" maxlength="2000" placeholder="Identificación de muestra, condiciones, comprobaciones o referencia al registro de laboratorio" /></label>
        <button :disabled="busy">Guardar medición</button>
      </form>
    </details>
    <p v-if="context && !total">Sin mediciones manuales registradas{{ alertId ? ' para este incidente' : '' }}.</p>
    <article v-for="row in rows" :key="row.id" :class="{ annulled: row.anulacion }">
      <h4>#{{ row.id }} · {{ context?.catalogo[row.variable]?.nombre || row.variable }}: {{ row.valor }} {{ row.unidad }} · {{ row.anulacion ? 'Anulada' : 'Registrada' }}</h4>
      <p>{{ methods[row.metodo] || row.metodo }} · {{ row.instrumento }}</p>
      <p>Observada: {{ date(row.observado_en) }} · Registrada: {{ date(row.registrado_en) }} · Autor: {{ row.autor }}</p>
      <p>{{ row.evidencia }}</p>
      <p v-if="row.alerta_id">Vinculada al incidente #{{ row.alerta_id }}</p>
      <p v-if="row.intervencion_id">Vinculada a la intervención #{{ row.intervencion_id }}</p>
      <p v-if="row.anulacion">Anulada por {{ row.anulacion.autor }} · {{ date(row.anulacion.registrado_en) }}<br />Motivo: {{ row.anulacion.motivo }}</p>
      <button v-if="context?.puede_operar && !row.anulacion" type="button" :disabled="busy" @click="annulling = row.id; reason = ''">Anular con motivo</button>
      <form v-if="annulling === row.id" @submit.prevent="annul">
        <p>El valor original y su autor se conservarán. Si corresponde, registra una nueva medición con los datos correctos.</p>
        <label>Motivo de anulación<textarea v-model.trim="reason" required minlength="5" maxlength="2000" /></label>
        <button :disabled="busy">Guardar anulación</button>
        <button type="button" :disabled="busy" @click="annulling = null">Volver</button>
      </form>
    </article>
    <nav v-if="total > size" aria-label="Páginas de mediciones manuales">
      <button :disabled="busy || !offset" @click="page(-size)">Anterior</button>
      <span>{{ offset + 1 }}–{{ Math.min(offset + size, total) }} de {{ total }}</span>
      <button :disabled="busy || offset + size >= total" @click="page(size)">Siguiente</button>
    </nav>
  </section>
</template>

<style scoped>
.manual-measurements { background: #fff; color: #342832; border: 1px solid #d8c8ce; padding: 20px; border-radius: 12px; margin: 20px 0; }
h3, h4 { margin: 0 0 12px; } p, summary { font-size: 14px; line-height: 1.6; overflow-wrap: anywhere; } p { white-space: pre-wrap; }
article, details { border-top: 1px solid #d8c8ce; padding: 16px 0; } .annulled { border-left: 4px solid #8a7b85; padding-left: 12px; }
form { display: grid; gap: 12px; margin-top: 12px; } label { display: grid; gap: 5px; font-size: 14px; }
input, select, textarea { width: 100%; box-sizing: border-box; min-width: 0; padding: 10px; border: 1px solid #8a7b85; border-radius: 6px; background: white; color: #342832; font: inherit; } textarea { min-height: 80px; resize: vertical; }
button { background: #66324c; color: white; border: 0; border-radius: 6px; padding: 9px 14px; margin: 4px 8px 4px 0; cursor: pointer; } button:disabled { opacity: .5; cursor: default; }
:focus-visible { outline: 3px solid #2185a3; outline-offset: 3px; } nav { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; } [role=alert] { color: #9a193f; }
</style>
