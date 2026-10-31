<script setup>
/**
 * 📋 09. [FRONT - VUE] Pantalla de Gestión de Usuarios y Roles
 * Módulo 5: Administración SaaS y Gestión de Empresa
 * Rama recomendada: feature/09-usuarios-roles
 *
 * Descripción:
 * Interfaz visual para controlar al personal interno de la viña de forma simulada.
 *
 * Características implementadas:
 * 1. Lista de usuarios ficticios con avatar (iniciales), nombre, email, rol y estado.
 * 2. Badges de rol diferenciados visualmente (Admin, Enólogo, Operario).
 * 3. Indicador de estado activo/inactivo.
 * 4. Modal para invitar nuevos usuarios (email + rol).
 * 5. Filtro por rol (pills toggle).
 * 6. Acciones por fila: editar rol, suspender/activar.
 * 7. 100% Frontend autónomo (sin requerir backend).
 */

import { ref, computed, nextTick } from 'vue'
import {
  UserPlus,
  Shield,
  FlaskConical,
  Wrench,
  Pencil,
  UserX,
  UserCheck,
  X,
  Mail,
  Users,
  ChevronDown,
  Check
} from 'lucide-vue-next'

// ==========================================
// CONFIGURACIÓN DE ROLES
// ==========================================
const roles = {
  admin:    { label: 'Administrador', icon: Shield,       colorClass: 'role-admin' },
  enologo:  { label: 'Enólogo',      icon: FlaskConical,  colorClass: 'role-enologo' },
  operario: { label: 'Operario',     icon: Wrench,        colorClass: 'role-operario' }
}

// ==========================================
// DATOS MOCK DE USUARIOS
// ==========================================
let nextId = 10

const users = ref([
  {
    id: 1,
    name: 'Carlos Mendoza',
    email: 'carlos.mendoza@vinamosto.cl',
    role: 'admin',
    active: true
  },
  {
    id: 2,
    name: 'María González',
    email: 'maria.gonzalez@vinamosto.cl',
    role: 'enologo',
    active: true
  },
  {
    id: 3,
    name: 'Alejandro Rojas',
    email: 'alejandro.rojas@vinamosto.cl',
    role: 'operario',
    active: true
  },
  {
    id: 4,
    name: 'Fernanda Vidal',
    email: 'fernanda.vidal@vinamosto.cl',
    role: 'enologo',
    active: false
  },
  {
    id: 5,
    name: 'Roberto Soto',
    email: 'roberto.soto@vinamosto.cl',
    role: 'operario',
    active: true
  },
  {
    id: 6,
    name: 'Valentina Parra',
    email: 'valentina.parra@vinamosto.cl',
    role: 'admin',
    active: true
  },
  {
    id: 7,
    name: 'Diego Fuentes',
    email: 'diego.fuentes@vinamosto.cl',
    role: 'operario',
    active: false
  }
])

// ==========================================
// FILTROS
// ==========================================
const activeFilter = ref('todos')

const filterCounts = computed(() => ({
  all: users.value.length,
  admin: users.value.filter(u => u.role === 'admin').length,
  enologo: users.value.filter(u => u.role === 'enologo').length,
  operario: users.value.filter(u => u.role === 'operario').length
}))

const filteredUsers = computed(() => {
  return users.value
    .filter(u => activeFilter.value === 'todos' || u.role === activeFilter.value)
    .sort((a, b) => {
      // Activos primero, luego por nombre
      if (a.active !== b.active) return b.active - a.active
      return a.name.localeCompare(b.name)
    })
})

// ==========================================
// HELPERS
// ==========================================
function getInitials(name) {
  return name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase()
}

// ==========================================
// MODAL INVITAR USUARIO
// ==========================================
const showInviteModal = ref(false)
const inviteForm = ref({
  name: '',
  email: '',
  role: 'operario'
})

function openInviteModal() {
  inviteForm.value = { name: '', email: '', role: 'operario' }
  showInviteModal.value = true
  nextTick(() => {
    const input = document.querySelector('.modal-name-input')
    if (input) input.focus()
  })
}

function submitInvite() {
  if (!inviteForm.value.name.trim() || !inviteForm.value.email.trim()) return

  users.value.push({
    id: nextId++,
    name: inviteForm.value.name.trim(),
    email: inviteForm.value.email.trim().toLowerCase(),
    role: inviteForm.value.role,
    active: true
  })

  showInviteModal.value = false
}

// ==========================================
// EDITAR ROL (inline dropdown)
// ==========================================
const editingUserId = ref(null)

function toggleEditRole(userId) {
  editingUserId.value = editingUserId.value === userId ? null : userId
}

