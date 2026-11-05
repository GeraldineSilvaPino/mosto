<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Grape,
  LayoutDashboard,
  Cylinder,
  Bell,
  RadioTower,
  SlidersHorizontal,
  ClipboardList,
  UsersRound,
  Building2,
  ShieldCheck,
  LogIn,
  KeyRound,
  ChevronRight,
  ChevronDown,
  Search,
  BookOpen,
  Download,
  MoreVertical,
  LogOut,
  Sparkles
} from 'lucide-vue-next'
import alertService from '../services/alertService'

const route = useRoute()
const router = useRouter()

// Contador reactivo de alertas pendientes en navbar/sidebar
const pendingAlertsCount = ref(0)
let alertPollTimer = null

// Modo de visualización en sidebar (Dashboard vs Sensores IoT)
const activeViewMode = ref('dashboard')

// Buscador global rápido
const globalSearchText = ref('')

// Dropdowns y menús contextuales
const showTenantMenu = ref(false)
const showUserMenu = ref(false)

async function updatePendingCount() {
  try {
    const metricas = await alertService.obtenerMetricas()
    pendingAlertsCount.value = metricas.alertas_activas || 0
  } catch (err) {
    // Si el backend aún no está listo, silencioso
  }
}

onMounted(() => {
  updatePendingCount()
  alertPollTimer = setInterval(updatePendingCount, 15000)

  // Escuchar shortcut de teclado Ctrl+K o Cmd+K para enfocar búsqueda
  window.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  if (alertPollTimer) clearInterval(alertPollTimer)
  window.removeEventListener('keydown', handleGlobalKeydown)
})

function handleGlobalKeydown(e) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    const searchInput = document.getElementById('global-search-input')
    if (searchInput) searchInput.focus()
  }
}

function handleGlobalSearch() {
  if (!globalSearchText.value.trim()) return
  // Si estamos en otra vista, navegar a dashboard con la query
  router.push({ path: '/', query: { q: globalSearchText.value.trim() } })
}

function handleExportGlobal() {
  // Disparar evento personalizado de exportación para la vista activa
  window.dispatchEvent(new CustomEvent('mosto:export-data'))
}

const navSections = [
  {
    title: 'Monitoreo & Análisis',
    items: [
      { id: '01', name: 'Dashboard General', path: '/', icon: LayoutDashboard },
      { id: '02', name: 'Detalle de Cuba', path: '/cuba-detalle', icon: Cylinder },
      { id: '03', name: 'Historial / Auditoría', path: '/historial-alertas', icon: ShieldCheck }
    ]
  },
  {
    title: 'Alertas & Protocolo',
    items: [
      { id: '04', name: 'Alertas e Incidencias', path: '/alertas', icon: Bell, badgeType: 'alert' },
      { id: '05', name: 'Bitácora Enológica', path: '/bitacora', icon: ClipboardList }
    ]
  },
  {
    title: 'Hardware IoT & Perfiles',
    items: [
      { id: '06', name: 'Dispositivos IoT', path: '/dispositivos', icon: RadioTower, badgeText: 'En Vivo' },
      { id: '07', name: 'Perfil y Umbrales', path: '/perfiles-umbrales', icon: SlidersHorizontal }
    ]
  },
  {
    title: 'Administración SaaS',
    items: [
      { id: '08', name: 'Usuarios y Roles', path: '/usuarios', icon: UsersRound },
      { id: '09', name: 'Configuración Viña', path: '/configuracion-empresa', icon: Building2 }
    ]
  }
]

const currentTitle = computed(() => {
  return route.meta?.title || 'MOSTO'
})
</script>

