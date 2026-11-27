<script setup>
import { computed, nextTick, ref } from 'vue'
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-vue-next'
import AuthLayout from '../layouts/AuthLayout.vue'
import authService from '../services/authService'

const email = ref('')
const emailInput = ref(null)
const heading = ref(null)
const touched = ref(false)
const isLoading = ref(false)
const submittedEmail = ref('')
const errorMessage = ref('')
const isDev = import.meta.env.DEV

const emailError = computed(() => {
  if (!touched.value) return ''
  if (!email.value.trim()) return 'Ingresa tu correo electrónico.'
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim()) ? '' : 'Revisa el formato del correo electrónico.'
})

async function submit() {
  if (isLoading.value) return
  touched.value = true
  errorMessage.value = ''
  if (emailError.value) {
    await nextTick()
    emailInput.value.focus()
    return
  }

  const address = email.value.trim()
  isLoading.value = true
  try {
    await authService.recuperarPassword(address)
    submittedEmail.value = address
    await nextTick()
    heading.value.focus()
  } catch {
    errorMessage.value = 'No se pudo procesar la solicitud. Vuelve a intentarlo.'
  } finally {
    isLoading.value = false
  }
}

async function editEmail() {
  submittedEmail.value = ''
  touched.value = false
  await nextTick()
  emailInput.value.focus()
  emailInput.value.select()
}

function useDemoEmail() {
  email.value = 'enologo@mosto.cl'
  errorMessage.value = ''
  emailInput.value.focus()
}
</script>

<template>
  <AuthLayout>
    <template v-if="!submittedEmail">
      <RouterLink to="/login" class="back"><ArrowLeft :size="16" aria-hidden="true" />Volver al inicio de sesión</RouterLink>
      <h1>Recuperar contraseña</h1>
      <p class="description">Ingresa el correo que usas para acceder a la bodega.</p>

      <form novalidate :aria-busy="isLoading" @submit.prevent="submit">
        <div class="field">
          <label for="email">Correo electrónico</label>
          <input id="email" ref="emailInput" v-model="email" name="email" type="email" autocomplete="email"
            autocapitalize="none" spellcheck="false" required :disabled="isLoading"
            :aria-invalid="!!emailError" :aria-describedby="emailError ? 'email-error' : undefined"
            @blur="touched = true" @input="errorMessage = ''" />
          <p v-if="emailError" id="email-error" class="error">{{ emailError }}</p>
        </div>
        <p v-if="errorMessage" class="server-error" role="alert">{{ errorMessage }}</p>
        <button class="submit" type="submit" :disabled="isLoading">
          {{ isLoading ? 'Enviando solicitud…' : 'Solicitar recuperación' }}
          <Loader2 v-if="isLoading" class="spinner" :size="18" aria-hidden="true" />
          <ArrowRight v-else :size="18" aria-hidden="true" />
        </button>
      </form>
      <button v-if="isDev" type="button" class="secondary" :disabled="isLoading" @click="useDemoEmail">Usar correo de demostración</button>
    </template>

    <template v-else>
      <h1 ref="heading" tabindex="-1">Solicitud recibida</h1>
      <p class="description">Recibimos tu solicitud para <strong>{{ submittedEmail }}</strong>.
        Para restablecer tu acceso, contacta a quien administra tu bodega.</p>
      <RouterLink class="submit" to="/login">Volver al inicio de sesión <ArrowRight :size="18" aria-hidden="true" /></RouterLink>
      <button type="button" class="secondary" @click="editEmail">Volver a intentar</button>
    </template>
  </AuthLayout>
</template>

<style scoped src="../assets/auth-form.css"></style>
<style scoped>
h1 { margin-bottom: 12px; }
.description { margin: 0 0 30px; color: var(--muted); font-size: .95rem; line-height: 1.6; }
.description strong { color: var(--ink); overflow-wrap: anywhere; }
.back, .secondary {
  display: inline-flex; align-items: center; gap: 8px; min-height: 44px;
  padding: 0; border: 0; background: transparent; color: var(--wine);
  font: 600 .82rem/1.4 var(--font-sans); text-decoration: none; text-underline-offset: 3px;
}
.back { margin-bottom: 16px; }
.secondary { margin-top: 10px; }
.back:hover, .secondary:hover { text-decoration: underline; }
a.submit { text-decoration: none; }
</style>
