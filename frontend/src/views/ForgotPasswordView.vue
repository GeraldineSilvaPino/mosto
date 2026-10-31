<script setup>
/**
 * 📋 02. [FRONT - VUE] Pantalla de Recuperación de Contraseña
 * Módulo 1: Autenticación y Acceso
 *
 * Características implementadas:
 * 1. Campo de correo electrónico con validación de formato visual en tiempo real.
 * 2. Simulación de envío con feedback visual de carga (loading spinner).
 * 3. Tarjeta de éxito interactiva con confirmación del correo al que se envió el enlace.
 * 4. Botón de reenvío/reintento y enlace fluido de regreso a Login.
 * 5. Acceso rápido con correo de demostración.
 * 6. 100% Frontend sin dependencias del backend.
 */

import { ref, reactive, computed } from 'vue'
import {
  Grape,
  Mail,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ShieldCheck,
  RotateCcw,
  Sparkles
} from 'lucide-vue-next'

const form = reactive({
  email: ''
})

const touched = reactive({
  email: false
})

const isLoading = ref(false)
const isSubmitted = ref(false)
const errorMessage = ref('')
const sentEmail = ref('')

// Validación de correo electrónico
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const emailError = computed(() => {
  if (!touched.email) return ''
  if (!form.email.trim()) return 'El correo electrónico es requerido.'
  if (!emailRegex.test(form.email.trim())) {
    return 'Ingresa un formato de correo válido (ej: usuario@mosto.cl).'
  }
  return ''
})

const isFormValid = computed(() => {
  return form.email.trim().length > 0 && emailRegex.test(form.email.trim())
})

// Acceso rápido con credencial demo
const fillDemoEmail = () => {
  form.email = 'enologo@mosto.cl'
  touched.email = true
  errorMessage.value = ''
}

// Envío simulado (Frontend Mock)
const handleRecoverPassword = async () => {
  touched.email = true
  errorMessage.value = ''

  if (!isFormValid.value) {
    errorMessage.value = 'Por favor ingresa un correo electrónico válido.'
    return
  }

  isLoading.value = true

  try {
    // Simular latencia de red de 750ms
    await new Promise((resolve) => setTimeout(resolve, 750))

    // Guardar el correo al que se le envió para el mensaje de confirmación
    sentEmail.value = form.email.trim()
    isSubmitted.value = true
  } catch (err) {
    errorMessage.value = 'Ocurrió un error al procesar la solicitud. Intenta nuevamente.'
  } finally {
    isLoading.value = false
  }
}

// Restablecer vista para reenviar o ingresar otro correo
const resetForm = () => {
  isSubmitted.value = false
  form.email = ''
  touched.email = false
  errorMessage.value = ''
  sentEmail.value = ''
}
</script>

