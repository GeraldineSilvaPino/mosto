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
  },

  /**
   * Obtiene la predicción de Machine Learning para parada temprana de fermentación
   * @param {number|string} id - ID de la cuba
   */
  obtenerPrediccionML(id) {
    return apiClient
      .get(`/api/cubas/${id}/ml-prediction`, {
        params: { _t: Date.now() }
      })
      .then((res) => res.data)
  },

  /**
   * Inyecta una anomalía de parada de fermentación para demo en vivo
   * @param {number|string} id - ID de la cuba
   */
  simularAnomalia(id) {
    return apiClient
      .post(`/api/cubas/${id}/simular-anomalia`)
      .then((res) => res.data)
  },

  /**
   * Restaura la cinética normal de fermentación tras una simulación
   * @param {number|string} id - ID de la cuba
   */
  restaurarNormalidad(id) {
    return apiClient
      .post(`/api/cubas/${id}/restaurar-normalidad`)
      .then((res) => res.data)
  }
}

export const obtenerCuba = (id) => cubaService.obtenerCuba(id)
export const obtenerHistorico = (id, rangoHoras = 24) => cubaService.obtenerHistorico(id, rangoHoras)
export const listarCubas = () => cubaService.listarCubas()
export const obtenerPrediccionML = (id) => cubaService.obtenerPrediccionML(id)
export const simularAnomalia = (id) => cubaService.simularAnomalia(id)
export const restaurarNormalidad = (id) => cubaService.restaurarNormalidad(id)

export default cubaService
