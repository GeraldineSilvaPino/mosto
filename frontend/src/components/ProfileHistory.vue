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
    if (active) rows.value = response.data
  } catch {
    if (active) error.value = 'No se pudo consultar el historial de versiones.'
  } finally { if (active) loading.value = false }
}, { immediate: true })
const origins = { creacion: 'Creación', edicion: 'Edición', archivo: 'Archivado', captura_existente: 'Captura de configuración existente', captura_demo_sintetica: 'Configuración de demo sintética' }
</script>

<template>
  <section class="profile-history" aria-label="Historial del perfil">
    <h3>Versión actual: {{ revision }}</h3>
    <p>Guardar cambios crea una nueva versión. Los procesos iniciados con una configuración congelada conservan sus parámetros.</p>
    <p v-if="loading" role="status">Consultando versiones…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!loading && !error && !rows.length">Perfil existente sin historial de versiones capturado. No se reconstruyen ediciones anteriores.</p>
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
.profile-history { background: #fff; border: 1px solid #d8d6d3; border-radius: 12px; padding: 20px; margin: 24px 0; color: #20262d; }
h3 { margin: 0 0 10px; } p, summary { font-size: 14px; line-height: 1.6; } details { border-top: 1px solid #ddd; padding: 12px 0; } summary { cursor: pointer; } summary:focus-visible { outline: 3px solid #277c9d; }
dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr)); gap: 14px; } dt { font-size: 12px; color: #53606c; } dd { margin: 4px 0; font-size: 14px; } [role=alert] { color: #9a193f; }
</style>
