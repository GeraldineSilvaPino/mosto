<script setup>
import { ref, watch } from 'vue'
import api from '../services/api'

const props = defineProps({ processId: { type: Number, required: true } })
const emit = defineEmits(['changed'])
const context = ref(null), busy = ref(false), error = ref(''), message = ref(''), offset = ref(0)
const form = ref({ accion: 'ajustar', temp_min: '', temp_max: '', motivo: '' })
const size = 10, pending = new Map()
let generation = 0
const date = value => new Date(value).toLocaleString('es-CL')
const band = profile => profile?.temp_min != null && profile?.temp_max != null ? `${profile.temp_min}–${profile.temp_max} °C` : 'Sin banda completa'
const detail = err => typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'No se pudo completar la operación. Revisa los campos y reintenta.'
async function load(reset = false) {
  const token = ++generation
  busy.value = true; error.value = ''
  try {
    const { data } = await api.get(`/api/procesos/${props.processId}/ajustes-perfil`, { params: { limit: size, offset: offset.value } })
    if (token !== generation) return
    context.value = data
    if (reset) form.value = { accion: 'ajustar', temp_min: data.applied?.temp_min ?? '', temp_max: data.applied?.temp_max ?? '', motivo: '' }
  } catch (err) { if (token === generation) { error.value = detail(err); context.value = null } }
  finally { if (token === generation) busy.value = false }
}
watch(() => props.processId, () => {
  context.value = null; offset.value = 0; message.value = ''; pending.clear(); load(true)
}, { immediate: true })
async function approve() {
  const payload = { accion: form.value.accion, motivo: form.value.motivo, expected_revision: context.value.revision }
  if (payload.accion === 'ajustar') {
    const low = Number(form.value.temp_min), high = Number(form.value.temp_max)
    if (form.value.temp_min === '' || form.value.temp_max === '' || !Number.isFinite(low) || !Number.isFinite(high) || low >= high) {
      error.value = 'Introduce un mínimo menor que el máximo.'; return
    }
    Object.assign(payload, { temp_min: low, temp_max: high })
  }
  const path = `/api/procesos/${props.processId}/ajustes-perfil`, signature = JSON.stringify([path, payload]), token = generation
  if (!pending.has(signature)) pending.set(signature, crypto.randomUUID())
  busy.value = true; error.value = ''; message.value = ''
  try {
    await api.post(path, { ...payload, request_id: pending.get(signature) })
    if (token !== generation) return
    pending.delete(signature); offset.value = 0; message.value = 'Ajuste aprobado y registrado.'; emit('changed'); await load(true)
  } catch (err) { if (token === generation) error.value = detail(err) }
  finally { if (token === generation) busy.value = false }
}
function page(delta) { offset.value += delta; load() }
</script>

<template>
  <section class="profile-adjustments" aria-label="Ajustes térmicos del proceso">
    <h3>Ajustes térmicos del proceso</h3>
    <p>Cada aprobación registra autor, motivo y hora de vigencia. La banda inicial y los ajustes anteriores se conservan.</p>
    <button type="button" :disabled="busy" @click="load(true)">Actualizar ajustes</button>
    <p v-if="busy" role="status">Procesando ajustes…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <template v-if="context">
      <p><strong>Banda inicial:</strong> {{ band(context.initial) }} · <strong>Banda vigente:</strong> {{ band(context.applied) }} · Revisión {{ context.revision }}</p>
      <p>Los episodios abiertos conservan sus umbrales hasta confirmar recuperación con mediciones. Cambiar la banda no resuelve incidentes.</p>
      <ul v-if="context.open_episodes.length">
        <li v-for="episode in context.open_episodes" :key="episode.id">Episodio #{{ episode.id }}: banda conservada {{ band(episode.configuration) }}</li>
      </ul>
      <p v-if="!context.can_approve">Solo un administrador o enólogo de esta bodega puede aprobar ajustes.</p>
      <p v-if="!context.can_adjust">Se requiere un proceso abierto con una banda térmica inicial completa y conservada.</p>
      <details v-if="context.can_approve && context.can_adjust">
        <summary>Aprobar un ajuste térmico</summary>
        <form @submit.prevent="approve">
          <label>Acción del ajuste<select v-model="form.accion" :disabled="busy"><option value="ajustar">Definir banda térmica</option><option value="restaurar">Restaurar banda inicial</option></select></label>
          <template v-if="form.accion === 'ajustar'">
            <label>Mínimo térmico (°C)<input v-model="form.temp_min" type="number" step="any" min="-50" max="100" required :disabled="busy" /></label>
            <label>Máximo térmico (°C)<input v-model="form.temp_max" type="number" step="any" min="-50" max="100" required :disabled="busy" /></label>
          </template>
          <p v-else>Se registrará una nueva revisión con la banda inicial {{ band(context.initial) }}.</p>
          <label>Motivo del ajuste<textarea v-model.trim="form.motivo" minlength="10" maxlength="2000" required :disabled="busy" /></label>
          <p>La vigencia comienza al aprobar. Revisa los valores y su justificación antes de guardar.</p>
          <button :disabled="busy">Aprobar y guardar ajuste</button>
        </form>
      </details>
      <p v-if="!context.total">Sin ajustes registrados.</p>
      <article v-for="row in context.items" :key="row.id">
        <h4>Revisión {{ row.revision }} · {{ row.accion === 'restaurar' ? 'Restauración' : 'Ajuste' }} · {{ band(row.configuracion) }}</h4>
        <p>Vigente desde {{ date(row.vigente_desde) }} · Aprobado por usuario #{{ row.usuario_id }} · Bitácora #{{ row.bitacora_id }}</p>
        <p>{{ row.motivo }}</p>
      </article>
      <nav v-if="context.total > size" aria-label="Páginas de ajustes">
        <button :disabled="busy || !offset" @click="page(-size)">Anterior</button>
        <span>{{ offset + 1 }}–{{ Math.min(offset + size, context.total) }} de {{ context.total }}</span>
        <button :disabled="busy || offset + size >= context.total" @click="page(size)">Siguiente</button>
      </nav>
    </template>
  </section>
</template>

<style scoped>
.profile-adjustments { background: #fff; color: #342832; border: 1px solid #d8c8ce; padding: 20px; border-radius: 12px; margin: 20px 0; }
h3, h4 { margin: 0 0 12px; } p, li, summary { font-size: 14px; line-height: 1.6; overflow-wrap: anywhere; } p { white-space: pre-wrap; }
article, details { border-top: 1px solid #d8c8ce; padding: 16px 0; }
form { display: grid; gap: 12px; margin-top: 12px; } label { display: grid; gap: 5px; font-size: 14px; }
input, select, textarea { width: 100%; box-sizing: border-box; min-width: 0; padding: 10px; border: 1px solid #8a7b85; border-radius: 6px; background: white; color: #342832; font: inherit; } textarea { min-height: 80px; resize: vertical; }
button { background: #66324c; color: white; border: 0; border-radius: 6px; padding: 9px 14px; margin: 4px 8px 4px 0; cursor: pointer; } button:disabled { opacity: .5; cursor: default; }
:focus-visible { outline: 3px solid #2185a3; outline-offset: 3px; } nav { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; } [role=alert] { color: #9a193f; }
</style>
