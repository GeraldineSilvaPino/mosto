<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  Cylinder,
  RadioTower,
  SlidersHorizontal,
  ClipboardList,
  UsersRound,
  Building2,
  ShieldCheck,
  MoreVertical,
  LogOut
} from 'lucide-vue-next'
import alertService from '../services/alertService'
import authService from '../services/authService'
import companyService, { wineryDisplayName } from '../services/companyService'

const route = useRoute()
const router = useRouter()
// Contador reactivo de alertas pendientes en navbar/sidebar
const pendingAlertsCount = ref(0)
let alertPollTimer = null

// Dropdowns y menús contextuales
const showUserMenu = ref(false)

// Usuario y Empresa sincronizados con backend y sesión
const currentUser = ref(authService.obtenerUsuarioSesion() || {})
const wineryName = ref(currentUser.value.winery || '')
const accountFooter = ref(null)
const accountButton = ref(null)

watch(() => route.fullPath, () => { showUserMenu.value = false })

function closeAccountMenu() {
  showUserMenu.value = false
  accountButton.value?.focus()
}

function dismissOutside(event) {
  if (!accountFooter.value?.contains(event.target)) showUserMenu.value = false
}

const displayName = computed(() => wineryDisplayName(wineryName.value))

function onWineryRenamed(event) {
  wineryName.value = event.detail
}

async function syncProfile() {
  if (authService.isAuthenticated()) {
    try {
      const u = await authService.obtenerUsuarioActual()
      if (u) {
        currentUser.value = u
        if (u.winery) wineryName.value = u.winery
      }
    } catch {
      // Mantener perfil local si falla
    }
  }

  try {
    const comp = await companyService.obtenerConfiguracion()
    if (comp?.brandName) {
      wineryName.value = comp.brandName
    }
  } catch {
    // Mantener nombre actual
  }
}

function handleLogout() {
  authService.cerrarSesion()
  router.push('/login')
}

async function updatePendingCount() {
  try {
    const metricas = await alertService.obtenerMetricas(null, 'pendiente')
    pendingAlertsCount.value = metricas.total_alertas || 0
  } catch (err) {
    // Si el backend aún no está listo, silencioso
  }
}

onMounted(() => {
  updatePendingCount()
  syncProfile()
  alertPollTimer = setInterval(updatePendingCount, 15000)

  document.addEventListener('pointerdown', dismissOutside)
  window.addEventListener('mosto:incident-updated', updatePendingCount)
  window.addEventListener('mosto:login-success', onUserChanged)
  window.addEventListener('mosto:user-updated', onUserChanged)
  window.addEventListener('mosto:winery-renamed', onWineryRenamed)
  window.addEventListener('mosto:auth-expired', handleLogout)
})

function onUserChanged(e) {
  if (e.detail) {
    currentUser.value = e.detail
    if (e.detail.winery) wineryName.value = e.detail.winery
  }
}

onBeforeUnmount(() => {
  if (alertPollTimer) clearInterval(alertPollTimer)
  document.removeEventListener('pointerdown', dismissOutside)
  window.removeEventListener('mosto:incident-updated', updatePendingCount)
  window.removeEventListener('mosto:login-success', onUserChanged)
  window.removeEventListener('mosto:user-updated', onUserChanged)
  window.removeEventListener('mosto:winery-renamed', onWineryRenamed)
  window.removeEventListener('mosto:auth-expired', handleLogout)
})

