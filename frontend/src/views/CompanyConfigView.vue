<script setup>
/**
 * 📋 10. [FRONT - VUE] Pantalla de Configuración de la Empresa / Viña
 * Módulo 5: Administración SaaS y Gestión de Empresa
 * Rama recomendada: feature/10-configuracion-empresa
 *
 * Características implementadas:
 * 1. Ficha de identidad y bodega con previsualización reactiva de logotipo (carga de archivo local o restablecer).
 * 2. Datos fiscales reales chilenos (RUT, Razón Social, Giro, Dirección, Contacto).
 * 3. Tarjeta de plan SaaS con estado activo y barras de consumo de cuotas reales (9/24 cubas, 7/15 usuarios).
 * 4. Modal funcional e interactivo para solicitud de ampliación de cubas/cuota.
 * 5. Toggles operativos funcionales (reporte enológico, alertas SMS).
 * 6. Botones reactivos de Guardar (con toast de éxito) y Restablecer valores.
 * 7. 100% Frontend autónomo (sin requerir backend).
 */

import { ref, computed } from 'vue'
import {
  Building2,
  Grape,
  Camera,
  Trash2,
  Save,
  RotateCcw,
  Receipt,
  MapPin,
  Mail,
  Phone,
  ShieldCheck,
  Cylinder,
  Users,
  Zap,
  Calendar,
  X,
  Check,
  BellRing,
  Sparkles
} from 'lucide-vue-next'

// ==========================================
// ESTADO INICIAL / VALORES POR DEFECTO
// ==========================================
const defaultData = {
  // Identidad
  brandName: 'Viña Santa Emiliana',
  facility: 'Planta Principal · Bodega Central',
  valley: 'Valle del Maule',
  logoUrl: '', // Si está vacío se muestra el avatar estilizado vitivinícola
  
  // Fiscales
  taxId: '76.432.891-K',
  legalName: 'Agrícola y Vitivinícola Santa Emiliana S.A.',
  taxCategory: 'Elaboración y Envasado de Vinos y Mostos',
  address: 'Ruta K-60, Km 14.5, San Javier',
  region: 'Región del Maule, Chile',
  contactEmail: 'contacto@santaemiliana.cl',
  contactPhone: '+56 73 245 8890',

  // Operacionales
  dailyEnologyReport: true,
  smsCriticalAlerts: true
}

// Estado reactivo editable
const company = ref({ ...defaultData })

// Cuotas SaaS (Conectadas con los datos del Dashboard y Usuarios)
const saasQuota = ref({
  planName: 'Plan Bodega Industrial',
  billingCycle: 'Anual (Renovación: Nov 2027)',
  status: 'Activo',
  usedCubas: 9,
  maxCubas: 24,
  usedUsers: 7,
  maxUsers: 15
})

// Porcentajes de cuota
const cubasPercentage = computed(() => {
  return Math.round((saasQuota.value.usedCubas / saasQuota.value.maxCubas) * 100)
})

const usersPercentage = computed(() => {
  return Math.round((saasQuota.value.usedUsers / saasQuota.value.maxUsers) * 100)
})

// Control de cambios no guardados
const hasUnsavedChanges = computed(() => {
  return JSON.stringify(company.value) !== JSON.stringify(defaultData)
})

// ==========================================
// PREVISUALIZACIÓN DE LOGOTIPO
// ==========================================
const fileInput = ref(null)

const triggerFileInput = () => {
  if (fileInput.value) fileInput.value.click()
}

const handleLogoUpload = (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    company.value.logoUrl = e.target.result
  }
  reader.readAsDataURL(file)
}

const removeLogo = () => {
  company.value.logoUrl = ''
  if (fileInput.value) fileInput.value.value = ''
}

// ==========================================
// GUARDAR Y RESTABLECER
// ==========================================
const isSaving = ref(false)
const showToast = ref(false)
const toastMessage = ref('')

const saveChanges = () => {
  isSaving.value = true
  setTimeout(() => {
    isSaving.value = false
    // Sincronizar estado por defecto
    Object.assign(defaultData, { ...company.value })
    toastMessage.value = 'Configuración de la viña actualizada correctamente'
    showToast.value = true
    setTimeout(() => {
      showToast.value = false
    }, 3500)
  }, 450)
}

