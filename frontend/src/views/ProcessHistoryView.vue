<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import CurveComparisonPanel from '../components/CurveComparisonPanel.vue'
import ManualMeasurementsPanel from '../components/ManualMeasurementsPanel.vue'
import InterventionsPanel from '../components/InterventionsPanel.vue'

const route = useRoute(), router = useRouter()
const processes = ref([]), process = ref(null), error = ref(''), listError = ref(''), busy = ref(false)
const revision = ref(0)
const filter = ref('todos'), selected = computed(() => String(route.params.id || ''))
const choices = computed(() => processes.value.filter(p => filter.value === 'todos' ||
  (filter.value === 'cerrados' ? !['en_proceso', 'detenida'].includes(p.estado) : ['en_proceso', 'detenida'].includes(p.estado))))
const date = value => value ? new Date(value).toLocaleString('es-CL') : 'Sin registro'
const detail = err => typeof err.response?.data?.detail === 'string' ? err.response.data.detail : (err.message || 'No se pudo consultar. Reintenta.')
let generation = 0, controller, listController
async function loadList() {
  listController?.abort(); const current = new AbortController(); listController = current
  listError.value = ''
  try {
    const response = await api.get('/api/procesos', { signal: current.signal })
    if (!current.signal.aborted) processes.value = response.data
  } catch (err) { if (!current.signal.aborted) listError.value = detail(err) }
}
async function loadProcess() {
  const token = ++generation
  controller?.abort(); controller = new AbortController()
  process.value = null; error.value = ''; busy.value = false
  if (!selected.value) return
  if (!/^[1-9]\d*$/.test(selected.value) || !Number.isSafeInteger(Number(selected.value))) {
    error.value = 'Identificador de proceso inválido.'; return
  }
  busy.value = true
  try {
    const response = await api.get(`/api/procesos/${selected.value}`, { signal: controller.signal })
    if (token === generation) process.value = response.data
  } catch (err) { if (token === generation) error.value = detail(err) }
  finally { if (token === generation) busy.value = false }
}
watch(selected, loadProcess, { immediate: true })
loadList()
onBeforeUnmount(() => { generation++; controller?.abort(); listController?.abort() })
</script>

<template>
  <main class="process-history">
    <h1>Historial de procesos</h1>
    <p>Revisa lecturas de procesos activos o cerrados y compáralas por fecha.</p>
    <div class="controls">
      <label>Mostrar<select v-model="filter"><option value="todos">Todos</option><option value="cerrados">Cerrados</option><option value="activos">Activos</option></select></label>
      <label>Proceso principal<select :value="selected" @change="router.push($event.target.value ? `/procesos/${$event.target.value}` : '/procesos')">
        <option value="">Seleccionar proceso</option>
        <option v-if="selected && !choices.some(p => String(p.id) === selected)" :value="selected">Proceso #{{ selected }} (fuera del filtro)</option>
        <option v-for="p in choices" :key="p.id" :value="String(p.id)">{{ p.codigo_cuba }} · #{{ p.id }} · {{ p.estado }} · {{ date(p.fecha_inicio) }}</option>
      </select></label>
      <button @click="revision++; loadList(); loadProcess()">Actualizar</button>
    </div>
    <p v-if="listError" role="alert">{{ listError }}</p>
    <p v-if="busy" role="status">Consultando proceso…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!selected">Selecciona un proceso para consultar su evidencia.</p>
    <template v-if="process">
      <section class="summary" aria-label="Proceso seleccionado">
        <h2>{{ process.codigo_cuba }} · proceso #{{ process.id }}</h2>
        <p>Estado actual: {{ process.estado }} · Inicio: {{ date(process.fecha_inicio) }} · {{ process.fecha_real_fin ? `Cierre: ${date(process.fecha_real_fin)}` : 'En curso' }}</p>
        <p>Perfil: {{ process.perfil_nombre || 'Sin perfil registrado' }} <span v-if="process.volumen_litros != null">· Volumen: {{ process.volumen_litros }} L</span></p>
        <RouterLink :to="`/cubas/${process.cuba_id}`">Ver estado actual de la cuba</RouterLink>
      </section>
      <CurveComparisonPanel :key="`curves-${process.id}-${revision}`" :process-id="process.id" />
      <ManualMeasurementsPanel :key="`manual-${process.id}`" :process-id="process.id" />
      <InterventionsPanel :key="`actions-${process.id}`" :process-id="process.id" />
    </template>
  </main>
</template>

<style scoped>
.process-history { padding: 24px; color: #342832; }
.controls { display: flex; flex-wrap: wrap; gap: 16px; align-items: end; }
label { display: grid; gap: 6px; max-width: 100%; }
select, button { padding: 10px; border: 1px solid #8a7b85; border-radius: 6px; font: inherit; max-width: 100%; }
button { background: #66324c; color: white; cursor: pointer; }
.summary { margin-top: 20px; padding: 20px; border: 1px solid #d8c8ce; border-radius: 12px; background: white; }
[role=alert] { color: #9a193f; } :focus-visible { outline: 3px solid #2185a3; outline-offset: 3px; }
</style>