<template>
  <div class="auth-container">
    <div class="auth-card">
      <!-- Encabezado de Marca -->
      <div class="brand-section">
        <div class="brand-badge">
          <div class="brand-icon-box">
            <Grape :size="24" :stroke-width="1.8" />
          </div>
          <span class="brand-live-pulse" title="Sistema Activo"></span>
        </div>
        <div class="brand-title">mosto<span>.</span></div>
        <p class="brand-subtitle">Plataforma Vitivinícola · Monitoreo y Control</p>
      </div>

      <!-- ESTADO 1: FORMULARIO DE ENVÍO -->
      <div v-if="!isSubmitted">
        <!-- Título de la vista -->
        <div class="auth-header-text">
          <h2>Recuperar Contraseña</h2>
          <p>
            Ingresa tu correo asociado y te enviaremos las instrucciones para restablecer tu acceso.
          </p>
        </div>

        <!-- Alerta de Error -->
        <transition name="fade">
          <div v-if="errorMessage" class="alert-box alert-error" role="alert">
            <AlertCircle :size="18" class="alert-icon" />
            <div class="alert-content">
              <span class="alert-text">{{ errorMessage }}</span>
            </div>
          </div>
        </transition>

        <!-- Formulario -->
        <form class="recover-form" @submit.prevent="handleRecoverPassword" novalidate>
          <div class="form-group" :class="{ 'has-error': emailError }">
            <label for="email" class="form-label">
              <span>Correo electrónico registrado</span>
            </label>
            <div class="input-wrapper">
              <Mail :size="18" class="input-icon" />
              <input
                id="email"
                v-model="form.email"
                type="email"
                name="email"
                class="form-input"
                placeholder="ejemplo@mosto.cl"
                autocomplete="email"
                :disabled="isLoading"
                @blur="touched.email = true"
              />
            </div>
            <span v-if="emailError" class="field-error-msg">
              {{ emailError }}
            </span>
          </div>

          <!-- Botón de Envío -->
          <button
            type="submit"
            class="submit-btn"
            :disabled="isLoading"
          >
            <Loader2 v-if="isLoading" :size="18" class="spin-icon" />
            <span v-if="isLoading">Enviando instrucciones...</span>
            <span v-else>Enviar Enlace de Recuperación</span>
            <ArrowRight v-if="!isLoading" :size="17" class="btn-arrow" />
          </button>
        </form>

        <!-- Atajo de Demostración -->
        <div class="demo-section">
          <div class="demo-header">
            <Sparkles :size="14" class="demo-icon" />
            <span>Prueba rápida:</span>
          </div>
          <button
            type="button"
            class="demo-chip"
            :disabled="isLoading"
            @click="fillDemoEmail"
          >
            Usar correo de prueba: <strong>enologo@mosto.cl</strong>
          </button>
        </div>

        <!-- Enlace para volver al Login -->
        <div class="back-link-wrapper">
          <router-link to="/login" class="back-link">
            <ArrowLeft :size="16" />
            <span>Volver al inicio de sesión</span>
          </router-link>
        </div>
      </div>

      <!-- ESTADO 2: FEEDBACK VISUAL DE ÉXITO (Simulación enviada) -->
      <div v-else class="success-view">
        <div class="success-icon-badge">
          <CheckCircle2 :size="38" :stroke-width="2" />
        </div>

        <div class="auth-header-text">
          <h2 class="success-title">¡Enlace Enviado!</h2>
          <p class="success-description">
            Hemos enviado un correo seguro con el enlace para restablecer tu contraseña a:
          </p>
          <div class="target-email-badge">
            <Mail :size="15" />
            <strong>{{ sentEmail }}</strong>
          </div>
        </div>

        <div class="info-notice">
          <p>
            Por favor revisa tu bandeja de entrada y la carpeta de spam. El enlace tiene una validez de <strong>60 minutos</strong> por seguridad.
          </p>
        </div>

        <div class="action-buttons">
          <router-link to="/login" class="submit-btn return-btn">
            <ArrowLeft :size="16" />
            <span>Ir al Inicio de Sesión</span>
          </router-link>

          <button
            type="button"
            class="btn-text-resend"
            @click="resetForm"
          >
            <RotateCcw :size="14" />
            <span>¿No recibiste el correo? Intentar nuevamente</span>
          </button>
        </div>
      </div>

      <!-- Pie de Seguridad -->
      <div class="auth-card-footer">
        <ShieldCheck :size="14" class="shield-icon" />
        <span>Protocolo de autenticación enológica · Mosto IoT</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Contenedor y Tarjeta Principal */
.auth-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 50% 20%, #FFFDFB 0%, var(--bg-canvas) 70%, #F5ECE8 100%);
  padding: 1.5rem;
}

.auth-card {
  width: 100%;
  max-width: 440px;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 2.5rem 2.25rem;
  box-shadow: 0 10px 30px rgba(48, 12, 21, 0.06), 0 1px 3px rgba(35, 22, 28, 0.04);
}

/* Sección de Marca */
.brand-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 1.5rem;
}

.brand-badge {
  position: relative;
  display: inline-block;
  margin-bottom: 0.65rem;
}

.brand-icon-box {
  width: 52px;
  height: 52px;
  background: linear-gradient(135deg, var(--wine-100) 0%, var(--wine-50) 100%);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--wine-700);
  box-shadow: 0 4px 10px rgba(92, 24, 40, 0.08);
}

.brand-live-pulse {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 10px;
  height: 10px;
  background-color: var(--status-good);
  border: 2px solid #FFFFFF;
  border-radius: 50%;
  box-shadow: 0 0 0 2px rgba(42, 102, 68, 0.2);
}

.brand-title {
  font-family: var(--font-serif);
  font-size: 2.25rem;
  font-weight: 700;
  color: var(--wine-900);
  line-height: 1;
  letter-spacing: -0.02em;
}

.brand-title span {
  color: var(--wine-600);
}

.brand-subtitle {
  font-size: 0.76rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-top: 0.35rem;
}

/* Encabezados de Texto */
.auth-header-text {
  text-align: center;
  margin-bottom: 1.5rem;
}

.auth-header-text h2 {
  font-family: var(--font-serif);
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.35rem;
}

.auth-header-text p {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.45;
}

