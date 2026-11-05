import apiClient from './api'

export default {
  /**
   * Lista alertas con filtros dinámicos (estado, severidad, cuba_id, limit, offset)
   * @param {Object} params - { estado, severidad, cuba_id, tipo_alerta, limit, offset }
   */
  listarAlertas(params = {}) {
    // Limpiar parámetros vacíos o nulos para enviar query params limpios
    const cleanParams = {}
    Object.keys(params).forEach((key) => {
      const val = params[key]
      if (val !== null && val !== undefined && val !== '' && val !== 'todas' && val !== 'todos') {
        cleanParams[key] = val
      }
    })
    return apiClient.get('/api/alertas', { params: cleanParams }).then((res) => res.data)
  },

  /**
   * Obtiene el detalle individual de una alerta por su ID
   * @param {number|string} id - Identificador de la alerta
   */
  obtenerAlerta(id) {
    return apiClient.get(`/api/alertas/${id}`).then((res) => res.data)
  },

  /**
   * Obtiene los KPIs globales de auditoría y la métrica MTTR calculada
   * @param {number|string|null} cubaId - ID opcional de la cuba para filtrar
   */
  obtenerMetricas(cubaId = null) {
    const params = (cubaId !== null && cubaId !== undefined && cubaId !== '' && cubaId !== 'all')
      ? { cuba_id: Number(cubaId) }
      : {}
    return apiClient.get('/api/alertas/metricas', { params }).then((res) => res.data)
  },

  /**
   * Registra el inicio de atención de una alerta por un operador
   * @param {number|string} id - Identificador de la alerta
   * @param {Object} payload - { usuario_id, nota }
   */
  atender(id, payload = { usuario_id: 1, nota: '' }) {
    return apiClient.patch(`/api/alertas/${id}/atender`, payload).then((res) => res.data)
  },

  /**
   * Resuelve formalmente una alerta registrando la acción correctiva
   * @param {number|string} id - Identificador de la alerta
   * @param {Object} payload - { usuario_id, nota_resolucion }
   */
  resolver(id, payload = { usuario_id: 1, nota_resolucion: '' }) {
    return apiClient.patch(`/api/alertas/${id}/resolver`, payload).then((res) => res.data)
  },

  /**
   * Descarga directa en el navegador de la bitácora histórica en formato CSV
   * @param {Object} params - { estado, severidad, cuba_id }
   */
  async exportarCsv(params = {}) {
    const cleanParams = {}
    Object.keys(params).forEach((key) => {
      const val = params[key]
      if (val !== null && val !== undefined && val !== '' && val !== 'todas' && val !== 'todos' && val !== 'all') {
        cleanParams[key] = val
      }
    })

    const response = await apiClient.get('/api/alertas/exportar', {
      params: cleanParams,
      responseType: 'blob'
    })

    let filename = `bitacora_alertas_${new Date().toISOString().slice(0, 10)}.csv`
    const disposition = response.headers['content-disposition']
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/)
      if (match && match[1]) filename = match[1]
    }

    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }
}
