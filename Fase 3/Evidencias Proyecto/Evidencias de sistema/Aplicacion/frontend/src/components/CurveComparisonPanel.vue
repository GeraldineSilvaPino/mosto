<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { Chart, registerables } from 'chart.js'
import api from '../services/api'
Chart.register(...registerables)
const props = defineProps({ processId: { type: Number, required: true } })
const data = ref(null), candidates = ref([]), reference = ref(''), variable = ref('brix_aparente'), hours = ref(24), cutoff = ref('')
const busy = ref(false), error = ref(''), canvas = ref(null)
const exportMessage = ref('')
function exportEvidence() {
  if (!data.value || busy.value) return
  const snapshot = data.value
  const envelope = {
    export_version: 'mosto-curve-evidence-v1',
    exported_at: new Date().toISOString(),
    scope: 'consulted_comparison_snapshot',
    notice: 'Exporta solo el resultado consultado. Conserva límites, exclusiones y anulaciones; no equivale al historial completo.',
    comparison: snapshot
  }
  let url
  try {
    url = URL.createObjectURL(new Blob([JSON.stringify(envelope, null, 2)], { type: 'application/json;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `mosto-comparacion-${snapshot.processes[0].process_id}-${snapshot.variable}-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
    document.body.appendChild(link)
    link.click(); link.remove()
    exportMessage.value = 'Descarga solicitada: evidencia de la comparación consultada en JSON.'
  } catch {
    exportMessage.value = 'No se pudo preparar la descarga. Reintenta la exportación.'
  } finally {
    if (url) setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}
const variables = { brix_aparente: 'Brix aparente', temperatura: 'Temperatura', densidad: 'Densidad', ph: 'pH' }
const reasons = {
  sin_canal_automatico: 'Esta variable no tiene canal automático v2; se muestran solo mediciones manuales.',
  sin_telemetria_disponible: 'Sin telemetría disponible en este intervalo al corte seleccionado.',
  muestras_no_graficables: 'Se excluyeron muestras de calidad insuficiente, sin calibración Brix o con hora ambigua.',
  sin_contrastes_manuales: 'Sin mediciones manuales disponibles en este intervalo.',
  limite_de_registros: 'Resultado parcial: se alcanzó el límite. Reduce la ventana para revisar más detalle.',
  mediciones_anuladas: 'Las mediciones anuladas al corte permanecen en la tabla y se excluyen del gráfico.',
  metodos_brix_no_equivalentes: 'Los métodos de Brix no se consideran equivalentes; no se calcula error ni azúcar residual.',
  incluye_simulacion: 'Incluye datos simulados; no acredita evolución física ni eficacia de tratamientos.',
  recepcion_legacy_no_registrada: 'Lecturas antiguas: el corte filtra la hora de medición; no se registró la hora de recepción.',
  mediciones_manuales_en_hora_real: 'Las mediciones manuales usan hora real y se muestran por separado del reloj simulado.',
  origenes_mixtos: 'Hay distintos orígenes de telemetría, presentados en segmentos separados.'
}
const date = value => value ? new Date(value).toLocaleString('es-CL') : 'Sin registro de recepción'
const localNow = () => { const now = new Date(); return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16) }
const maxCutoff = ref(localNow())
let chart, generation = 0, controller
function destroy() { chart?.destroy(); chart = null }
async function draw() {
  await nextTick()
  if (!canvas.value || !data.value) return
  destroy()
  const datasets = []
  data.value.processes.forEach((process, index) => {
    const color = index ? '#21758a' : '#76263d'
    const prefix = `${process.tank} · proceso ${process.process_id}`
    process.segments.forEach(segment => datasets.push({
      label: `${prefix} · ${segment.source} · equipo ${segment.device_id} · ${segment.calibration_id ? `calibración ${segment.calibration_id}` : 'registro histórico'}`,
      data: segment.points.map(p => ({ x: p.hour, y: p.value, observed: p.observed_at, available: p.available_at })),
      showLine: true, cubicInterpolationMode: 'monotone', stepped: false, borderColor: color, backgroundColor: color, borderDash: index ? [6, 4] : [], borderWidth: 2, pointRadius: 2, spanGaps: false
    }))
    const groups = new Map()
    process.manual.filter(p => !p.annulment && p.unit === data.value.unit).forEach(p => {
      const key = JSON.stringify([p.method, p.instrument])
      if (!groups.has(key)) groups.set(key, { label: `${prefix} · manual · ${p.method} · ${p.instrument}`, data: [],
        showLine: false, borderColor: color, backgroundColor: color, pointStyle: 'triangle', pointRadius: 6 })
      groups.get(key).data.push({ x: p.hour, y: p.value, observed: p.observed_at, available: p.available_at })
    })
    datasets.push(...groups.values())
  })
  chart = new Chart(canvas.value, { type: 'scatter', data: { datasets }, options: {
    responsive: true, maintainAspectRatio: false, animation: false,
    scales: { x: { type: 'linear', min: data.value.age_start, max: Math.max(data.value.age_end, data.value.age_start + .01), title: { display: true, text: 'Horas desde el inicio de cada proceso' } },
      y: { title: { display: true, text: `${variables[data.value.variable]} (${data.value.unit})` } } },
    plugins: { legend: { display: false }, tooltip: { callbacks: {
      label: item => `${item.dataset.label}: ${item.parsed.y} ${data.value.unit}`,
      afterLabel: item => [`Observada: ${date(item.raw.observed)}`, `Disponible: ${date(item.raw.available)}`]
    } } }
  } })
}
async function load() {
  exportMessage.value = ''
  maxCutoff.value = localNow()
  if (cutoff.value && (!Number.isFinite(new Date(cutoff.value).getTime()) || new Date(cutoff.value) > new Date())) {
    error.value = 'El corte debe ser una fecha válida anterior o igual a ahora.'
    return
  }
  const token = ++generation
  controller?.abort(); controller = new AbortController()
  busy.value = true; error.value = ''; data.value = null; destroy()
  try {
    const response = await api.get(`/api/procesos/${props.processId}/comparacion`, { signal: controller.signal, params: {
      variable: variable.value, hours: hours.value, reference_id: reference.value || undefined,
      as_of: cutoff.value ? new Date(cutoff.value).toISOString() : undefined
    } })
    if (token !== generation) return
    data.value = response.data
    await draw()
  } catch (err) { if (token === generation) error.value = err.message || 'No se pudo consultar la comparación.' }
  finally { if (token === generation) busy.value = false }
}
watch(() => props.processId, async () => {
  reference.value = ''; cutoff.value = ''; candidates.value = []
  const ident = props.processId
  load()
  try {
    const result = await api.get('/api/procesos')
    if (ident === props.processId) candidates.value = result.data.filter(p => p.id !== ident)
  } catch { if (ident === props.processId) error.value = 'No se pudo cargar la lista de procesos de referencia.' }
}, { immediate: true })
onBeforeUnmount(() => { generation++; controller?.abort(); destroy() })
</script>

<template>
  <section class="comparison" aria-label="Comparación de curvas y evidencia manual">
    <h3>Curvas del proceso</h3>
    <p>Compara la evolución a la misma edad de fermentación.</p>
    <form @submit.prevent="load">
      <label>Variable de comparación<select v-model="variable" :disabled="busy"><option v-for="(name, key) in variables" :key="key" :value="key">{{ name }}</option></select></label>
      <label>Proceso de referencia<select v-model="reference" :disabled="busy"><option value="">Solo este proceso</option><option v-for="p in candidates" :key="p.id" :value="p.id">{{ p.codigo_cuba }} · proceso {{ p.id }} · {{ p.estado }}</option></select></label>
      <label>Ventana<select v-model="hours" :disabled="busy"><option :value="24">24 horas</option><option :value="48">48 horas</option><option :value="168">7 días</option></select></label>
      <label>Ver datos hasta (hora local)<input v-model="cutoff" type="datetime-local" :max="maxCutoff" :disabled="busy" /><small>Vacío: hasta ahora</small></label>
      <button :disabled="busy">{{ busy ? 'Consultando…' : 'Aplicar filtros' }}</button>
      <button v-if="cutoff" type="button" :disabled="busy" @click="cutoff = ''; load()">Volver a ahora</button>
    </form>
    <p v-if="busy" role="status">Consultando evidencia…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="data">
      <button type="button" :disabled="busy" @click="exportEvidence">Exportar evidencia consultada (JSON)</button>

      <p v-if="exportMessage" role="status">{{ exportMessage }}</p>
      <p>Corte: {{ date(data.as_of) }} · intervalo de edad: {{ data.age_start.toFixed(2) }}–{{ data.age_end.toFixed(2) }} h. Se aplica a las mediciones y, cuando existe, a su hora de recepción.</p>

      <p v-if="!data.processes.some(p => p.segments.length || p.manual.length)" role="status">No hay lecturas en este intervalo. Prueba otra ventana o fecha de corte.</p>
      <div class="plot"><canvas ref="canvas" role="img" :aria-label="`Comparación de ${variables[data.variable]} por horas de proceso. Revisa procedencia, cobertura y tabla de evidencia debajo.`" /></div>
      <article v-for="(process, index) in data.processes" :key="process.process_id" :class="index ? 'reference' : 'main'">
        <h4>{{ index ? 'Referencia · azul' : 'Principal · burdeos' }}: {{ process.tank }} · proceso {{ process.process_id }}</h4>
        <p>Inicio: {{ date(process.process_start) }} · estado actual: {{ process.current_state }} · orígenes automáticos: {{ process.sources.join(', ') || 'sin registros' }}</p>
        <p>Telemetría consultada: {{ process.telemetry.returned }} de {{ process.telemetry.total }} muestras; {{ process.telemetry.excluded }} excluidas del gráfico. Manuales: {{ process.manual_counts.returned }} de {{ process.manual_counts.total }}.</p>
        <details v-if="process.warnings.length"><summary>Notas sobre los datos</summary><ul><li v-for="warning in process.warnings" :key="warning">{{ reasons[warning] || warning }}</li></ul></details>
        <p v-if="process.simulation_clock">Reloj simulado · mediciones hasta {{ date(process.observation_as_of) }}</p>
        <details v-if="process.manual_real?.length"><summary>Mediciones manuales · hora real ({{ process.manual_real.length }})</summary><p v-for="row in process.manual_real" :key="row.id">{{ date(row.observed_at) }} · {{ row.value }} {{ row.unit }} · {{ row.method }} · {{ row.annulment ? 'Anulada' : 'Registrada' }}</p></details>
        <details v-if="process.manual.length"><summary>Evidencia manual ({{ process.manual.length }})</summary>
          <div class="table-wrap"><table><caption>Observaciones y anulaciones conocidas al corte</caption><thead><tr><th>Observación</th><th>Valor / método</th><th>Disponibilidad / autor</th><th>Evidencia</th></tr></thead>
            <tbody><tr v-for="row in process.manual" :key="row.id">
              <td>#{{ row.id }} · {{ date(row.observed_at) }}<br />{{ row.hour.toFixed(2) }} h</td>
              <td>{{ row.value }} {{ row.unit }}<br />{{ row.method }} · {{ row.instrument }}</td>
              <td>{{ date(row.available_at) }}<br />Usuario #{{ row.author_id }}<br />{{ row.annulment ? 'Anulada al corte' : 'Registrada al corte' }}</td>
              <td>{{ row.evidence }}<p v-if="row.annulment">Anulada: {{ row.annulment.reason }} · {{ date(row.annulment.available_at) }}</p><span v-if="row.alert_id">Incidente #{{ row.alert_id }}</span><span v-if="row.intervention_id"> · Intervención #{{ row.intervention_id }}</span></td>
            </tr></tbody></table></div>
        </details>
      </article>

    </template>
  </section>
</template>

<style scoped>
.comparison { background: #fff; color: #342832; border: 1px solid #d8c8ce; padding: 20px; border-radius: 12px; margin: 20px 0; }
h3, h4 { margin: 0 0 12px; } p, li, summary { font-size: 14px; line-height: 1.6; overflow-wrap: anywhere; }
form { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; align-items: end; }
label { display: grid; gap: 5px; font-size: 14px; } input, select { width: 100%; min-width: 0; box-sizing: border-box; padding: 9px; background: white; color: #342832; border: 1px solid #8a7b85; border-radius: 6px; font: inherit; }
button { background: #66324c; color: white; border: 0; border-radius: 6px; padding: 10px; cursor: pointer; } button:disabled { opacity: .5; cursor: default; }
.plot { position: relative; height: 330px; margin: 20px 0; } article { border-left: 4px solid #76263d; padding: 12px; margin: 12px 0; } article.reference { border-color: #21758a; }
.table-wrap { overflow-x: auto; } table { border-collapse: collapse; width: 100%; font-size: 13px; } th, td { text-align: left; padding: 10px; border-bottom: 1px solid #d8c8ce; vertical-align: top; } td { min-width: 135px; overflow-wrap: anywhere; }
[role=alert] { color: #9a193f; } :focus-visible { outline: 3px solid #2185a3; outline-offset: 3px; }
</style>
