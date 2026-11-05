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

// Interceptor de respuesta global para manejo unificado de errores
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorMsg =
      error.response?.data?.detail ||
      error.message ||
      'Error de comunicación con el servidor MOSTO'

    console.error(`[API Error ${error.response?.status || 'RED'}]:`, errorMsg)
    return Promise.reject(new Error(errorMsg))
  }
)

export default apiClient
