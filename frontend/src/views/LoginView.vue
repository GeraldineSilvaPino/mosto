<script setup>
/**
 * 📋 01. [FRONT - VUE] Pantalla de Inicio de Sesión
 * Módulo 1: Autenticación y Acceso
 *
 * Características implementadas:
 * 1. Formulario completo con campos de correo y contraseña validados visualmente.
 * 2. Simulación de autenticación local (mock de respuesta exitosa con token en localStorage).
 * 3. Botones rápidos para rellenar credenciales de demostración (Enólogo / Administrador).
 * 4. Redirección automática al Dashboard general al iniciar sesión exitosamente.
 * 5. Totalmente autónomo en el frontend (sin requerir backend activo).
 */

import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Grape,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ShieldCheck,
  Sparkles
} from 'lucide-vue-next'

const router = useRouter()

// Estado del formulario
const form = reactive({
  email: '',
  password: '',
  rememberMe: false
})

const touched = reactive({
  email: false,
  password: false
})

const showPassword = ref(false)
const isLoading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

// Validaciones en tiempo real
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const errors = computed(() => {
  const errs = {
    email: '',
    password: ''
  }

  if (touched.email) {
    if (!form.email.trim()) {
      errs.email = 'El correo electrónico es requerido.'
    } else if (!emailRegex.test(form.email.trim())) {
      errs.email = 'Ingresa un formato de correo válido (ej: usuario@mosto.cl).'
    }
  }

  if (touched.password) {
    if (!form.password) {
      errs.password = 'La contraseña es requerida.'
    } else if (form.password.length < 6) {
      errs.password = 'La contraseña debe tener al menos 6 caracteres.'
    }
  }

  return errs
})

const isFormValid = computed(() => {
  return (
    form.email.trim().length > 0 &&
    emailRegex.test(form.email.trim()) &&
    form.password.length >= 6
  )
})

// Acceso rápido con credenciales de prueba (Mock)
const setDemoCredentials = (role) => {
  errorMessage.value = ''
  successMessage.value = ''
  touched.email = true
  touched.password = true

  if (role === 'enologo') {
    form.email = 'enologo@mosto.cl'
    form.password = 'vinacura2024'
  } else if (role === 'admin') {
    form.email = 'admin@mosto.cl'
    form.password = 'bodega2024'
  }
}

