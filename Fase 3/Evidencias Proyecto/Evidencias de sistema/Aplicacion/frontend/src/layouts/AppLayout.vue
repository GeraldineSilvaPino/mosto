<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '../components/AppSidebar.vue'

const route = useRoute()
const atlasLocations = { Dashboard: 'Dashboard general', CubaDetail: 'Detalle de cuba', CubaDetailParam: 'Detalle de cuba', AlertsAudit: 'Auditoría', Binnacle: 'Bitácora', Devices: 'Dispositivos IoT', Thresholds: 'Perfil y umbrales', Users: 'Usuarios y roles', CompanyConfig: 'Configuración de la viña' }
const atlasSection = computed(() => ({ Binnacle: 'Operación', Devices: 'Configuración', Thresholds: 'Configuración', Users: 'Administración', CompanyConfig: 'Administración' })[route.name] || 'Monitoreo')
const usaAtlas = computed(() => Boolean(atlasLocations[route.name]))
</script>

<template>
  <div class="app-container" :class="{ 'atlas-shell': usaAtlas }">
    <AppSidebar />

    <!-- Área de Contenido Principal -->
    <div class="main-layout">
      <header v-if="usaAtlas" class="topbar">
        <span class="dashboard-location">{{ atlasSection }} <span>/</span> {{ atlasLocations[route.name] }}</span>
      </header>

      <!-- Contenedor de la Vista Activa -->
      <main class="content-wrapper">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
@font-face {
  font-family: 'Instrument Serif';
  src: url('../assets/fonts/instrument-serif-400-latin.woff2') format('woff2');
  font-weight: 400;
  font-display: swap;
}

.atlas-shell .topbar { background: #fbf9f4; }
.dashboard-location { color: var(--text-secondary); font-size: .79rem; }
.dashboard-location span { margin: 0 .4rem; color: var(--text-muted); }
@media(max-width:900px) {
  .atlas-shell .topbar { display: none; }
}
</style>
