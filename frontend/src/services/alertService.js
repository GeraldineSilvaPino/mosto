import apiClient from './api.js'

/**
 * Función auxiliar para desencadenar la descarga de un archivo en el navegador
 * mediante la creación de un enlace temporal en el DOM (window.URL.createObjectURL(blob)).
 * @param {Blob} blob - Archivo en formato Blob
 * @param {string} filename - Nombre con el que se guardará el archivo
 */
export function descargarBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

/**
 * Extrae el nombre de archivo desde la cabecera Content-Disposition o asigna un fallback.
 * @param {string|undefined} disposition - Valor de la cabecera Content-Disposition
 * @param {string} [fallback='bitacora_alertas_export.csv'] - Nombre de respaldo
 * @returns {string} Nombre extraído o de fallback
 */
export function extraerNombreArchivo(disposition, fallback = 'bitacora_alertas_export.csv') {
  if (!disposition || typeof disposition !== 'string') {
    return fallback
  }

  // 1. Cabeceras con codificación RFC 5987 (filename*=UTF-8''...)
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match && utf8Match[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim())
    } catch {
      return utf8Match[1].trim()
    }
  }

  // 2. Cabeceras estándar filename="nombre.csv" o filename=nombre.csv
  const match = disposition.match(/filename="?([^";]+)"?/i)
  if (match && match[1]) {
    return match[1].trim()
  }

  return fallback
}

export default {
  /**
   * Lista alertas con filtros dinámicos (estado, severidad, cuba_id, limit, offset)
   * @param {Object} params - { estado, severidad, cuba_id, tipo_alerta, limit, offset }
   */
  listarAlertas(params = {}) {
    // Limpiar parámetros vacíos o nulos para enviar query params limpios
    const cleanParams = {}
    Object.keys(params || {}).forEach((key) => {
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
   * Función auxiliar expuesta para desencadenar descarga en navegador
   */
  descargarBlob,

  /**
   * Función auxiliar expuesta para extracción de nombre de archivo
   */
  extraerNombreArchivo,

  /**
   * Descarga directa en el navegador de la bitácora histórica en formato CSV (GET /api/alertas/exportar)
   * Cumple con cabecera Content-Disposition y BOM UTF-8 para compatibilidad nativa con Excel.
   * @param {Object} [filtros={}] - Filtros opcionales { estado, severidad, cuba_id }
   * @returns {Promise<{success: boolean, filename: string}>}
   */
  async exportarCsv(filtros = {}) {
    const cleanParams = {}
    Object.keys(filtros || {}).forEach((key) => {
      const val = filtros[key]
      if (val !== null && val !== undefined && val !== '' && val !== 'todas' && val !== 'todos' && val !== 'all') {
        cleanParams[key] = val
      }
    })

    try {
      const response = await apiClient.get('/api/alertas/exportar', {
        params: cleanParams,
        responseType: 'blob'
      })

      // Extraer nombre del archivo de la cabecera Content-Disposition con fallback oficial
      const disposition = response.headers?.['content-disposition'] ||
        (typeof response.headers?.get === 'function' ? response.headers.get('content-disposition') : null)

      const filename = extraerNombreArchivo(disposition, 'bitacora_alertas_export.csv')

      // Asegurar instancia Blob con MIME text/csv;charset=utf-8;
      const blob = response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: 'text/csv;charset=utf-8;' })

      // Desencadenar la descarga en el navegador con el enlace temporal
      descargarBlob(blob, filename)

      return { success: true, filename }
    } catch (err) {
      if (err.response?.data instanceof Blob) {
        try {
          const errorText = await err.response.data.text()
          const parsed = JSON.parse(errorText)
          if (parsed?.detail) {
            throw new Error(parsed.detail)
          }
        } catch (parseErr) {
          if (parseErr.message && parseErr !== err) throw parseErr
        }
      }
      throw err
    }
  }
}