const resetChanges = () => {
  company.value = { ...defaultData }
}

// ==========================================
// MODAL DE AMPLIACIÓN DE CUOTA
// ==========================================
const showUpgradeModal = ref(false)
const requestedExtraCubas = ref(6)
const isSubmittingUpgrade = ref(false)

const openUpgradeModal = () => {
  requestedExtraCubas.value = 6
  showUpgradeModal.value = true
}

const confirmUpgrade = () => {
  isSubmittingUpgrade.value = true
  setTimeout(() => {
    saasQuota.value.maxCubas += requestedExtraCubas.value
    isSubmittingUpgrade.value = false
    showUpgradeModal.value = false
    toastMessage.value = `Capacidad ampliada a ${saasQuota.value.maxCubas} cubas en monitoreo`
    showToast.value = true
    setTimeout(() => {
      showToast.value = false
    }, 3500)
  }, 500)
}
</script>

<template>
  <div class="company-config-page">
    <!-- Notificación Toast reactiva -->
    <transition name="toast-pop">
      <div v-if="showToast" class="toast-feedback">
        <Check :size="16" class="toast-icon" />
        <span>{{ toastMessage }}</span>
      </div>
    </transition>

    <!-- Encabezado con Botones de Acción Funcionales -->
    <header class="config-header">
      <div>
        <div class="header-pretitle">
          <Building2 :size="14" />
          <span>Ficha de la Empresa</span>
        </div>
        <h1 class="header-title">Configuración de la Viña</h1>
        <p class="header-description">
          Administración de los datos fiscales, marca y capacidad contratada en la plataforma MOSTO.
        </p>
      </div>

      <div class="header-actions">
        <button
          type="button"
          class="btn-reset"
          :disabled="!hasUnsavedChanges || isSaving"
          @click="resetChanges"
          title="Deshacer cambios no guardados"
        >
          <RotateCcw :size="15" />
          <span>Restablecer</span>
        </button>

        <button
          type="button"
          class="btn-save"
          :class="{ 'is-loading': isSaving }"
          :disabled="isSaving || !hasUnsavedChanges"
          @click="saveChanges"
        >
          <Save :size="15" />
          <span>{{ isSaving ? 'Guardando...' : 'Guardar' }}</span>
        </button>
      </div>
    </header>

    <!-- Layout en 2 columnas: Datos (Izquierda) y SaaS/Operación (Derecha) -->
    <div class="config-grid">
      <!-- Columna Principal: Identidad y Datos Fiscales -->
      <div class="grid-column-main">
        <!-- Tarjeta de Identidad y Logotipo -->
        <section class="config-card">
          <div class="card-header">
            <div class="card-header-title">
              <Grape :size="18" class="header-icon" />
              <h2>Identidad de la Bodega</h2>
            </div>
            <span class="badge-tag">{{ company.valley }}</span>
          </div>

          <div class="card-body">
            <!-- Selector de Logo reactivo -->
            <div class="logo-uploader-row">
              <div class="logo-preview-box">
                <img
                  v-if="company.logoUrl"
                  :src="company.logoUrl"
                  alt="Logotipo de la viña"
                  class="logo-image"
                />
                <div v-else class="logo-placeholder">
                  <Grape :size="28" :stroke-width="1.8" />
                  <span class="logo-placeholder-text">Sin Logo</span>
                </div>
              </div>

              <div class="logo-actions">
                <input
                  ref="fileInput"
                  type="file"
                  accept="image/png, image/jpeg, image/webp, image/svg+xml"
                  class="file-hidden-input"
                  @change="handleLogoUpload"
                />
                <div class="logo-buttons">
                  <button type="button" class="btn-action-sm" @click="triggerFileInput">
                    <Camera :size="14" />
                    <span>Subir Logo</span>
                  </button>
                  <button
                    v-if="company.logoUrl"
                    type="button"
                    class="btn-action-sm btn-danger"
                    @click="removeLogo"
                  >
                    <Trash2 :size="14" />
                    <span>Quitar</span>
                  </button>
                </div>
                <span class="logo-hint">Formatos PNG, JPG o SVG (máx. 2MB)</span>
              </div>
            </div>

            <!-- Campos de Identidad -->
            <div class="form-row-2">
              <div class="form-field">
                <label class="form-label">
                  <Building2 :size="13" />
                  <span>Nombre Comercial</span>
                </label>
                <input
                  v-model="company.brandName"
                  type="text"
                  class="form-input"
                  placeholder="Ej: Viña Santa Emiliana"
                />
              </div>

              <div class="form-field">
                <label class="form-label">
                  <MapPin :size="13" />
                  <span>Valle Vitivinícola</span>
                </label>
                <input
                  v-model="company.valley"
                  type="text"
                  class="form-input"
                  placeholder="Ej: Valle del Maule"
                />
              </div>
            </div>

            <div class="form-field">
              <label class="form-label">
                <Grape :size="13" />
                <span>Instalación / Sede</span>
              </label>
              <input
                v-model="company.facility"
                type="text"
                class="form-input"
                placeholder="Planta Principal · Bodega Central"
              />
            </div>
          </div>
        </section>

        <!-- Tarjeta de Datos Fiscales y Facturación -->
        <section class="config-card">
          <div class="card-header">
            <div class="card-header-title">
              <Receipt :size="18" class="header-icon" />
              <h2>Datos Fiscales y Contacto</h2>
            </div>
            <span class="badge-country">CL</span>
          </div>

          <div class="card-body">
            <div class="form-row-2">
              <div class="form-field">
                <label class="form-label">
                  <Receipt :size="13" />
                  <span>RUT Empresa</span>
                </label>
                <input
                  v-model="company.taxId"
                  type="text"
                  class="form-input mono-font"
                  placeholder="76.xxx.xxx-x"
                />
              </div>

              <div class="form-field">
                <label class="form-label">
                  <Building2 :size="13" />
                  <span>Razón Social</span>
                </label>
                <input
                  v-model="company.legalName"
                  type="text"
                  class="form-input"
                  placeholder="Razón Social Legal"
                />
              </div>
            </div>

            <div class="form-field">
              <label class="form-label">
                <Receipt :size="13" />
                <span>Giro Comercial</span>
              </label>
              <input
                v-model="company.taxCategory"
                type="text"
                class="form-input"
                placeholder="Giro según SII"
              />
            </div>

            <div class="form-row-2">
              <div class="form-field">
                <label class="form-label">
                  <MapPin :size="13" />
                  <span>Dirección Bodega</span>
                </label>
                <input
                  v-model="company.address"
                  type="text"
                  class="form-input"
                  placeholder="Ruta y kilómetro"
                />
              </div>

              <div class="form-field">
                <label class="form-label">
                  <MapPin :size="13" />
                  <span>Comuna y Región</span>
                </label>
                <input
                  v-model="company.region"
                  type="text"
                  class="form-input"
                  placeholder="San Javier, Maule"
                />
              </div>
            </div>

            <div class="form-row-2">
              <div class="form-field">
                <label class="form-label">
                  <Mail :size="13" />
                  <span>Correo Administrativo</span>
                </label>
                <input
                  v-model="company.contactEmail"
                  type="email"
                  class="form-input"
                  placeholder="contacto@bodega.cl"
                />
              </div>

              <div class="form-field">
                <label class="form-label">
                  <Phone :size="13" />
                  <span>Teléfono Central</span>
                </label>
                <input
                  v-model="company.contactPhone"
                  type="tel"
                  class="form-input mono-font"
                  placeholder="+56 ..."
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- Columna Lateral: Estado SaaS y Preferencias -->
      <div class="grid-column-side">
        <!-- Tarjeta de Plan SaaS -->
        <section class="config-card saas-card">
          <div class="card-header">
            <div class="card-header-title">
              <ShieldCheck :size="18" class="header-icon wine" />
              <h2>Estado del Servicio</h2>
            </div>
            <div class="status-pill-good">
              <span class="status-dot"></span>
              <span>{{ saasQuota.status }}</span>
            </div>
          </div>

          <div class="card-body">
            <div class="plan-hero">
              <div class="plan-info">
                <span class="plan-badge">{{ saasQuota.planName }}</span>
                <div class="plan-cycle">
                  <Calendar :size="12" />
                  <span>{{ saasQuota.billingCycle }}</span>
                </div>
              </div>
            </div>

            <!-- Cuota de Cubas -->
            <div class="quota-block">
              <div class="quota-meta">
                <div class="quota-label">
                  <Cylinder :size="14" class="quota-icon" />
                  <span>Capacidad de Cubas</span>
                </div>
                <span class="quota-count">
                  <strong>{{ saasQuota.usedCubas }}</strong> / {{ saasQuota.maxCubas }}
                </span>
              </div>
              <div class="progress-track">
                <div
                  class="progress-fill wine"
                  :style="{ width: `${cubasPercentage}%` }"
                ></div>
              </div>
              <span class="quota-percent">{{ cubasPercentage }}% de cubas conectadas</span>
            </div>

            <!-- Cuota de Usuarios -->
            <div class="quota-block">
              <div class="quota-meta">
                <div class="quota-label">
                  <Users :size="14" class="quota-icon" />
                  <span>Cuentas de Personal</span>
                </div>
                <span class="quota-count">
                  <strong>{{ saasQuota.usedUsers }}</strong> / {{ saasQuota.maxUsers }}
                </span>
              </div>
              <div class="progress-track">
                <div
                  class="progress-fill navy"
                  :style="{ width: `${usersPercentage}%` }"
                ></div>
              </div>
              <span class="quota-percent">{{ usersPercentage }}% de usuarios registrados</span>
            </div>

            <!-- Botón interactivo de ampliación -->
            <button type="button" class="btn-upgrade" @click="openUpgradeModal">
              <Zap :size="15" />
              <span>Solicitar Ampliación</span>
            </button>
          </div>
        </section>

        <!-- Ajustes Operativos y Notificaciones -->
        <section class="config-card">
          <div class="card-header">
            <div class="card-header-title">
              <BellRing :size="18" class="header-icon" />
              <h2>Canales Operativos</h2>
            </div>
          </div>

          <div class="card-body switches-list">
            <label class="switch-item">
              <div class="switch-info">
                <span class="switch-title">Reporte Diario a Enología</span>
                <span class="switch-desc">Envío de resumen consolidado a las 07:00 hrs.</span>
              </div>
              <input
                v-model="company.dailyEnologyReport"
                type="checkbox"
                class="switch-input"
              />
              <span class="switch-slider"></span>
            </label>

            <label class="switch-item">
              <div class="switch-info">
                <span class="switch-title">Alertas Críticas por SMS</span>
                <span class="switch-desc">Notificar de inmediato ante paradas o sobrecalentamiento.</span>
              </div>
              <input
                v-model="company.smsCriticalAlerts"
                type="checkbox"
                class="switch-input"
              />
              <span class="switch-slider"></span>
            </label>
          </div>
        </section>
      </div>
    </div>

    <!-- Modal de Ampliación de Capacidad -->
    <transition name="modal-fade">
      <div v-if="showUpgradeModal" class="modal-overlay" @click.self="showUpgradeModal = false">
        <div class="modal-card">
          <div class="modal-header">
            <h3>
              <Sparkles :size="18" class="modal-icon-sparkle" />
              Ampliación de Capacidad
            </h3>
            <button type="button" class="modal-close" @click="showUpgradeModal = false">
              <X :size="16" />
            </button>
          </div>

          <div class="modal-body">
            <p class="modal-lead">
              Selecciona el paquete de cubas telemétricas adicionales para incorporar a
              <strong>{{ company.brandName }}</strong>.
            </p>

            <div class="cubas-selector-grid">
              <button
                v-for="qty in [6, 12, 24]"
                :key="qty"
                type="button"
                class="cuba-option-btn"
                :class="{ active: requestedExtraCubas === qty }"
                @click="requestedExtraCubas = qty"
              >
                <Cylinder :size="18" />
                <span class="option-qty">+{{ qty }} Cubas</span>
                <span class="option-label">Sensor DS18B20 + MPU</span>
              </button>
            </div>

            <div class="upgrade-summary">
              <div class="summary-row">
                <span>Capacidad Actual:</span>
                <strong>{{ saasQuota.maxCubas }} Cubas</strong>
              </div>
              <div class="summary-row highlight">
                <span>Nueva Capacidad:</span>
                <strong>{{ saasQuota.maxCubas + requestedExtraCubas }} Cubas</strong>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="showUpgradeModal = false">
              Cancelar
            </button>
            <button
              type="button"
              class="btn-primary"
              :disabled="isSubmittingUpgrade"
              @click="confirmUpgrade"
            >
              <Check :size="15" />
              <span>{{ isSubmittingUpgrade ? 'Procesando...' : 'Confirmar Ampliación' }}</span>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
