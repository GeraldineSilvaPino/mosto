import apiClient from './api.js'

export const authService = {
  /**
   * Inicia sesión con credenciales contra el backend FastAPI / Supabase PostgreSQL.
   * @param {Object} credentials - { email, password, rememberMe }
   * @returns {Promise<Object>} { access_token, token_type, user }
   */
  async login({ email, password, rememberMe = false }) {
    const payload = {
      email: email.trim().toLowerCase(),
      password,
      remember_me: rememberMe
    }

    const res = await apiClient.post('/api/auth/login', payload)
    const { access_token, user } = res.data

    authService.guardarSesion(access_token, user, rememberMe)
    return res.data
  },

  /**
   * Solicita el restablecimiento de contraseña.
   * @param {string} email
   */
  recuperarPassword(email) {
    return apiClient
      .post('/api/auth/recuperar-password', { email: email.trim().toLowerCase() })
      .then((res) => res.data)
  },

  /**
   * Obtiene el perfil del usuario autenticado en tiempo real.
   */
  obtenerUsuarioActual() {
    return apiClient.get('/api/auth/me').then((res) => {
      const user = res.data
      const storage = localStorage.getItem('mosto_auth_token') ? localStorage : sessionStorage
      storage.setItem('mosto_user', JSON.stringify(user))
      window.dispatchEvent(new CustomEvent('mosto:user-updated', { detail: user }))
      return user
    })
  },

  /**
   * Guarda el token y el perfil del usuario en el storage correspondiente.
   */
  guardarSesion(token, user, rememberMe = false) {
    // Limpiar almacenamiento previo
    localStorage.removeItem('mosto_auth_token')
    sessionStorage.removeItem('mosto_auth_token')
    localStorage.removeItem('mosto_user')
    sessionStorage.removeItem('mosto_user')

    const storage = rememberMe ? localStorage : sessionStorage
    storage.setItem('mosto_auth_token', token)
    storage.setItem('mosto_user', JSON.stringify(user))

    window.dispatchEvent(new CustomEvent('mosto:login-success', { detail: user }))
  },

  /**
   * Obtiene el usuario almacenado en la sesión local.
   */
  obtenerUsuarioSesion() {
    const userStr = localStorage.getItem('mosto_user') || sessionStorage.getItem('mosto_user')
    if (userStr) {
      try {
        return JSON.parse(userStr)
      } catch {
        return null
      }
    }
    return null
  },

  /**
   * Verifica si existe un token de sesión activo.
   */
  isAuthenticated() {
    return Boolean(localStorage.getItem('mosto_auth_token') || sessionStorage.getItem('mosto_auth_token'))
  },

  /**
   * Cierra la sesión activa y limpia los almacenamientos.
   */
  cerrarSesion() {
    localStorage.removeItem('mosto_auth_token')
    sessionStorage.removeItem('mosto_auth_token')
    localStorage.removeItem('mosto_user')
    sessionStorage.removeItem('mosto_user')
    window.dispatchEvent(new CustomEvent('mosto:logout'))
  }
}

export default authService