const navSections = [
  {
    title: 'Monitoreo',
    items: [
      { id: '01', name: 'Dashboard General', path: '/', icon: LayoutDashboard },
      { id: '02', name: 'Detalle de Cuba', path: '/cuba-detalle', icon: Cylinder },
      { id: '03', name: 'Auditoría', path: '/historial-alertas', icon: ShieldCheck, badgeType: 'alert' }
    ]
  },
  {
    title: 'Operación',
    items: [
      { id: '05', name: 'Bitácora Enológica', path: '/bitacora', icon: ClipboardList }
    ]
  },
  {
    title: 'Configuración',
    items: [
      { id: '06', name: 'Dispositivos IoT', path: '/dispositivos', icon: RadioTower },
      { id: '07', name: 'Perfil y Umbrales', path: '/perfiles-umbrales', icon: SlidersHorizontal }
    ]
  },
  {
    title: 'Administración',
    items: [
      { id: '08', name: 'Usuarios y Roles', path: '/usuarios', icon: UsersRound },
      { id: '09', name: 'Configuración Viña', path: '/configuracion-empresa', icon: Building2 }
    ]
  }
]
</script>

<template>
  <aside class="sidebar">
    <!-- Selector de Bodega / Entidad Superior -->
    <div class="sidebar-header">
      <div class="workspace-selector">
        <div class="workspace-info">
          <img class="workspace-badge-icon" src="../assets/mosto.svg" alt="" width="33" height="33" />
          <div class="workspace-text">
            <span class="workspace-title">Mosto</span>
            <span class="workspace-sub">{{ displayName }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Menú de Navegación Organizado por Categorías -->
    <nav class="sidebar-nav" aria-label="Navegación principal">
      <div v-for="(section, idx) in navSections" :key="idx" class="nav-section">
        <div class="nav-section-title">{{ section.title }}</div>
        <router-link
          v-for="item in section.items"
          :key="item.path"
          :to="item.path"
          :title="item.name"
          :aria-label="item.name"
          class="nav-link"
          :class="{ active: route.path === item.path || (item.path === '/cuba-detalle' && route.name === 'CubaDetailParam') }"
        >
          <component :is="item.icon" :size="16" :stroke-width="1.8" class="nav-link-icon" />
          <span>{{ item.name }}</span>

          <!-- Badge de Alerta Activa -->
          <span
            v-if="item.badgeType === 'alert' && pendingAlertsCount > 0"
            class="nav-alert-pill"
            title="Incidencias por atender"
          >
            {{ pendingAlertsCount }}
          </span>

        </router-link>
      </div>
    </nav>

    <div ref="accountFooter" class="sidebar-footer" @keydown.esc="closeAccountMenu" @focusout="!$event.currentTarget.contains($event.relatedTarget) && (showUserMenu = false)">
      <div class="account">
        <button ref="accountButton" type="button" class="user-profile"
          aria-label="Opciones de cuenta" aria-controls="account-menu" :aria-expanded="showUserMenu"
          :title="currentUser.name || 'Opciones de cuenta'" @click="showUserMenu = !showUserMenu">
          <span class="user-avatar">{{ currentUser.avatarInitial || 'US' }}</span>
          <span class="user-details">
            <span class="user-name">{{ currentUser.name }}</span>
            <span class="user-role">{{ currentUser.email }}</span>
          </span>
          <MoreVertical class="account-more" :size="16" aria-hidden="true" />
        </button>
        <!-- Menú Flotante de Usuario (Logout) -->
        <div v-show="showUserMenu" id="account-menu" class="user-dropdown-menu">
          <div class="dropdown-header">
            <strong>{{ currentUser.name }}</strong>
            <small>{{ currentUser.email }}</small>
            <small>{{ currentUser.role }}</small>
          </div>
          <div class="dropdown-divider"></div>
          <button type="button" class="dropdown-item" @click="router.push('/usuarios'); showUserMenu = false">
            <UsersRound :size="14" />
            <span>Ver Equipo</span>
          </button>
          <button type="button" class="dropdown-item" @click="router.push('/configuracion-empresa'); showUserMenu = false">
            <Building2 :size="14" />
            <span>Configuración Viña</span>
          </button>
          <div class="dropdown-divider"></div>
          <button type="button" class="dropdown-item logout-item" @click="handleLogout">
            <LogOut :size="14" />
            <span>Cerrar Sesión</span>
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* Barra Lateral (Sidebar) */
.sidebar {
  position: sticky;
  top: 0;
  align-self: flex-start;
  height: 100vh;
  height: 100dvh;
  width: 256px;
  background-color: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  z-index: 20;
}

/* Cabecera del Sidebar con Selector de Workspace */
.sidebar-header {
  padding: 1.2rem 1rem .65rem;
}

.workspace-selector { padding: 0 .35rem; }

.workspace-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-width: 0;
}