function setRole(user, newRole) {
  user.role = newRole
  editingUserId.value = null
}

// ==========================================
// SUSPENDER / ACTIVAR
// ==========================================
function toggleActive(user) {
  user.active = !user.active
}
</script>

<template>
  <div class="users-page">
    <!-- Encabezado -->
    <header class="users-header">
      <div>
        <div class="header-pretitle">
          <Users :size="14" />
          <span>Administración de Personal</span>
        </div>
        <h1 class="header-title">Usuarios y Roles</h1>
        <p class="header-description">
          Gestión del equipo interno de la viña: enólogos, operarios y administradores.
        </p>
      </div>
      <div class="header-actions">
        <button type="button" class="btn-invite" @click="openInviteModal">
          <UserPlus :size="16" />
          <span>Invitar usuario</span>
        </button>
      </div>
    </header>

    <!-- Filtros por rol -->
    <section class="toolbar-section">
      <div class="filter-pills">
        <button
          type="button"
          class="pill-btn"
          :class="{ active: activeFilter === 'todos' }"
          @click="activeFilter = 'todos'"
        >
          Todos ({{ filterCounts.all }})
        </button>
        <button
          type="button"
          class="pill-btn pill-admin"
          :class="{ active: activeFilter === 'admin' }"
          @click="activeFilter = 'admin'"
        >
          <Shield :size="13" />
          {{ filterCounts.admin }}
        </button>
        <button
          type="button"
          class="pill-btn pill-enologo"
          :class="{ active: activeFilter === 'enologo' }"
          @click="activeFilter = 'enologo'"
        >
          <FlaskConical :size="13" />
          {{ filterCounts.enologo }}
        </button>
        <button
          type="button"
          class="pill-btn pill-operario"
          :class="{ active: activeFilter === 'operario' }"
          @click="activeFilter = 'operario'"
        >
          <Wrench :size="13" />
          {{ filterCounts.operario }}
        </button>
      </div>
    </section>

    <!-- Lista de usuarios -->
    <section class="users-list">
      <div
        v-for="user in filteredUsers"
        :key="user.id"
        class="user-row"
        :class="{ 'is-inactive': !user.active }"
      >
        <!-- Avatar con iniciales -->
        <div class="user-avatar" :class="roles[user.role].colorClass">
          {{ getInitials(user.name) }}
        </div>

        <!-- Info -->
        <div class="user-info">
          <span class="user-name">{{ user.name }}</span>
          <span class="user-email">{{ user.email }}</span>
        </div>

        <!-- Badge de rol -->
        <div class="user-role-badge" :class="roles[user.role].colorClass">
          <component :is="roles[user.role].icon" :size="13" />
          <span>{{ roles[user.role].label }}</span>
        </div>

        <!-- Estado -->
        <div class="user-status" :class="user.active ? 'status-active' : 'status-inactive'">
          <span class="status-dot"></span>
          <span>{{ user.active ? 'Activo' : 'Inactivo' }}</span>
        </div>

        <!-- Acciones -->
        <div class="user-actions">
          <!-- Editar rol -->
          <div class="action-edit-wrapper">
            <button
              type="button"
              class="action-btn"
              title="Cambiar rol"
              @click="toggleEditRole(user.id)"
            >
              <Pencil :size="14" />
            </button>

            <!-- Dropdown de roles -->
            <transition name="dropdown-fade">
              <div v-if="editingUserId === user.id" class="role-dropdown">
                <button
                  v-for="(cfg, key) in roles"
                  :key="key"
                  type="button"
                  class="role-option"
                  :class="{ selected: user.role === key }"
                  @click="setRole(user, key)"
                >
                  <component :is="cfg.icon" :size="14" />
                  <span>{{ cfg.label }}</span>
                  <Check v-if="user.role === key" :size="14" class="check-icon" />
                </button>
              </div>
            </transition>
          </div>

          <!-- Suspender / Activar -->
          <button
            type="button"
            class="action-btn"
            :class="user.active ? 'action-suspend' : 'action-activate'"
            :title="user.active ? 'Suspender' : 'Reactivar'"
            @click="toggleActive(user)"
          >
            <UserX v-if="user.active" :size="14" />
            <UserCheck v-else :size="14" />
          </button>
        </div>
      </div>

      <!-- Estado vacío -->
      <div v-if="!filteredUsers.length" class="empty-state">
        <Users :size="40" />
        <h3>Sin resultados</h3>
        <p>No hay usuarios con el rol seleccionado.</p>
      </div>
    </section>

    <!-- Modal Invitar Usuario -->
    <transition name="modal-fade">
      <div v-if="showInviteModal" class="modal-overlay" @click.self="showInviteModal = false">
        <div class="modal-card">
          <div class="modal-header">
            <h3>
              <UserPlus :size="18" />
              Invitar usuario
            </h3>
            <button type="button" class="modal-close" @click="showInviteModal = false">
              <X :size="16" />
            </button>
          </div>

          <div class="modal-body">
            <!-- Nombre -->
            <div class="form-field">
              <label class="form-label">Nombre completo</label>
              <input
                v-model="inviteForm.name"
                type="text"
                class="form-input modal-name-input"
                placeholder="Ej: Andrea Muñoz"
              />
            </div>

            <!-- Email -->
            <div class="form-field">
              <label class="form-label">Correo electrónico</label>
              <div class="input-icon-wrapper">
                <Mail :size="15" class="input-icon" />
                <input
                  v-model="inviteForm.email"
                  type="email"
                  class="form-input with-icon"
                  placeholder="andrea.munoz@vinamosto.cl"
                />
              </div>
            </div>

            <!-- Rol -->
            <div class="form-field">
              <label class="form-label">Rol asignado</label>
              <div class="role-selector">
                <button
                  v-for="(cfg, key) in roles"
                  :key="key"
                  type="button"
                  class="role-select-btn"
                  :class="[cfg.colorClass, { active: inviteForm.role === key }]"
                  @click="inviteForm.role = key"
                >
                  <component :is="cfg.icon" :size="15" />
                  <span>{{ cfg.label }}</span>
                </button>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="showInviteModal = false">
              Cancelar
            </button>
            <button
              type="button"
              class="btn-primary"
              :disabled="!inviteForm.name.trim() || !inviteForm.email.trim()"
              @click="submitInvite"
            >
              <UserPlus :size="14" />
              Enviar invitación
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
/* =========================================
   USUARIOS - LAYOUT GENERAL
   ========================================= */
