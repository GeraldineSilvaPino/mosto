<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import apiClient from '../services/api'

const props = defineProps({ processId: { type: Number, required: true } })
const simulation = ref(null)
const error = ref(false)
const phases = [
  { key: 'lag', label: 'Adaptación', interval: '≈ 0–20 h' },
  { key: 'exponential', label: 'Exponencial', interval: '≈ 20–70 h' },
  { key: 'stationary', label: 'Estacionaria', interval: '≈ 70–150 h' },
  { key: 'decline', label: 'Declive', interval: '≈ >150 h' }
]
const scenarios = { healthy: 'Evolución sana', cold_shock: 'Choque por frío', heat_stress: 'Estrés por calor', nutrient_depletion: 'Agotamiento de nutrientes', slow: 'Fermentación lenta' }
let generation = 0
let timer
let busy = false
async function refresh() {
  if (busy || !props.processId) return
  busy = true
  const current = generation
  try {
    const { data } = await apiClient.get(`/api/simulaciones/procesos/${props.processId}`)
    if (current === generation) { simulation.value = data; error.value = false }
  } catch {
    if (current === generation) error.value = true
  } finally { busy = false }
}
watch(() => props.processId, () => {
  generation++
  simulation.value = null
  error.value = false
  clearInterval(timer)
  refresh()
  timer = setInterval(refresh, 5000)
}, { immediate: true })
onBeforeUnmount(() => { generation++; clearInterval(timer) })
</script>

<template>
  <p v-if="error" class="simulation-error" role="status">No se pudo actualizar la información de simulación.</p>
  <section v-if="simulation?.registered" class="simulation-panel" aria-label="Trayectoria simulada">
    <div class="simulation-header">
      <div>
        <span class="simulation-eyebrow">CUBA SIMULADA · {{ scenarios[simulation.scenario] }}</span>
        <h2>Fase programada de fermentación</h2>
      </div>
      <span class="simulation-clock">Tiempo físico · 1× · muestras cada 5 min</span>
    </div>
    <div class="simulation-phases">
      <div v-for="phase in phases" :key="phase.key" class="simulation-phase" :class="{ active: simulation.phase === phase.key }">
        <div class="phase-top"><strong>{{ phase.label }}</strong><span>{{ phase.interval }}</span></div>
        <div class="phase-track"><div :style="{ width: `${(simulation.phase_weights?.[phase.key] || 0) * 100}%` }"></div></div>
      </div>
    </div>
    <div class="simulation-footer">
      <span v-if="simulation.observed_age_hours != null">Última muestra: {{ simulation.observed_age_hours.toFixed(1) }} h de proceso</span>
      <span v-else>Esperando la primera muestra del simulador</span>
      <span v-if="simulation.calibration_revoked" class="simulation-warning">Calibración revocada</span>
      <span v-else-if="simulation.process_closed">Proceso cerrado</span>
      <span v-else-if="simulation.coverage === 'atrasado'" class="simulation-warning">Historial pendiente: {{ (simulation.lag_seconds / 3600).toFixed(1) }} h</span>
      <span v-else-if="simulation.coverage === 'al_dia'">Historial al día</span>
    </div>
    <p>El escenario y las fases pertenecen al generador sintético. No representan un diagnóstico ni una predicción de la cuba física.</p>
  </section>
</template>

<style scoped>
.simulation-panel { margin: 1.5rem 0; padding: 1.5rem; border: 1px solid #d7cad2; border-radius: 14px; background: linear-gradient(120deg, #faf5f8, #fff); color: #342733; }
.simulation-header, .phase-top, .simulation-footer { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.simulation-eyebrow { font-size: .72rem; letter-spacing: .08em; color: #824257; font-weight: 700; }
.simulation-header h2 { font-size: 1.05rem; margin: .45rem 0 0; }
.simulation-clock, .simulation-footer, .simulation-panel p { font-size: .78rem; color: #655b66; }
.simulation-phases { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; margin: 1.4rem 0 1rem; }
.phase-top { font-size: .78rem; gap: .3rem; }
.phase-top span { color: #7c7380; font-size: .7rem; }
.phase-track { height: 6px; background: #e9e2e7; border-radius: 10px; margin-top: .6rem; overflow: hidden; }
.phase-track div { background: #8b284c; height: 100%; transition: width .4s; }
.simulation-phase.active strong { color: #8b284c; }
.simulation-panel p { margin: 1rem 0 0; line-height: 1.5; }
.simulation-warning { color: #975608; }
.simulation-error { font-size: .85rem; color: #975608; }
@media (max-width: 850px) { .simulation-phases { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