<template>
  <div class="app-container">
    <!-- Barra Lateral (Estilo Searchable) -->
    <aside class="sidebar">
      <!-- Selector de Bodega / Entidad Superior -->
      <div class="sidebar-header">
        <div class="workspace-selector" @click="showTenantMenu = !showTenantMenu">
          <div class="workspace-info">
            <div class="workspace-badge-icon">
              <Grape :size="15" :stroke-width="2.2" />
            </div>
            <div class="workspace-text">
              <span class="workspace-title">vina-santaemiliana.cl</span>
              <span class="workspace-sub">Planta Principal · Valle Central</span>
            </div>
          </div>
          <ChevronDown :size="14" class="workspace-chevron" />
        </div>
      </div>

      <!-- Segmented Control / Pill Mode Switcher -->
      <div class="sidebar-mode-switcher">
        <button
          type="button"
          class="mode-pill-btn"
          :class="{ active: activeViewMode === 'dashboard' }"
          @click="activeViewMode = 'dashboard'; router.push('/')"
        >
          Dashboard
        </button>
        <button
          type="button"
          class="mode-pill-btn"
          :class="{ active: activeViewMode === 'iot' }"
          @click="activeViewMode = 'iot'; router.push('/dispositivos')"
        >
          Sensores IoT
        </button>
      </div>

      <!-- Menú de Navegación Organizado por Categorías -->
      <nav class="sidebar-nav">
        <div v-for="(section, idx) in navSections" :key="idx" class="nav-section">
          <div class="nav-section-title">{{ section.title }}</div>
          <router-link
            v-for="item in section.items"
            :key="item.path"
            :to="item.path"
            class="nav-link"
            :class="{ active: route.path === item.path }"
          >
            <component :is="item.icon" :size="16" :stroke-width="1.8" class="nav-link-icon" />
            <span>{{ item.name }}</span>

            <!-- Badge de Alerta Activa -->
            <span
              v-if="item.badgeType === 'alert' && pendingAlertsCount > 0"
              class="nav-alert-pill"
              title="Alertas pendientes"
            >
              {{ pendingAlertsCount }}
            </span>

            <!-- Badge Informativo 'En Vivo' -->
            <span
              v-else-if="item.badgeText"
              class="badge-pill-cyan"
            >
              {{ item.badgeText }}
            </span>
          </router-link>
        </div>
      </nav>

      <!-- Pie de Barra Lateral con Perfil de Usuario -->
      <div class="sidebar-footer">
        <div class="user-profile">
          <div class="user-info-group">
            <div class="user-avatar">SC</div>
            <div class="user-details">
              <span class="user-name">Sarah Chen</span>
              <span class="user-role">sarah@santaemiliana.cl</span>
            </div>
          </div>
          <button
            type="button"
            class="sidebar-action-btn"
            title="Opciones de cuenta"
            @click="showUserMenu = !showUserMenu"
          >
            <MoreVertical :size="15" style="color: var(--text-muted);" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Área de Contenido Principal -->
    <div class="main-layout">
      <!-- Topbar Header con Buscador y Acciones (Estilo Searchable) -->
      <header class="topbar">
        <!-- Buscador Global Central -->
        <div class="topbar-search-wrapper">
          <Search :size="15" class="topbar-search-icon" />
          <input
            id="global-search-input"
            v-model="globalSearchText"
            type="text"
            class="topbar-search-input"
            placeholder="Buscar cubas, cepas, sensores o alertas..."
            @keyup.enter="handleGlobalSearch"
          />
          <span class="topbar-search-badge">⌘K</span>
        </div>

        <!-- Acciones a la Derecha -->
        <div class="topbar-actions">
          <!-- Indicador de Telemetría en Vivo -->
          <div class="telemetry-status-badge">
            <span class="telemetry-pulse-dot"></span>
            <span>Telemetría en Vivo (5s)</span>
          </div>

          <!-- Botón de Documentación / Aprender -->
          <button
            type="button"
            class="btn-learn"
            title="Consultar manual enológico y protocolos"
            @click="router.push('/bitacora')"
          >
            <BookOpen :size="14" />
            <span>Guía Enológica</span>
          </button>

          <!-- Botón de Exportar (Dark Pill estilo Searchable) -->
          <button
            type="button"
            class="btn-export"
            title="Exportar reporte de telemetría a CSV / PDF"
            @click="handleExportGlobal"
          >
            <Download :size="14" />
            <span>Exportar</span>
          </button>
        </div>
      </header>

      <!-- Contenedor de la Vista Activa -->
      <main class="content-wrapper">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.sidebar-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all 0.15s ease;
}

.sidebar-action-btn:hover {
  background-color: var(--bg-subtle);
  color: var(--text-primary);
}
</style>