.workspace-badge-icon {
  width: 33px;
  height: 33px;
  flex-shrink: 0;
}

.workspace-text {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.workspace-title {
  font: 400 2.15rem/.95 var(--sidebar-display);
  letter-spacing: -.04em;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workspace-sub {
  margin-top: 4px;
  font-size: .75rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0.75rem 0.75rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
}

.nav-section {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.nav-section-title {
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 0.35rem 0.65rem 0.35rem;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.5rem 0.65rem;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 0.8125rem;
  font-weight: 500;
  transition: all 0.12s ease;
}

.nav-link:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.nav-link.active,
.nav-link.router-link-exact-active {
  background-color: var(--bg-active);
  color: #65334a;
  font-weight: 600;
}

.nav-link-icon {
  color: var(--text-muted);
  transition: color 0.12s ease;
  flex-shrink: 0;
}

.nav-link:hover .nav-link-icon,
.nav-link.active .nav-link-icon {
  color: #763c51;
}

/* Badges de Navegación */
.nav-alert-pill {
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  font-weight: 700;
  color: #FFFFFF;
  background-color: #943d52;
  padding: 0.1rem 0.5rem;
  border-radius: var(--radius-full);
  margin-left: auto;
}

/* Pie de Barra Lateral */
.sidebar-footer {
  padding: 0.85rem 1rem;
  border-top: 1px solid var(--border-color);
  background-color: var(--bg-sidebar);
}

.account { position: relative; }

.user-profile {
  width: 100%;
  min-height: 36px;
  text-align: left;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.user-profile:hover { background: var(--bg-hover); }
.account-more { margin-left: auto; flex: none; color: var(--text-muted); }

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #59424c;
  color: #FFFFFF;
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}

.user-details {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.user-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 0.6875rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-dropdown-menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  right: 0;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: 0 10px 25px rgba(35, 22, 28, 0.12);
  padding: 0.4rem;
  max-height: calc(100dvh - 72px);
  overflow: auto;
  overflow-wrap: anywhere;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.dropdown-header {
  padding: 0.4rem 0.6rem;
  display: flex;
  flex-direction: column;
}

.dropdown-header strong {
  font-size: 0.82rem;
  color: var(--text-primary);
}

.dropdown-header small {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.dropdown-divider {
  height: 1px;
  background-color: var(--border-color);
  margin: 0.25rem 0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.6rem;
  border-radius: var(--radius-sm);
  font-size: 0.78rem;
  color: var(--text-secondary);
  transition: all 0.12s ease;
  width: 100%;
  text-align: left;
}

.dropdown-item:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.dropdown-item.logout-item {
  color: var(--status-danger);
}

.dropdown-item.logout-item:hover {
  background-color: var(--status-danger-bg);
}

@media (max-width: 900px) {
  .sidebar { width: 60px; }
  .sidebar-header { padding: 1rem .35rem .55rem; }
  .sidebar-footer { padding: .5rem .35rem; }
  .workspace-info, .nav-link, .user-profile { justify-content: center; }
  .workspace-text, .nav-section-title, .nav-link > span, .user-details, .account-more { display: none; }
  .user-profile { min-height: 44px; }
  .sidebar-nav { padding-inline: .35rem; }
  .nav-section + .nav-section { border-top: 1px solid var(--border-color); padding-top: .5rem; }
  .user-dropdown-menu { right: auto; width: min(220px, calc(100vw - 16px)); }
}
</style>