/* =========================================
   PÁGINA DE CONFIGURACIÓN - LAYOUT GENERAL
   ========================================= */
.company-config-page {
  max-width: 1040px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  position: relative;
}

/* =========================================
   TOAST DE CONFIRMACIÓN FLOTANTE
   ========================================= */
.toast-feedback {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  background-color: var(--wine-900);
  color: #FFFFFF;
  padding: 0.75rem 1.25rem;
  border-radius: var(--radius-md);
  box-shadow: 0 10px 30px rgba(35, 22, 28, 0.25);
  font-size: 0.86rem;
  font-weight: 500;
  z-index: 200;
}

.toast-icon {
  color: #55D48E;
  flex-shrink: 0;
}

.toast-pop-enter-active,
.toast-pop-leave-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-pop-enter-from,
.toast-pop-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.95);
}

/* =========================================
   ENCABEZADO
   ========================================= */
.config-header {
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
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-shrink: 0;
  padding-top: 0.35rem;
}

.btn-reset {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.55rem 0.95rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 600;
  transition: all 0.15s ease;
  cursor: pointer;
}

.btn-reset:hover:not(:disabled) {
  background-color: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--text-muted);
}

.btn-reset:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-save {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  background-color: var(--wine-700);
  color: #FFFFFF;
  padding: 0.55rem 1.25rem;
  border-radius: var(--radius-sm);
  font-size: 0.84rem;
  font-weight: 600;
  transition: all 0.15s ease;
  cursor: pointer;
}

