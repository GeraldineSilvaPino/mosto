import apiClient from './api.js'

export const binnacleService = {
  /**
   * Obtiene la lista cronológica de eventos y notas de la bitácora.
   * @param {Object} [params={}] - { tipo, cuba, search }
   */
  listarEntradas(params = {}) {
    const cleanParams = { _t: Date.now() }
    Object.keys(params || {}).forEach((key) => {
      const val = params[key]
      if (val !== null && val !== undefined && val !== '' && val !== 'todos' && val !== 'all') {
        cleanParams[key] = val
      }
    })
    return apiClient.get('/api/bitacora', { params: cleanParams }).then((res) => res.data)
  },

  /**
   * Registra una nueva nota, alerta, configuración o lectura enológica.
   * @param {Object} payload - { type, cuba, message, author, dosis }
   */
  registrarEntrada(payload) {
    return apiClient.post('/api/bitacora', payload).then((res) => res.data)
  }
}

export default binnacleService