/* Alerta de Error */
.alert-box {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.75rem 0.9rem;
  border-radius: var(--radius-sm);
  font-size: 0.83rem;
  line-height: 1.4;
  margin-bottom: 1.25rem;
}

.alert-error {
  background-color: var(--status-danger-bg);
  border: 1px solid var(--status-danger-border);
  color: var(--status-danger);
}

.alert-icon {
  flex-shrink: 0;
  margin-top: 1px;
}

/* Formulario */
.recover-form {
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 0.85rem;
  color: var(--text-muted);
  pointer-events: none;
  transition: color 0.15s ease;
}

.form-input {
  width: 100%;
  height: 44px;
  padding: 0 0.85rem 0 2.5rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.9rem;
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
}

.form-input::placeholder {
  color: var(--text-light);
}

.form-input:focus {
  border-color: var(--wine-600);
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.12);
  background-color: #FFFFFF;
}

.input-wrapper:focus-within .input-icon {
  color: var(--wine-700);
}

.has-error .form-input {
  border-color: var(--status-danger);
  background-color: var(--status-danger-bg);
}

.has-error .input-icon {
  color: var(--status-danger);
}

.field-error-msg {
  font-size: 0.74rem;
  font-weight: 500;
  color: var(--status-danger);
  margin-top: 0.15rem;
}

/* Botón Principal */
.submit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  height: 46px;
  background-color: var(--wine-700);
  color: #FFFFFF;
  border-radius: var(--radius-sm);
  font-size: 0.92rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  transition: background-color 0.15s ease, transform 0.1s ease, box-shadow 0.15s ease;
  box-shadow: 0 4px 12px rgba(92, 24, 40, 0.2);
  margin-top: 0.25rem;
}

.submit-btn:hover:not(:disabled) {
  background-color: var(--wine-800);
  box-shadow: 0 6px 16px rgba(92, 24, 40, 0.28);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn-arrow {
  transition: transform 0.15s ease;
}

.submit-btn:hover:not(:disabled) .btn-arrow {
  transform: translateX(3px);
}

.spin-icon {
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Demo chip */
.demo-section {
  margin-top: 1.5rem;
  padding-top: 1.1rem;
  border-top: 1px dashed var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.demo-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.73rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.demo-icon {
  color: var(--wine-600);
}

.demo-chip {
  width: 100%;
  font-size: 0.76rem;
  color: var(--text-secondary);
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-color);
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-sm);
  text-align: center;
  transition: all 0.12s ease;
  cursor: pointer;
}

.demo-chip:hover {
  background-color: var(--wine-50);
  border-color: var(--wine-100);
  color: var(--wine-900);
}

.demo-chip strong {
  color: var(--wine-800);
}

/* Enlace Volver */
.back-link-wrapper {
  margin-top: 1.25rem;
  display: flex;
  justify-content: center;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--wine-700);
  transition: color 0.15s ease;
  text-decoration: none;
}

.back-link:hover {
  color: var(--wine-900);
  text-decoration: underline;
}

/* ESTADO DE ÉXITO */
.success-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 0.5rem 0;
}

.success-icon-badge {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-full);
  background-color: var(--status-good-bg);
  border: 1px solid var(--status-good-border);
  color: var(--status-good);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.25rem;
  animation: pulse-badge 2s infinite ease-in-out;
}

@keyframes pulse-badge {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(42, 102, 68, 0.2);
  }
  50% {
    transform: scale(1.04);
    box-shadow: 0 0 0 8px rgba(42, 102, 68, 0);
  }
}

.success-title {
  color: var(--wine-900);
  font-family: var(--font-serif);
}

.success-description {
  margin-bottom: 0.75rem;
}

.target-email-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-color);
  padding: 0.4rem 0.85rem;
  border-radius: var(--radius-full);
  font-size: 0.82rem;
  color: var(--wine-800);
  margin-top: 0.35rem;
}

.info-notice {
  background-color: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 0.85rem 1rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.45;
  margin: 1.25rem 0;
  text-align: center;
}

.action-buttons {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.return-btn {
  margin-top: 0;
}

.btn-text-resend {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  font-size: 0.78rem;
  color: var(--text-muted);
  padding: 0.4rem;
  transition: color 0.15s ease;
}

.btn-text-resend:hover {
  color: var(--wine-800);
  text-decoration: underline;
}

/* Pie de Tarjeta */
.auth-card-footer {
  margin-top: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.shield-icon {
  color: var(--status-good);
}

/* Transiciones */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