// Proceso de autenticación simulada (Frontend Mock)
const handleLogin = async () => {
  // Marcar campos como tocados
  touched.email = true
  touched.password = true
  errorMessage.value = ''
  successMessage.value = ''

  if (!isFormValid.value) {
    errorMessage.value = 'Por favor completa los campos correctamente antes de continuar.'
    return
  }

  isLoading.value = true

  try {
    // Simulamos latencia de red de 750ms para una experiencia realista
    await new Promise((resolve) => setTimeout(resolve, 750))

    // Simulación de credencial de prueba rechazada (ejemplo intencional si escribe 'error@mosto.cl')
    if (form.email.toLowerCase() === 'error@mosto.cl') {
      throw new Error('Credenciales inválidas. Comprueba tu correo y contraseña.')
    }

    // Generar sesión simulada local (Mock Token)
    const mockToken = 'mock_jwt_mosto_' + Math.random().toString(36).substring(2) + Date.now()
    const mockUser = {
      name: form.email.includes('admin') ? 'Administrador General' : 'Enología & Control',
      email: form.email.trim(),
      role: form.email.includes('admin') ? 'Administrador' : 'Enólogo Jefe',
      winery: 'Viña Santa Emiliana',
      avatarInitial: form.email.substring(0, 2).toUpperCase()
    }

    if (form.rememberMe) {
      localStorage.setItem('mosto_auth_token', mockToken)
      localStorage.setItem('mosto_user', JSON.stringify(mockUser))
    } else {
      sessionStorage.setItem('mosto_auth_token', mockToken)
      sessionStorage.setItem('mosto_user', JSON.stringify(mockUser))
    }

    successMessage.value = '¡Credenciales verificadas! Entrando al sistema...'

    // Redirección al Dashboard tras breve confirmación visual
    setTimeout(() => {
      router.push('/')
    }, 600)
  } catch (err) {
    errorMessage.value = err.message || 'Error al iniciar sesión. Inténtalo nuevamente.'
  } finally {
    isLoading.value = false
  }
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

      <!-- Título de la vista -->
      <div class="auth-header-text">
        <h2>Iniciar Sesión</h2>
        <p>Ingresa tus credenciales para acceder a la gestión de cubas</p>
      </div>

      <!-- Mensaje de Error -->
      <transition name="fade">
        <div v-if="errorMessage" class="alert-box alert-error" role="alert">
          <AlertCircle :size="18" class="alert-icon" />
          <div class="alert-content">
            <span class="alert-text">{{ errorMessage }}</span>
          </div>
        </div>
      </transition>

      <!-- Mensaje de Éxito -->
      <transition name="fade">
        <div v-if="successMessage" class="alert-box alert-success" role="alert">
          <CheckCircle2 :size="18" class="alert-icon" />
          <div class="alert-content">
            <span class="alert-text">{{ successMessage }}</span>
          </div>
        </div>
      </transition>

      <!-- Formulario -->
      <form class="login-form" @submit.prevent="handleLogin" novalidate>
        <!-- Campo: Correo Electrónico -->
        <div class="form-group" :class="{ 'has-error': errors.email }">
          <label for="email" class="form-label">
            <span>Correo electrónico</span>
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
          <span v-if="errors.email" class="field-error-msg">
            {{ errors.email }}
          </span>
        </div>

        <!-- Campo: Contraseña -->
        <div class="form-group" :class="{ 'has-error': errors.password }">
          <div class="password-label-row">
            <label for="password" class="form-label">
              <span>Contraseña</span>
            </label>
            <router-link
              to="/recuperar-password"
              class="forgot-link"
              tabindex="0"
            >
              ¿Olvidaste tu contraseña?
            </router-link>
          </div>
          <div class="input-wrapper">
            <Lock :size="18" class="input-icon" />
            <input
              id="password"
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              class="form-input"
              placeholder="••••••••"
              autocomplete="current-password"
              :disabled="isLoading"
              @blur="touched.password = true"
            />
            <button
              type="button"
              class="toggle-password-btn"
              :title="showPassword ? 'Ocultar contraseña' : 'Ver contraseña'"
              :aria-label="showPassword ? 'Ocultar contraseña' : 'Ver contraseña'"
              tabindex="-1"
              @click="showPassword = !showPassword"
            >
              <EyeOff v-if="showPassword" :size="17" />
              <Eye v-else :size="17" />
            </button>
          </div>
          <span v-if="errors.password" class="field-error-msg">
            {{ errors.password }}
          </span>
        </div>

        <!-- Opciones adicionales: Recordar sesión -->
        <div class="form-options">
          <label class="remember-label">
            <input
              v-model="form.rememberMe"
              type="checkbox"
              class="checkbox-input"
              :disabled="isLoading"
            />
            <span class="checkbox-custom"></span>
            <span class="remember-text">Recordar en este equipo</span>
          </label>
        </div>

        <!-- Botón de Envío -->
        <button
          type="submit"
          class="submit-btn"
          :disabled="isLoading"
        >
          <Loader2 v-if="isLoading" :size="18" class="spin-icon" />
          <span v-if="isLoading">Verificando acceso...</span>
          <span v-else>Ingresar a la Plataforma</span>
          <ArrowRight v-if="!isLoading" :size="17" class="btn-arrow" />
        </button>
      </form>

      <!-- Atajos de Demostración (Mock Rápido) -->
      <div class="demo-section">
        <div class="demo-header">
          <Sparkles :size="14" class="demo-icon" />
          <span>Acceso rápido de demostración:</span>
        </div>
        <div class="demo-pills">
          <button
            type="button"
            class="demo-chip"
            :disabled="isLoading"
            @click="setDemoCredentials('enologo')"
          >
            <strong>Enólogo</strong> (enologo@mosto.cl)
          </button>
          <button
            type="button"
            class="demo-chip"
            :disabled="isLoading"
            @click="setDemoCredentials('admin')"
          >
            <strong>Admin</strong> (admin@mosto.cl)
          </button>
        </div>
      </div>

      <!-- Pie de Seguridad -->
      <div class="auth-card-footer">
        <ShieldCheck :size="14" class="shield-icon" />
        <span>Conexión segura de grado enológico · Mosto IoT v1.0</span>
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
  transition: transform 0.2s ease, box-shadow 0.2s ease;
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

/* Texto del encabezado */
.auth-header-text {
  text-align: center;
  margin-bottom: 1.75rem;
}

.auth-header-text h2 {
  font-family: var(--font-serif);
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}

.auth-header-text p {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

/* Alertas de Feedback */
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

.alert-success {
  background-color: var(--status-good-bg);
  border: 1px solid var(--status-good-border);
  color: var(--status-good);
}

.alert-icon {
  flex-shrink: 0;
  margin-top: 1px;
}

/* Formulario */
.login-form {
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

.password-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.forgot-link {
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--wine-700);
  transition: color 0.15s ease;
  text-decoration: none;
}

.forgot-link:hover {
  color: var(--wine-900);
  text-decoration: underline;
}

/* Wrappers de Input e Iconos */
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

/* Botón para alternar visibilidad de contraseña */
.toggle-password-btn {
  position: absolute;
  right: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem;
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  transition: color 0.15s ease;
}

.toggle-password-btn:hover {
  color: var(--text-primary);
}

/* Opciones: Checkbox */
.form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: -0.25rem;
}

.remember-label {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  user-select: none;
}

.checkbox-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.checkbox-custom {
  width: 17px;
  height: 17px;
  border: 1.5px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--bg-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.checkbox-input:checked + .checkbox-custom {
  background-color: var(--wine-700);
  border-color: var(--wine-700);
}

.checkbox-input:checked + .checkbox-custom::after {
  content: '';
  width: 5px;
  height: 9px;
  border: solid #FFFFFF;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg) translate(-0.5px, -1px);
}

.checkbox-input:focus-visible + .checkbox-custom {
  box-shadow: 0 0 0 3px rgba(118, 31, 51, 0.15);
}

.remember-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

/* Botón de Envío */
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
  margin-top: 0.35rem;
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

/* Atajos Demo */
.demo-section {
  margin-top: 1.75rem;
  padding-top: 1.25rem;
  border-top: 1px dashed var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.demo-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.74rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.demo-icon {
  color: var(--wine-600);
}

.demo-pills {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.demo-chip {
  flex: 1;
  min-width: 130px;
  font-size: 0.74rem;
  color: var(--text-secondary);
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-color);
  padding: 0.45rem 0.65rem;
  border-radius: var(--radius-sm);
  text-align: left;
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
  display: block;
  font-size: 0.76rem;
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

/* Animaciones */
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
