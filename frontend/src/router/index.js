import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'

const routes = [
  // ==========================================
  // Módulo 1: Autenticación y Acceso
  // ==========================================
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: 'Inicio de Sesión', module: 'Módulo 1: Autenticación' }
  },
  {
    path: '/recuperar-password',
    name: 'ForgotPassword',
    component: () => import('../views/ForgotPasswordView.vue'),
    meta: { title: 'Recuperación de Contraseña', module: 'Módulo 1: Autenticación' }
  },

  // ==========================================
  // Layout Principal con Sidebar
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

export default router