.users-page {
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* =========================================
   ENCABEZADO
   ========================================= */
.users-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.header-pretitle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.73rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 0.3rem;
}

.header-title {
  font-family: var(--font-serif);
  font-size: 2.1rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1.15;
  letter-spacing: -0.01em;
}

.header-description {
  font-size: 0.88rem;
  color: var(--text-secondary);
  margin-top: 0.35rem;
}

.header-actions {
  flex-shrink: 0;
  padding-top: 0.5rem;
}

.btn-invite {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background-color: var(--wine-700);
  color: #FFFFFF;
  padding: 0.55rem 1.15rem;
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
  font-weight: 600;
  transition: background-color 0.15s ease, transform 0.1s ease;
}

.btn-invite:hover {
  background-color: var(--wine-800);
  transform: translateY(-1px);
}

/* =========================================
   TOOLBAR / FILTROS
   ========================================= */
.toolbar-section {
  display: flex;
  align-items: center;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  padding: 0.7rem 1rem;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-subtle);
}

.filter-pills {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.35rem 0.7rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--text-secondary);
  transition: all 0.12s ease;
  cursor: pointer;
}

.pill-btn:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.pill-btn.active {
  background-color: var(--wine-700);
  border-color: var(--wine-700);
  color: #FFFFFF;
}

.pill-btn.pill-admin.active {
  background-color: #B8860B;
  border-color: #B8860B;
}

.pill-btn.pill-enologo.active {
  background-color: #1A5296;
  border-color: #1A5296;
}

.pill-btn.pill-operario.active {
  background-color: var(--status-good);
  border-color: var(--status-good);
}

/* =========================================
   LISTA DE USUARIOS
   ========================================= */
.users-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.user-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.85rem 1.15rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-subtle);
  transition: all 0.15s ease;
}

.user-row:hover {
  border-color: var(--text-light);
  box-shadow: var(--shadow-card);
}

.user-row.is-inactive {
  opacity: 0.55;
}

.user-row.is-inactive:hover {
  opacity: 0.75;
}

/* Avatar */
.user-avatar {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  flex-shrink: 0;
  letter-spacing: 0.02em;
}

.user-avatar.role-admin {
  background-color: #FDF6E3;
  color: #B8860B;
  border: 1px solid #F0DCA0;
}

.user-avatar.role-enologo {
  background-color: #EDF4FC;
  color: #1A5296;
  border: 1px solid #B8D4F0;
}

.user-avatar.role-operario {
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border: 1px solid var(--status-good-border);
}

/* Info */
.user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.user-email {
  font-size: 0.75rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Badge de rol */
.user-role-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.65rem;
  border-radius: var(--radius-full);
  font-size: 0.73rem;
  font-weight: 600;
  flex-shrink: 0;
}

