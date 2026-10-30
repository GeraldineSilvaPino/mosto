<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
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
  ChevronRight
} from 'lucide-vue-next'

const route = useRoute()

const navSections = [
  {
    title: 'Monitoreo en Vivo',
    items: [
      { id: '03', name: 'Dashboard General', path: '/', icon: LayoutDashboard },
      { id: '04', name: 'Detalle de Cuba', path: '/cuba-detalle', icon: Cylinder }
    ]
  },
  {
    title: 'Alertas y Protocolo',
    items: [
      { id: '05', name: 'Alertas e Incidencias', path: '/alertas', icon: Bell }
    ]
  },
  {
    title: 'Hardware y Configuración',
    items: [
      { id: '06', name: 'Dispositivos IoT', path: '/dispositivos', icon: RadioTower },
      { id: '07', name: 'Perfil y Umbrales', path: '/perfiles-umbrales', icon: SlidersHorizontal },
      { id: '08', name: 'Bitácora Enológica', path: '/bitacora', icon: ClipboardList }
    ]
  },
  {
    title: 'Administración SaaS',
    items: [
      { id: '09', name: 'Usuarios y Roles', path: '/usuarios', icon: UsersRound },
      { id: '10', name: 'Configuración Viña', path: '/configuracion-empresa', icon: Building2 },
      { id: '11', name: 'Historial / Auditoría', path: '/historial-alertas', icon: ShieldCheck }
    ]
  },
  {
    title: 'Autenticación',
    items: [
      { id: '01', name: 'Inicio de Sesión', path: '/login', icon: LogIn },
      { id: '02', name: 'Recuperar Contraseña', path: '/recuperar-password', icon: KeyRound }
    ]
  }
]

const currentTitle = computed(() => {
  return route.meta?.title || 'MOSTO'
})
</script>

<template>
  <div class="app-container">
    <!-- Barra Lateral -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="brand">
          <div class="brand-icon">
            <Grape :size="19" :stroke-width="1.8" />
          </div>
          <div>
            <div class="brand-name">mosto.</div>
            <span class="brand-tag">Plataforma Vitivinícola</span>
          </div>
        </div>
      </div>

      <div class="sidebar-tenant">
        <div class="tenant-info">
          <span class="tenant-name">Viña Santa Emiliana</span>
          <span class="tenant-meta">Planta Principal · Cuba 01 a 24</span>
        </div>
      </div>

      <!-- Menú -->
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
            <component :is="item.icon" :size="16" :stroke-width="1.75" />
            <span>{{ item.name }}</span>
            <span class="nav-badge-num">{{ item.id }}</span>
          </router-link>
        </div>
      </nav>

      <!-- Pie de sidebar -->
      <div class="sidebar-footer">
        <div class="user-profile">
          <div class="user-avatar">EN</div>
          <div class="user-details">
            <span class="user-name">Enología & QA</span>
            <span class="user-role">Espacio de Trabajo</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- Contenido Principal -->
    <div class="main-layout">
      <header class="topbar">
        <div class="topbar-breadcrumb">
          <span>Espacio de Trabajo</span>
          <ChevronRight :size="14" style="color: var(--text-muted);" />
          <strong>{{ currentTitle }}</strong>
        </div>

        <div class="topbar-actions">
          <div class="telemetry-status">
            <span class="telemetry-dot"></span>
            <span>Telemetría en línea</span>
          </div>
        </div>
      </header>

      <main class="content-wrapper">
        <router-view />
      </main>
    </div>
  </div>
</template>
