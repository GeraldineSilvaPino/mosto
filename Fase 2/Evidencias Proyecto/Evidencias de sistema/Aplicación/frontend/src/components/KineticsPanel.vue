<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import apiClient from '../services/api'

const props = defineProps({ processId: { type: Number, required: true } })
const data = ref(null)
const loading = ref(false)
const error = ref('')
let sequence = 0
let timer
let controller
let disposed = false
const date = value => value ? new Date(value).toLocaleString('es-CL') : ''
const metrics = computed(() => {
  const values = data.value?.display?.metrics || data.value?.features || {}
  const specs = [
    ['brix_mean_1h', 'Brix · media 1 h', '°Bx', 2],
    ['temperature_mean_1h', 'Temperatura · media 1 h', '°C', 2],
    ['brix_slope_6h', 'Tendencia 6 h', '°Bx/h', 3],
    ['brix_slope_24h', 'Tendencia 24 h', '°Bx/h', 3]
  ]
  if (!Number.isFinite(values.brix_mean_1h)) specs.unshift(['brix_latest', 'Último Brix', '°Bx', 2])
  if (!Number.isFinite(values.temperature_mean_1h)) specs.push(['temperature_latest', 'Última temperatura', '°C', 2])
  return specs.filter(([key]) => Number.isFinite(values[key])).map(([key, label, unit, digits]) =>
    ({ key, label, unit, value: values[key].toFixed(digits) }))
})
const sourceLabel = computed(() => data.value?.display?.legacy ? 'Lecturas históricas' : 'Lecturas de sensores')
async function refresh() {
  if (disposed || !props.processId) return
  clearTimeout(timer)
  controller?.abort()
  controller = new AbortController()
  const request = ++sequence
  loading.value = true
  error.value = ''
  try {
    const response = await apiClient.get(`/api/procesos/${props.processId}/cinetica`, {
      signal: controller.signal, timeout: 15000
    })
    if (request === sequence) data.value = response.data
  } catch {
    if (request === sequence) {
      data.value = null
      error.value = 'No se pudo consultar la cinética. Los valores actuales no están disponibles.'
    }
  } finally {
    if (request === sequence && !disposed) {
      loading.value = false
      timer = setTimeout(refresh, 30000)
    }
  }
}
watch(() => props.processId, () => { data.value = null; refresh() }, { immediate: true })
onBeforeUnmount(() => { disposed = true; sequence++; controller?.abort(); clearTimeout(timer) })
</script>

<template>
  <section class="kinetics-panel" aria-label="Evolución de Brix" :aria-busy="loading">
    <header>
      <div><h2>Evolución de la fermentación</h2><p v-if="data?.display?.latest_at">{{ sourceLabel }} · {{ date(data.display.latest_at) }}</p></div>
      <button type="button" @click="refresh" :disabled="loading">{{ loading ? 'Actualizando…' : 'Actualizar' }}</button>
    </header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!data" role="status">Consultando lecturas…</p>
    <dl v-else-if="metrics.length" class="metrics">
      <div v-for="metric in metrics" :key="metric.key"><dt>{{ metric.label }}</dt><dd>{{ metric.value }} <small>{{ metric.unit }}</small></dd></div>
    </dl>
    <p v-else role="status">Esperando lecturas válidas de este proceso.</p>
  </section>
</template>

<style scoped>
.kinetics-panel { padding: 22px; background: #fff; color: #422932; border: 1px solid #e6dadd; border-radius: 16px; }
header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
h2 { margin: 0 0 6px; font-size: 18px; } p { font-size: 12px; color: #79636b; margin: 5px 0; }
button { padding: 8px 14px; background: #faf6f7; border: 1px solid #d9c6cc; color: #76263d; border-radius: 8px; cursor: pointer; }
button:disabled { opacity: .65; } button:focus-visible { outline: 3px solid #76263d; outline-offset: 3px; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 18px; margin: 20px 0 0; }
dt { font-size: 12px; color: #79636b; } dd { margin: 6px 0 0; font-size: 23px; font-variant-numeric: tabular-nums; } small { font-size: 12px; }
[role=alert] { color: #9a193f; }
</style>