.user-role-badge.role-admin {
  background-color: #FDF6E3;
  color: #B8860B;
  border: 1px solid #F0DCA0;
}

.user-role-badge.role-enologo {
  background-color: #EDF4FC;
  color: #1A5296;
  border: 1px solid #B8D4F0;
}

.user-role-badge.role-operario {
  background-color: var(--status-good-bg);
  color: var(--status-good);
  border: 1px solid var(--status-good-border);
}

/* Estado */
.user-status {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.73rem;
  font-weight: 600;
  flex-shrink: 0;
  min-width: 72px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.status-active {
  color: var(--status-good);
}

.status-active .status-dot {
  background-color: var(--status-good);
}

.status-inactive {
  color: var(--text-muted);
}

.status-inactive .status-dot {
  background-color: var(--text-light);
}

/* Acciones */
.user-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

.action-edit-wrapper {
  position: relative;
}

.action-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all 0.12s ease;
}

.action-btn:hover {
  background-color: var(--bg-subtle);
  color: var(--text-primary);
}

.action-btn.action-suspend:hover {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
}

.action-btn.action-activate:hover {
  background-color: var(--status-good-bg);
  color: var(--status-good);
}

/* Dropdown de roles */
.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: all 0.15s ease;
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.role-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card), 0 8px 24px rgba(35, 22, 28, 0.1);
  z-index: 50;
  min-width: 180px;
  padding: 0.3rem;
  overflow: hidden;
}

.role-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.5rem 0.7rem;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all 0.1s ease;
  text-align: left;
}

.role-option:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.role-option.selected {
  background-color: var(--wine-50);
  color: var(--wine-800);
  font-weight: 600;
}

.check-icon {
  margin-left: auto;
  color: var(--wine-700);
}

/* =========================================
   MODAL
   ========================================= */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: all 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-from .modal-card,
.modal-fade-leave-to .modal-card {
  transform: translateY(12px) scale(0.97);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(35, 22, 28, 0.35);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 1.5rem;
}

.modal-card {
  width: 100%;
  max-width: 460px;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card), 0 16px 48px rgba(35, 22, 28, 0.15);
  overflow: hidden;
  transition: transform 0.2s ease;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
  background-color: var(--bg-subtle);
}

.modal-header h3 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--wine-800);
}

.modal-close {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all 0.12s ease;
}

.modal-close:hover {
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
}

.modal-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--border-subtle);
}

/* Campos del formulario */
.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.form-input {
  width: 100%;
  height: 40px;
  padding: 0 0.85rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.85rem;
  color: var(--text-primary);
  outline: none;
  transition: all 0.15s ease;
}

.form-input:focus {
  border-color: var(--wine-600);
  background-color: #FFFFFF;
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.08);
}

.form-input::placeholder {
  color: var(--text-light);
}

.input-icon-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 0.75rem;
  color: var(--text-muted);
  pointer-events: none;
}

.form-input.with-icon {
  padding-left: 2.3rem;
}

/* Selector de rol en modal */
.role-selector {
  display: flex;
  gap: 0.4rem;
}

.role-select-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  padding: 0.55rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  background-color: var(--bg-canvas);
  transition: all 0.12s ease;
}

.role-select-btn:hover {
  background-color: var(--bg-hover);
}

.role-select-btn.role-admin.active {
  background-color: #FDF6E3;
  border-color: #F0DCA0;
  color: #B8860B;
}

.role-select-btn.role-enologo.active {
  background-color: #EDF4FC;
  border-color: #B8D4F0;
  color: #1A5296;
}

.role-select-btn.role-operario.active {
  background-color: var(--status-good-bg);
  border-color: var(--status-good-border);
  color: var(--status-good);
}

/* =========================================
   ESTADO VACÍO
   ========================================= */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
  color: var(--text-muted);
  background-color: var(--bg-surface);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
}

.empty-state h3 {
  font-family: var(--font-serif);
  font-size: 1.3rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-top: 1rem;
  margin-bottom: 0.3rem;
}

.empty-state p {
  font-size: 0.86rem;
  max-width: 360px;
}

/* =========================================
   RESPONSIVE
   ========================================= */
@media (max-width: 680px) {
  .users-header {
    flex-direction: column;
  }

  .header-actions {
    padding-top: 0;
  }

  .user-row {
    flex-wrap: wrap;
    gap: 0.65rem;
  }

  .user-info {
    flex: 1 1 calc(100% - 54px);
  }

  .user-role-badge,
  .user-status {
    font-size: 0.7rem;
  }

  .user-actions {
    margin-left: auto;
  }

  .role-selector {
    flex-direction: column;
  }
}
</style>
