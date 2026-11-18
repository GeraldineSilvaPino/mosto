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
const number = (value, digits = 3) => Number.isFinite(value) ? Number(value.toFixed(digits)).toFixed(digits) : 'N/D'
const percent = value => Number.isFinite(value) ? `${(value * 100).toFixed(0)} %` : 'N/D'
const minutes = value => Number.isFinite(value) ? `${(value / 60).toFixed(0)} min` : 'N/D'
const date = value => value ? new Date(value).toLocaleString('es-CL') : 'Sin registro'
const features = computed(() => data.value?.features || {})
const observations = {
  ralentizacion_observada: 'Ralentización observada en la ventana',
  sin_desviacion_detectada: 'Sin ralentización detectada por esta regla',
  sin_evaluacion: 'Sin evaluación fiable de Brix'
}
const monitoringLabels = {
  sin_telemetria_v2: 'Sin telemetría v2 recibida para este proceso',
  sin_recepcion_reciente: 'Sin recepción reciente de telemetría',
  mediciones_atrasadas: 'Se reciben paquetes, pero las mediciones están atrasadas',
  datos_recientes: 'Recepción y mediciones recientes; revisar calidad por canal',
  proceso_cerrado: 'Proceso cerrado: seguimiento histórico'
}
const reasonLabels = {
  coverage: 'Cobertura insuficiente', gap: 'Huecos demasiado largos', stale: 'Sin datos recientes',
  latest_quality: 'Última lectura no utilizable', recent_coverage: 'Cobertura reciente insuficiente',
  calibration_or_device_change: 'Cambio de calibración o dispositivo'
}
function reasonLabel(reason) {
  if (reason === 'ambiguous_timestamps') return 'Hay observaciones con la misma hora'
  if (reason === 'mixed_sources') return 'Hay fuentes mezcladas en el proceso'
  const channel = reason.startsWith('temperature_') ? 'Temperatura' : 'Brix'
  const suffix = reason.replace(/^(temperature|brix)_/, '')
  return `${channel}: ${reasonLabels[suffix] || suffix}`
}
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
  <section class="kinetics-panel" aria-label="Cinética de Brix aparente" :aria-busy="loading">
    <header>
      <div><h2>Evolución de Brix aparente</h2><p>Tasas por hora · ventana de 24 horas</p></div>
      <button type="button" @click="refresh" :disabled="loading">{{ loading ? 'Actualizando…' : 'Actualizar' }}</button>
    </header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!data" role="status">Consultando cobertura y evolución…</p>
    <template v-else>
      <div v-if="data.current_monitoring" class="monitoring" role="status">
        <strong>{{ monitoringLabels[data.current_monitoring.status] || 'Estado de seguimiento desconocido' }}</strong>
        <p>Última recepción: {{ date(data.current_monitoring.last_received_at) }} · Última medición: {{ date(data.current_monitoring.last_observed_at) }}</p>
        <p v-if="Object.values(data.current_monitoring.thermal_rules || {}).includes('sin_limites_de_perfil')">Reglas térmicas sin límites de perfil: no se están suponiendo umbrales.</p>
        <p v-else-if="Object.values(data.current_monitoring.thermal_rules || {}).includes('pendiente_primera_evaluacion')">Reglas térmicas pendientes de su primera evaluación.</p>
        <p>El silencio no acredita recuperación. Diagnóstico actual: {{ date(data.current_monitoring.evaluated_at) }}.</p>
      </div>
      <p class="observation">{{ observations[data.observation] || 'Sin evaluación fiable' }}</p>
      <p class="context">{{ data.evidence?.source?.includes('simulado') ? 'Telemetría simulada' : data.evidence?.source?.includes('fisico') ? 'Dispositivo físico' : 'Sin telemetría v2 disponible' }} · Evaluado: {{ date(data.as_of) }}</p>
      <dl class="metrics">
        <div><dt>Brix aparente · media 1 h</dt><dd>{{ number(features.brix_mean_1h, 2) }} °Bx</dd></div>
        <div><dt>Tasa suavizada</dt><dd>{{ number(features.brix_rate_smoothed) }} °Bx/h</dd></div>
        <div><dt>Pendiente 6 h</dt><dd>{{ number(features.brix_slope_6h) }} °Bx/h</dd></div>
        <div><dt>Pendiente 24 h</dt><dd>{{ number(features.brix_slope_24h) }} °Bx/h</dd></div>
        <div><dt>Temperatura · media 1 h</dt><dd>{{ number(features.temperature_mean_1h, 2) }} °C</dd></div>
      </dl>
      <div class="coverage">
        <article v-for="(label, channel) in { brix: 'Brix', temperature: 'Temperatura' }" :key="channel">
          <h3>{{ label }}</h3>
          <p>Cobertura: <strong>{{ percent(data.channels?.[channel]?.coverage) }}</strong></p>
          <p>Mayor hueco: {{ minutes(data.channels?.[channel]?.max_gap_seconds) }}</p>
          <p>Edad de última lectura válida: {{ minutes(data.channels?.[channel]?.latest_age_seconds) }}</p>
        </article>
      </div>
      <div v-if="data.abstention_reasons?.length" class="abstention" role="status">
        <strong>Evaluación incompleta</strong>
        <ul><li v-for="reason in data.abstention_reasons" :key="reason">{{ reasonLabel(reason) }}</li></ul>
        <p>Se muestran solo las métricas de los canales utilizables.</p>
      </div>
      <p v-if="data.current_kinetic_rule?.configured" class="rule-status">
        Regla persistente experimental activada para simulación.
        {{ data.current_kinetic_rule.episode_id ? `Episodio #${data.current_kinetic_rule.episode_id} en seguimiento.` : 'Sin episodio abierto registrado.' }}
      </p>
      <p v-else class="rule-status">Regla persistente sin configurar. Estas observaciones no generan incidentes cinéticos.</p>
      <p class="limitation">Brix aparente no equivale a azúcar residual. Estas tasas no confirman una parada ni identifican su causa. Riesgo futuro y proyección: N/D, pendientes de validación.</p>
    </template>
  </section>
