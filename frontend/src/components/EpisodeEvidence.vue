<script setup>
import { ref, watch } from 'vue'
import api from '../services/api'
import binnacle from '../services/binnacleService'

const props = defineProps({ alert: Object, revision: { type: Number, default: 0 } })
const events = ref([])
const notes = ref([])
const error = ref('')
const loading = ref(false)
let request = 0
const date = value => value ? new Date(value).toLocaleString('es-CL') : 'Sin registro'
const labels = { activa: 'Fuera de rango', recuperada: 'Recuperación observada', desconocida: 'Calidad insuficiente', cerrada_proceso: 'Proceso finalizado' }
watch(() => [props.alert?.id, props.revision, props.alert?.estado], async () => {
  const current = ++request
  events.value = []; notes.value = []; error.value = ''
  if (!props.alert?.id) return
  loading.value = true
  try {
    const [history, entries] = await Promise.all([
      api.get(`/api/alertas/${props.alert.id}/eventos`),
      binnacle.listarEntradas({ alerta_id: props.alert.id })
    ])
    if (current !== request) return
    events.value = history.data
    notes.value = entries
  } catch (err) {
    if (current === request) error.value = 'No se pudo cargar la trazabilidad. Vuelve a abrir la ficha para reintentar.'
  } finally { if (current === request) loading.value = false }
}, { immediate: true })
</script>

<template>
  <section class="episode-evidence" aria-label="Evidencia del episodio">
    <h4>Evidencia y seguimiento</h4>
    <template v-if="alert?.version_regla">
      <div class="episode-tags">
        <span>{{ alert.origen === 'simulado' ? 'Telemetría simulada' : 'Dispositivo físico' }}</span>
        <span>Condición: {{ labels[alert.estado_condicion] || alert.estado_condicion }}</span>
        <span>Gestión: {{ alert.estado }}</span>
      </div>
      <p>La resolución del operador no acredita recuperación de la temperatura ni confirma una parada de fermentación.</p>
      <dl>
        <div><dt>Temperatura al confirmar</dt><dd>{{ alert.evidencia?.temperature_c ?? 'N/D' }} °C</dd></div>
        <div><dt>Perfil aplicado</dt><dd>{{ alert.evidencia?.configuration?.temp_min ?? 'N/D' }}–{{ alert.evidencia?.configuration?.temp_max ?? 'N/D' }} °C</dd></div>
        <div><dt>Inicio observado</dt><dd>{{ date(alert.inicio_condicion) }}</dd></div>
        <div><dt>Disponible en plataforma</dt><dd>{{ date(alert.timestamp) }}</dd></div>
        <div><dt>Última observación evaluada</dt><dd>{{ date(alert.ultima_observacion) }}</dd></div>
        <div><dt>Regla</dt><dd>{{ alert.version_regla }}</dd></div>
      </dl>
      <p v-if="!alert.fin_condicion && Date.now() - new Date(alert.ultima_observacion).getTime() > 900000" role="status">
        Sin observación reciente: el estado registrado no acredita la condición actual.
      </p>
    </template>
    <p v-if="loading" role="status">Cargando trazabilidad…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <ol v-if="events.length">
      <li v-for="event in events" :key="event.id">
        <strong>{{ event.accion }}</strong> · {{ date(event.registrado_en) }} · {{ event.usuario_id ? `Usuario #${event.usuario_id}` : 'Sistema' }}
        <small v-if="event.observado_en">Observado: {{ date(event.observado_en) }}</small>
      </li>
    </ol>
    <h5>Bitácora vinculada</h5>
    <p v-if="!loading && !error && !notes.length">Sin intervenciones registradas.</p>
    <article v-for="note in notes" :key="note.id">
      <strong>{{ note.author }}</strong> · {{ date(note.timestamp) }}
      <p>{{ note.message }}</p>
    </article>
  </section>
</template>

<style scoped>
.episode-evidence { padding: 20px; margin-bottom: 24px; border: 1px solid #d8c8ce; border-radius: 12px; background: #faf7f8; color: #342832; }
h4, h5 { margin: 0 0 12px; }
.episode-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.episode-tags span { padding: 5px 9px; border-radius: 6px; background: #eee4e8; font-size: 12px; }
dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
dt, small { color: #63555f; font-size: 12px; }
dd { margin: 3px 0 0; font-size: 13px; font-weight: 600; }
ol { padding-left: 20px; } li { margin-bottom: 10px; font-size: 13px; } small { display: block; }
p { font-size: 13px; line-height: 1.6; white-space: pre-wrap; } article { border-top: 1px solid #d8c8ce; padding: 12px 0; font-size: 12px; }
[role=alert] { color: #9a193f; }
</style>
