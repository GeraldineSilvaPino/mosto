<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Eye, EyeOff, Grape, Loader2 } from 'lucide-vue-next'
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
  <main class="login">
    <header class="cellar">
      <div class="wordmark"><Grape aria-hidden="true" :size="33" :stroke-width="1.5" /><span>Mosto</span></div>
      <p>Monitor de bodega</p>
    </header>

    <div class="entry">
      <div class="access">
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
      </div>
    </div>
  </main>
</template>

<style scoped>
.login {
  --canvas: #f8f5ef;
  --ink: #30232a;
  --muted: #695d61;
  --wine: #763c51;
  --line: #d8cec6;
  --display: 'Instrument Serif', Georgia, serif;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  min-height: 100vh;
  min-height: 100svh;
  color: var(--ink);
  background: var(--canvas);
}
.cellar {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: clamp(32px, 4.6vw, 90px);
  color: #fff7ee;
  background-color: #32232d;
  background-image: linear-gradient(0deg, rgb(27 20 23 / .88), transparent 46%), url('../assets/sala-de-cubas.webp');
  background-size: cover;
  background-position: center;
}
.wordmark { display: flex; flex-direction: column; align-items: flex-start; gap: 12px; font: 400 clamp(4.4rem, 7.8vw, 8rem)/.88 var(--display); letter-spacing: -.035em; }
.wordmark svg { color: #f2dcdf; }
.cellar p { margin-top: 16px; font-size: 1rem; }
.entry { display: grid; align-items: center; justify-items: center; padding: 46px clamp(32px, 4vw, 96px); }
.access { width: min(100%, 415px); }
h1 { margin: 0 0 33px; font: 400 clamp(2.7rem, 4.2vw, 3.9rem)/1.06 var(--display); letter-spacing: -.027em; text-wrap: balance; }
form, .field { display: grid; }
form { gap: 20px; }
.field { gap: 7px; }
.field label { font-size: .89rem; font-weight: 600; }
.field input {
  width: 100%; min-width: 0; height: 47px; padding: 9px 13px;
  border: 1px solid #b3a49f; border-radius: 7px; background: #fffdf9;
  color: var(--ink); caret-color: var(--wine); font: inherit;
}
.field input[aria-invalid=true] { border-color: #963e4c; }
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
.submit { display: flex; justify-content: space-between; align-items: center; min-height: 46px; padding: 10px 16px; border: 0; border-radius: 7px; color: #fffaf5; background: var(--wine); font: 600 .94rem/1.4 var(--font-sans); }
.submit:hover { background: #623146; }
button { cursor: pointer; }
button:disabled { cursor: wait; opacity: .65; }
:where(input, button, a):focus-visible { outline: 2px solid var(--wine); outline-offset: 3px; }
.error, .server-error { font-size: .83rem; color: #8a3444; }
.server-error { padding: 10px 12px; background: #f4e4e5; border-radius: 6px; }
.demo { margin-top: 30px; padding-top: 20px; border-top: 1px solid var(--line); }
.demo h2 { font: 400 1.35rem/1.25 var(--display); }
.roles { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.roles button { padding: 6px 13px; min-height: 35px; border-radius: 5px; border: 1px solid #c5b8b2; color: var(--muted); background: transparent; font-family: inherit; }
.roles button:hover { border-color: var(--wine); color: var(--wine); background: #f1e9e3; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.login ::selection { background: #e4cdd5; color: var(--ink); }
@media (prefers-reduced-motion: no-preference) {
  .spinner { animation: spin .9s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
}
@media (max-width: 760px) {
  .login { grid-template-columns: 1fr; align-content: start; }
  .cellar { flex-direction: row; align-items: center; justify-content: space-between; gap: 12px; padding: 16px clamp(18px, 5vw, 32px); background-image: none; }
  .wordmark { flex-direction: row; align-items: center; gap: 8px; font-size: 2.35rem; }
  .wordmark svg { width: 25px; height: 25px; }
  .cellar p { margin: 0; font-size: .84rem; }
  .entry { padding: clamp(32px, 7vh, 68px) clamp(18px, 5vw, 32px); }
  h1 { margin-bottom: 27px; }
}
</style>