</template>

<style scoped>
.kinetics-panel { margin: 24px 0; padding: 24px; background: #fff; color: #20262d; border: 1px solid #d8d6d3; border-radius: 16px; }
header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; }
h2 { margin: 0 0 6px; font-size: 20px; } h3 { margin: 0 0 8px; font-size: 14px; }
p { font-size: 13px; line-height: 1.6; margin: 5px 0; }
header p, .context, dt { color: #53606c; }
button { padding: 8px 14px; background: #fff; border: 1px solid #76263d; color: #76263d; border-radius: 8px; cursor: pointer; }
button:focus-visible { outline: 3px solid #277c9d; outline-offset: 3px; } button:disabled { opacity: .65; cursor: wait; }
.observation { font-size: 16px; font-weight: 600; margin-top: 20px; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 18px; margin: 20px 0; }
dt { font-size: 12px; } dd { margin: 6px 0 0; font-size: 20px; font-variant-numeric: tabular-nums; }
.coverage { display: flex; flex-wrap: wrap; gap: 20px; } article { flex: 1 1 220px; background: #f5f3ef; border-radius: 10px; padding: 14px; }
.abstention { margin-top: 16px; padding: 14px; background: #fff6df; color: #65410c; font-size: 13px; border-radius: 10px; }
.monitoring { margin-top: 16px; padding: 14px; background: #eef2f5; border-radius: 10px; font-size: 13px; }
ul { padding-left: 20px; line-height: 1.7; }.rule-status { margin-top: 16px; }.limitation { margin-top: 12px; color: #53606c; }
[role=alert] { color: #9a193f; }
@media (max-width: 540px) { .kinetics-panel { padding: 16px; } .metrics { grid-template-columns: 1fr 1fr; } dd { font-size: 17px; } }
</style>