.btn-save:hover:not(:disabled) {
  background-color: var(--wine-800);
  transform: translateY(-1px);
}

.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* =========================================
   GRID PRINCIPAL
   ========================================= */
.config-grid {
  display: grid;
  grid-template-columns: 1.55fr 1fr;
  gap: 1.5rem;
  align-items: flex-start;
}

.grid-column-main,
.grid-column-side {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* =========================================
   TARJETAS DE CONFIGURACIÓN
   ========================================= */
.config-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-subtle);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.95rem 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
  background-color: var(--bg-subtle);
}

.card-header-title {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.card-header-title h2 {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--wine-900);
}

.header-icon {
  color: var(--text-muted);
}

.header-icon.wine {
  color: var(--wine-700);
}

.card-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

.badge-tag {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--wine-700);
  background-color: var(--wine-50);
  border: 1px solid var(--wine-100);
  padding: 0.15rem 0.55rem;
  border-radius: var(--radius-full);
}

.badge-country {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--text-secondary);
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  padding: 0.1rem 0.45rem;
  border-radius: var(--radius-sm);
}

/* =========================================
   SUBIDOR DE LOGO
   ========================================= */
.logo-uploader-row {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px dashed var(--border-subtle);
}

.logo-preview-box {
  width: 76px;
  height: 76px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background-color: var(--bg-canvas);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

.logo-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.logo-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--wine-700);
  gap: 0.25rem;
}

