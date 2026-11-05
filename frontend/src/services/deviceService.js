import apiClient from './api.js'

export default {
  /**
   * Lista el inventario de dispositivos IoT con estado telemétrico dinámico y RSSI
   * @param {Object} [params={}] - Filtros opcionales { cuba_id, status }
   * @returns {Promise<Array>} Lista de dispositivos DTO DispositivoOut
   */
  listarDispositivos(params = {}) {
    const cleanParams = {}
    Object.keys(params || {}).forEach((key) => {
      const val = params[key]
      if (val !== null && val !== undefined && val !== '' && val !== 'all' && val !== 'todos' && val !== 'todas') {
        cleanParams[key] = val
      }
    })
    return apiClient.get('/api/dispositivos', { params: cleanParams }).then((res) => res.data)
  },

  /**
   * Obtiene el detalle telemétrico de un dispositivo IoT por ID
   * @param {number|string} id - Identificador único del dispositivo
   */
  obtenerDispositivo(id) {
    return apiClient.get(`/api/dispositivos/${id}`).then((res) => res.data)
  },

  /**
   * Vincula físicamente un sensor a una cuba
   * @param {number|string} dispositivoId - ID del dispositivo
   * @param {number|string} cubaId - ID de la cuba
   */
  vincular(dispositivoId, cubaId) {
    return apiClient
      .post('/api/dispositivos/vincular', {
        dispositivo_id: Number(dispositivoId),
        cuba_id: Number(cubaId)
      })
      .then((res) => res.data)
  },

  /**
   * Desvincula un dispositivo de su cuba actual dejándolo en reserva
   * @param {number|string} dispositivoId - ID del dispositivo
   */
  desvincular(dispositivoId) {
    return apiClient
      .post('/api/dispositivos/desvincular', {
        dispositivo_id: Number(dispositivoId)
      })
      .then((res) => res.data)
  }
}
