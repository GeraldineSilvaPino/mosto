import apiClient from './api'

export const processService = {
  /**
   * Lista los procesos de fermentación con filtros opcionales (?cuba_id, ?estado)
   */
  listarProcesos(params = {}) {
    return apiClient
      .get('/api/procesos', { params: { ...params, _t: Date.now() } })
      .then((res) => res.data)
  },

  /**
   * Obtiene el detalle de un proceso por ID
   */
  obtenerProceso(id) {
    return apiClient
      .get(`/api/procesos/${id}`, { params: { _t: Date.now() } })
      .then((res) => res.data)
  },

  /**
   * Inicia una nueva fermentación (Vendimia)
   * Payload requerido / aceptado:
   * {
   *   cuba_id: number,
   *   volumen_litros: number,
   *   brix_inicial?: number,
   *   brix_objetivo?: number,
   *   dias_estimados?: number,
   *   perfil_id?: number,
   *   cepa_id?: number,
   *   densidad_inicial_sg?: number
   * }
   */
  iniciar(payload) {
    const body = {
      cuba_id: Number(payload.cuba_id),
      volumen_litros: Number(payload.volumen_litros),
      brix_inicial:
        payload.brix_inicial !== undefined && payload.brix_inicial !== '' && payload.brix_inicial !== null
          ? Number(payload.brix_inicial)
          : 24.5,
      brix_objetivo:
        payload.brix_objetivo !== undefined && payload.brix_objetivo !== '' && payload.brix_objetivo !== null
          ? Number(payload.brix_objetivo)
          : 1.0,
      dias_estimados:
        payload.dias_estimados !== undefined && payload.dias_estimados !== '' && payload.dias_estimados !== null
          ? Number(payload.dias_estimados)
          : 14
    }

    if (payload.perfil_id) body.perfil_id = Number(payload.perfil_id)
    if (payload.cepa_id) body.cepa_id = Number(payload.cepa_id)
    if (payload.densidad_inicial_sg) body.densidad_inicial_sg = Number(payload.densidad_inicial_sg)

    return apiClient.post('/api/procesos/iniciar', body).then((res) => res.data)
  },

  /**
   * Finaliza una fermentación activa y libera la cuba
   * Payload opcional:
   * {
   *   densidad_final_sg?: number,
   *   brix_final?: number,
   *   motivo?: string,
   *   observaciones?: string
   * }
   */
  finalizar(procesoId, payload = {}) {
    const body = {}

    if (payload.densidad_final_sg !== undefined && payload.densidad_final_sg !== '' && payload.densidad_final_sg !== null) {
      body.densidad_final_sg = Number(payload.densidad_final_sg)
    }

    if (payload.brix_final !== undefined && payload.brix_final !== '' && payload.brix_final !== null) {
      body.brix_final = Number(payload.brix_final)
    }

    const motivoObservaciones = payload.motivo || payload.observaciones
    if (motivoObservaciones !== undefined && motivoObservaciones !== null && motivoObservaciones !== '') {
      body.motivo = String(motivoObservaciones).trim()
    }

    return apiClient
      .patch(`/api/procesos/${procesoId}/finalizar`, body)
      .then((res) => res.data)
  }
}

export const iniciarProceso = (payload) => processService.iniciar(payload)
export const finalizarProceso = (procesoId, payload) => processService.finalizar(procesoId, payload)
export const listarProcesos = (params) => processService.listarProcesos(params)
export const obtenerProceso = (id) => processService.obtenerProceso(id)

export default processService

