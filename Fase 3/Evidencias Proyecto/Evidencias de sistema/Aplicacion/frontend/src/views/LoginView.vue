<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Eye, EyeOff, Loader2 } from 'lucide-vue-next'
import AuthLayout from '../layouts/AuthLayout.vue'
import authService from '../services/authService'

const router = useRouter()
const form = reactive({ email: '', password: '', rememberMe: false })
const touched = reactive({ email: false, password: false })
const emailInput = ref(null)
const passwordInput = ref(null)
const submitButton = ref(null)
const showPassword = ref(false)
const isLoading = ref(false)
const errorMessage = ref('')
const demoMessage = ref('')

const demoProfiles = import.meta.env.DEV ? [
  { label: 'Enólogo', email: 'enologo@mosto.cl', password: 'vinacura2024' },
  { label: 'Admin', email: 'admin@mosto.cl', password: 'bodega2024' },
  { label: 'Operador', email: 'operador@mosto.cl', password: 'operador2024' }
] : []
const emailError = computed(() => {
  if (!touched.email) return ''
  if (!form.email.trim()) return 'Ingresa tu correo electrónico.'
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()) ? '' : 'Revisa el formato del correo electrónico.'
})
const passwordError = computed(() => {
  if (!touched.password) return ''
  if (!form.password) return 'Ingresa tu contraseña.'
  return form.password.length >= 6 ? '' : 'La contraseña debe tener al menos 6 caracteres.'
})

function clearFeedback() {
  errorMessage.value = ''
  demoMessage.value = ''
}

function selectDemo(profile) {
  clearFeedback()
  form.email = profile.email
  form.password = profile.password
  showPassword.value = false
  demoMessage.value = 'Perfil ' + profile.label + ' seleccionado. Pulsa Iniciar sesión para entrar.'
  submitButton.value.focus()
}

async function handleLogin() {
  if (isLoading.value) return
  clearFeedback()
  touched.email = true
  touched.password = true
  if (emailError.value || passwordError.value) {
    await nextTick()
    const invalidField = emailError.value ? emailInput : passwordInput
    invalidField.value.focus()
    return
  }
  isLoading.value = true
  try {
    await authService.login(form)
    await router.push('/')
  } catch (error) {
    errorMessage.value = error.message || 'No se pudo iniciar sesión. Vuelve a intentarlo.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h1>Acceso a la bodega</h1>
    <form novalidate :aria-busy="isLoading" @submit.prevent="handleLogin">
      <div class="field">
        <label for="email">Correo electrónico</label>
        <input id="email" ref="emailInput" v-model="form.email" name="email" type="email" autocomplete="username" autocapitalize="none" spellcheck="false" required
          :disabled="isLoading" :aria-invalid="!!emailError" :aria-describedby="emailError ? 'email-error' : undefined" @blur="touched.email = true" @input="clearFeedback" />
        <p v-if="emailError" id="email-error" class="error">{{ emailError }}</p>
      </div>
      <div class="field">
        <label for="password">Contraseña</label>
        <div class="password-box">
          <input id="password" ref="passwordInput" v-model="form.password" name="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" required
            :disabled="isLoading" :aria-invalid="!!passwordError" :aria-describedby="passwordError ? 'password-error' : undefined" @blur="touched.password = true" @input="clearFeedback" />
          <button type="button" class="visibility" :aria-label="showPassword ? 'Ocultar contraseña' : 'Ver contraseña'" :disabled="isLoading" @click="showPassword = !showPassword">
            <EyeOff v-if="showPassword" :size="18" /><Eye v-else :size="18" />
          </button>
        </div>
        <p v-if="passwordError" id="password-error" class="error">{{ passwordError }}</p>
      </div>
      <div class="options">
        <label class="remember"><input v-model="form.rememberMe" type="checkbox" :disabled="isLoading" /> Recordar en este equipo</label>
        <RouterLink to="/recuperar-password">¿Olvidaste tu contraseña?</RouterLink>
      </div>
      <p v-if="errorMessage" class="server-error" role="alert">{{ errorMessage }}</p>
      <button ref="submitButton" class="submit" type="submit" :disabled="isLoading">
        {{ isLoading ? 'Verificando acceso…' : 'Iniciar sesión' }}
        <Loader2 v-if="isLoading" class="spinner" :size="18" /><ArrowRight v-else :size="18" />
      </button>
    </form>

    <section v-if="demoProfiles.length" class="demo" aria-labelledby="demo-title">
      <h2 id="demo-title">Perfiles de demostración</h2>
      <div class="roles"><button v-for="profile in demoProfiles" :key="profile.email" type="button" :disabled="isLoading" @click="selectDemo(profile)">{{ profile.label }}</button></div>
      <p class="sr-only" role="status">{{ demoMessage }}</p>
    </section>
  </AuthLayout>
</template>

<style scoped src="../assets/auth-form.css"></style>
<style scoped>
.password-box { position: relative; }
.password-box input { padding-right: 46px; }
.visibility { position: absolute; inset: 0 0 0 auto; width: 44px; display: grid; place-items: center; background: transparent; color: var(--muted); border: 0; border-radius: 7px; }
.visibility:hover { color: var(--wine); }
.options { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px 14px; }
.options, .roles button { font-size: .82rem; }
.remember { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
.remember input { width: 16px; height: 16px; accent-color: var(--wine); }
.options a { color: var(--wine); text-underline-offset: 3px; }
.options a:hover { text-decoration: underline; }
.demo { margin-top: 30px; padding-top: 20px; border-top: 1px solid var(--line); }
.demo h2 { font: 400 1.35rem/1.25 var(--display); }
.roles { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.roles button { padding: 6px 13px; min-height: 35px; border-radius: 5px; border: 1px solid #c5b8b2; color: var(--muted); background: transparent; font-family: inherit; }
.roles button:hover { border-color: var(--wine); color: var(--wine); background: #f1e9e3; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
</style>
