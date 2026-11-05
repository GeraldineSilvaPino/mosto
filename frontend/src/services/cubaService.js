import apiClient from './api'

export const cubaService = {
  /**
   * Obtiene la lista de todas las cubas con telemetría en tiempo real.
   * Se incluye query param `_t` para evitar almacenamiento en caché HTTP del navegador.
   */
  listarCubas() {
    return apiClient
      .get('/api/cubas', {
        params: { _t: Date.now() }
      })
      .then((res) => res.data)
  },

  /**
   * Obtiene el detalle completo de una cuba por su ID
   */
  obtenerCuba(id) {
    return apiClient
      .get(`/api/cubas/${id}`, {
        params: { _t: Date.now() }
      })
      .then((res) => res.data)
  },

  /**
   * Obtiene la serie histórica de lecturas para Chart.js
   * @param {number|string} id - ID de la cuba
   * @param {number} rangoHoras - Ventana de tiempo (24, 48, 168)
   */
  obtenerHistorico(id, rangoHoras = 24) {
    return apiClient
      .get(`/api/cubas/${id}/historico`, {
        params: { rango_horas: Number(rangoHoras) || 24, _t: Date.now() }
      })
      .then((res) => res.data)
  }
}

export const obtenerCuba = (id) => cubaService.obtenerCuba(id)
export const obtenerHistorico = (id, rangoHoras = 24) => cubaService.obtenerHistorico(id, rangoHoras)
export const listarCubas = () => cubaService.listarCubas()

export default cubaService
