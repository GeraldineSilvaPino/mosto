import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'
import authService from '../services/authService.js'

const routes = [
  // ==========================================
  // Módulo 1: Autenticación y Acceso
  // ==========================================
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: 'Inicio de Sesión', public: true }
  },
  {
    path: '/recuperar-password',
    name: 'ForgotPassword',
    component: () => import('../views/ForgotPasswordView.vue'),
    meta: { title: 'Recuperación de Contraseña', public: true }
  },

  // ==========================================
  // Layout Principal con Sidebar (Protegido)
  // ==========================================
  {
    path: '/',
    component: AppLayout,
    children: [
      // Módulo 2: Monitoreo en Vivo (Core)
      {
        path: '',
        alias: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/DashboardView.vue'),
        meta: { title: 'Dashboard General (Dash)', module: 'Módulo 2: Monitoreo' }
      },
      {
        path: 'cuba-detalle',
        name: 'CubaDetail',
        component: () => import('../views/CubaDetailView.vue'),
        meta: { title: 'Detalle de Cuba', module: 'Módulo 2: Monitoreo' }
      },
      {
        path: 'cubas/:id',
        name: 'CubaDetailParam',
        component: () => import('../views/CubaDetailView.vue'),
        meta: { title: 'Detalle de Cuba', module: 'Módulo 2: Monitoreo' }
      },

      // Módulo 3: Alertas y Protocolo
      {
        path: 'alertas',
        name: 'Alerts',
        component: () => import('../views/AlertsView.vue'),
        meta: { title: 'Alertas y Gestión de Incidencias', module: 'Módulo 3: Alertas' }
      },

      // Módulo 4: Hardware y Configuración Operativa
      {
        path: 'dispositivos',
        name: 'Devices',
        component: () => import('../views/DevicesView.vue'),
        meta: { title: 'Dispositivos IoT', module: 'Módulo 4: Hardware' }
      },
      {
        path: 'perfiles-umbrales',
        name: 'Thresholds',
        component: () => import('../views/ThresholdsView.vue'),
        meta: { title: 'Perfil y Umbrales', module: 'Módulo 4: Hardware' }
      },
      {
        path: 'bitacora',
        name: 'Binnacle',
        component: () => import('../views/BinnacleView.vue'),
        meta: { title: 'Bitácora', module: 'Módulo 4: Hardware' }
      },

      // Módulo 5: Administración SaaS y Gestión de Empresa
      {
        path: 'usuarios',
        name: 'Users',
        component: () => import('../views/UsersView.vue'),
        meta: { title: 'Gestión de Usuarios y Roles', module: 'Módulo 5: Administración' }
      },
      {
        path: 'configuracion-empresa',
        name: 'CompanyConfig',
        component: () => import('../views/CompanyConfigView.vue'),
        meta: { title: 'Configuración Empresa / Viña', module: 'Módulo 5: Administración' }
      },
      {
        path: 'historial-alertas',
        name: 'AlertsAudit',
        component: () => import('../views/AlertsAuditView.vue'),
        meta: { title: 'Historial de Alertas / Auditoría', module: 'Módulo 5: Administración' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Guardia de navegación para control de autenticación
router.beforeEach((to, from, next) => {
  // Título del documento
  if (to.meta?.title) {
    document.title = `${to.meta.title} · MOSTO Platform`
  }

  const authenticated = authService.isAuthenticated()

  if (!to.meta?.public && !authenticated) {
    // Si no está autenticado y la ruta es protegida, redirigir a Login
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }

  if (to.path === '/login' && authenticated) {
    // Si ya está autenticado e intenta ir a login, redirigir a inicio
    return next({ path: '/' })
  }

  next()
})

export default router
