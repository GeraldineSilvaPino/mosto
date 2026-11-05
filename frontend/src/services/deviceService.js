import apiClient from './api.js'

export const deviceService = {
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
   * Acepta payload { dispositivo_id, cuba_id } o parámetros posicionales (dispositivoId, cubaId)
   * @param {Object|number|string} payloadOrId - Objeto { dispositivo_id, cuba_id } o ID del dispositivo
   * @param {number|string} [maybeCubaId] - ID de la cuba (si el primer parámetro es un id)
   */
  vincular(payloadOrId, maybeCubaId) {
    let dispositivo_id
    let cuba_id

    if (typeof payloadOrId === 'object' && payloadOrId !== null) {
      dispositivo_id = payloadOrId.dispositivo_id ?? payloadOrId.dispositivoId
      cuba_id = payloadOrId.cuba_id ?? payloadOrId.cubaId
    } else {
      dispositivo_id = payloadOrId
      cuba_id = maybeCubaId
    }

    return apiClient
      .post('/api/dispositivos/vincular', {
        dispositivo_id: Number(dispositivo_id),
        cuba_id: Number(cuba_id)
      })
      .then((res) => res.data)
  },

  /**
   * Desvincula un dispositivo de su cuba actual dejándolo en reserva
   * Acepta payload { dispositivo_id } o parámetro posicional (dispositivoId)
   * @param {Object|number|string} payloadOrId - Objeto { dispositivo_id } o ID del dispositivo
   */
  desvincular(payloadOrId) {
    let dispositivo_id

    if (typeof payloadOrId === 'object' && payloadOrId !== null) {
      dispositivo_id = payloadOrId.dispositivo_id ?? payloadOrId.dispositivoId
    } else {
      dispositivo_id = payloadOrId
    }

    return apiClient
      .post('/api/dispositivos/desvincular', {
        dispositivo_id: Number(dispositivo_id)
      })
      .then((res) => res.data)
  }
}

export const listarDispositivos = (params) => deviceService.listarDispositivos(params)
export const obtenerDispositivo = (id) => deviceService.obtenerDispositivo(id)
export const vincular = (payloadOrId, maybeCubaId) => deviceService.vincular(payloadOrId, maybeCubaId)
export const desvincular = (payloadOrId) => deviceService.desvincular(payloadOrId)

export default deviceService