.logo-placeholder-text {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted);
}

.file-hidden-input {
  display: none;
}

.logo-actions {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.logo-buttons {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.btn-action-sm {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.75rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.12s ease;
}

.btn-action-sm:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--text-muted);
}

.btn-action-sm.btn-danger:hover {
  background-color: var(--status-danger-bg);
  border-color: var(--status-danger-border);
  color: var(--status-danger);
}

.logo-hint {
  font-size: 0.72rem;
  color: var(--text-muted);
}

/* =========================================
   FORMULARIOS
   ========================================= */
.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.form-input {
  width: 100%;
  height: 38px;
  padding: 0 0.85rem;
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.84rem;
  color: var(--text-primary);
  outline: none;
  transition: all 0.15s ease;
}

.form-input:focus {
  border-color: var(--wine-600);
  background-color: #FFFFFF;
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.08);
}

.form-input.mono-font {
  font-family: var(--font-mono);
  font-size: 0.82rem;
}

/* =========================================
   COLUMNA LATERAL (SAAS Y CUOTAS)
   ========================================= */
.status-pill-good {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--status-good);
  background-color: var(--status-good-bg);
  border: 1px solid var(--status-good-border);
  padding: 0.15rem 0.55rem;
  border-radius: var(--radius-full);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--status-good);
}

