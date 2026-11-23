<script setup>
import { ref, watch } from 'vue'
import api from '../services/api'
const props = defineProps({ profileId: Number, revision: Number })
const rows = ref([])
const error = ref('')
const loading = ref(false)
watch(() => [props.profileId, props.revision], async (_, __, cleanup) => {
  let active = true
  cleanup(() => { active = false })
  rows.value = []; error.value = ''; loading.value = true
  try {
    const response = await api.get(`/api/perfiles/${props.profileId}/versiones`)
    if (active) rows.value = [...response.data].sort((a, b) => b.revision - a.revision)
  } catch {
    if (active) error.value = 'No se pudo consultar el historial de versiones.'
  } finally { if (active) loading.value = false }
}, { immediate: true })
const origins = { creacion: 'Creación', edicion: 'Edición', archivo: 'Archivado', captura_existente: 'Captura de configuración existente', captura_demo_sintetica: 'Configuración de demo sintética' }
</script>

<template>
  <section class="profile-history" aria-label="Historial del perfil">
    <h2>Historial de versiones</h2>
    <p>Los procesos que fijaron sus parámetros al inicio conservan la versión con la que comenzaron.</p>
    <p v-if="loading" role="status">Consultando versiones…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!loading && !error && !rows.length">Aún no hay versiones registradas en el historial de este perfil.</p>
    <details v-for="row in rows" :key="row.revision">
      <summary>Versión {{ row.revision }} · {{ origins[row.origin] || row.origin }} · {{ new Date(row.registered_at).toLocaleString('es-CL') }}</summary>
      <p>{{ row.actor_id ? `Registrada por usuario #${row.actor_id}` : 'Autor de la configuración original no registrado' }}</p>
      <dl>
        <div><dt>Nombre</dt><dd>{{ row.configuration.nomb_perfil }}</dd></div>
        <div><dt>Temperatura</dt><dd>{{ row.configuration.temp_min ?? 'N/D' }}–{{ row.configuration.temp_max ?? 'N/D' }} °C</dd></div>
        <div><dt>pH</dt><dd>{{ row.configuration.ph_min ?? 'N/D' }}–{{ row.configuration.ph_max ?? 'N/D' }}</dd></div>
        <div><dt>Caída diaria configurada</dt><dd>{{ row.configuration.brix_caida_min_dia ?? 'N/D' }} °Bx/d</dd></div>
        <div><dt>Estado</dt><dd>{{ row.configuration.activo ? 'Activo' : 'Archivado' }}</dd></div>
      </dl>
    </details>
  </section>
</template>

<style scoped>
.profile-history { background: var(--paper); border: 1px solid var(--rule); border-radius: 12px; padding: 18px 21px; margin-top: 18px; overflow-wrap: anywhere; }
h2 { font: 400 1.9rem/1.12 var(--display); }
p, summary { font-size: .84rem; line-height: 1.6; }
p { margin-top: 6px; color: var(--muted); }
details { border-top: 1px solid var(--rule); margin-top: 10px; padding-top: 9px; }
summary { color: var(--wine); cursor: pointer; font-weight: 600; }
summary:focus-visible { outline: 2px solid var(--wine); outline-offset: 2px; }
dl { display: grid; grid-template-columns: repeat(auto-fit,minmax(min(150px,100%),1fr)); gap: 12px; margin-top: 12px; }
dt { font-size: .76rem; color: var(--muted); } dd { margin: 3px 0; font-size: .86rem; }
[role=alert] { color: #882f40; }
</style>
