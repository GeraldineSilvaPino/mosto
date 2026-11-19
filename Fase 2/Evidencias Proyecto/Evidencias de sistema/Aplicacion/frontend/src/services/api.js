import axios from 'axios'

const API_BASE_URL = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) || 'http://localhost:8000'
const TIMEOUT_MS = Number(typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_TIMEOUT_MS) || 10000

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0'
  }
})

// Interceptor de petición para inyectar token JWT automáticamente
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('mosto_auth_token') || sessionStorage.getItem('mosto_auth_token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Interceptor de respuesta global para manejo unificado de errores y expiración de sesión
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Si el token expiró y no estamos en /login, limpiar sesión
      const isLoginRequest = error.config?.url?.includes('/api/auth/login')
      if (!isLoginRequest) {
        localStorage.removeItem('mosto_auth_token')
        sessionStorage.removeItem('mosto_auth_token')
        localStorage.removeItem('mosto_user')
        sessionStorage.removeItem('mosto_user')
        window.dispatchEvent(new CustomEvent('mosto:auth-expired'))
      }
    }

    let errorMsg =
      error.response?.data?.detail ||
      error.message ||
      'Error de comunicación con el servidor MOSTO'

    if (typeof errorMsg === 'object' && errorMsg !== null) {
      if (Array.isArray(errorMsg)) {
        errorMsg = errorMsg.map((e) => e.msg || e.message || JSON.stringify(e)).join(' | ')
      } else {
        errorMsg = errorMsg.message || errorMsg.msg || JSON.stringify(errorMsg)
      }
    }

    console.error(`[API Error ${error.response?.status || 'RED'}]:`, errorMsg)
    return Promise.reject(new Error(errorMsg))
  }
)

export default apiClient