.plan-hero {
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 0.85rem 1rem;
}

.plan-info {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.plan-badge {
  font-family: var(--font-serif);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wine-900);
}

.plan-cycle {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.73rem;
  color: var(--text-muted);
}

/* Barras de progreso de cuotas */
.quota-block {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.quota-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.quota-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-primary);
}

.quota-icon {
  color: var(--text-muted);
}

.quota-count {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.quota-count strong {
  color: var(--wine-800);
}

.progress-track {
  width: 100%;
  height: 7px;
  background-color: var(--bg-subtle);
  border-radius: var(--radius-full);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}

.progress-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.4s ease;
}

.progress-fill.wine {
  background-color: var(--wine-700);
}

.progress-fill.navy {
  background-color: #1A5296;
}

.quota-percent {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.btn-upgrade {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  width: 100%;
  padding: 0.6rem 1rem;
  background-color: var(--wine-50);
  border: 1px dashed var(--wine-700);
  border-radius: var(--radius-sm);
  color: var(--wine-800);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  margin-top: 0.35rem;
}

.btn-upgrade:hover {
  background-color: var(--wine-100);
  border-style: solid;
}

/* =========================================
   SWITCHES OPERATIVOS
   ========================================= */
.switches-list {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.switch-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  cursor: pointer;
  position: relative;
}

.switch-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
}

.switch-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.switch-desc {
  font-size: 0.73rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.switch-input {
  display: none;
}

.switch-slider {
  width: 38px;
  height: 22px;
  background-color: var(--border-color);
  border-radius: var(--radius-full);
  position: relative;
  transition: background-color 0.2s ease;
  flex-shrink: 0;
}

.switch-slider::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background-color: #FFFFFF;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  transition: transform 0.2s ease;
}

.switch-input:checked + .switch-slider {
  background-color: var(--wine-700);
}

.switch-input:checked + .switch-slider::after {
  transform: translateX(16px);
}

/* =========================================
   MODAL DE AMPLIACIÓN
   ========================================= */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: all 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(35, 22, 28, 0.4);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 120;
  padding: 1.5rem;
}

.modal-card {
  width: 100%;
  max-width: 480px;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card), 0 16px 48px rgba(35, 22, 28, 0.15);
  overflow: hidden;
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

.modal-icon-sparkle {
  color: var(--wine-700);
}

.modal-close {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
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
  gap: 1.1rem;
}

.modal-lead {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

.cubas-selector-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.65rem;
}

.cuba-option-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 0.85rem 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background-color: var(--bg-canvas);
  color: var(--text-secondary);
  gap: 0.35rem;
  cursor: pointer;
  transition: all 0.12s ease;
}

.cuba-option-btn:hover {
  background-color: var(--bg-hover);
  border-color: var(--text-muted);
}

.cuba-option-btn.active {
  background-color: var(--wine-50);
  border-color: var(--wine-700);
  color: var(--wine-800);
}

.option-qty {
  font-family: var(--font-mono);
  font-size: 0.88rem;
  font-weight: 700;
}

.option-label {
  font-size: 0.65rem;
  color: var(--text-muted);
}

.upgrade-summary {
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.summary-row.highlight {
  font-weight: 600;
  color: var(--wine-800);
  padding-top: 0.35rem;
  border-top: 1px dashed var(--border-color);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--border-subtle);
}

/* =========================================
   RESPONSIVE
   ========================================= */
@media (max-width: 860px) {
  .config-grid {
    grid-template-columns: 1fr;
  }

  .form-row-2 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .config-header {
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .logo-uploader-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
