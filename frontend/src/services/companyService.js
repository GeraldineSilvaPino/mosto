import apiClient from './api.js'

export const companyService = {
  /**
   * Obtiene la configuración de la empresa, bodega y las cuotas SaaS en tiempo real.
   */
  obtenerConfiguracion() {
    return apiClient
      .get('/api/empresa', { params: { _t: Date.now() } })
      .then((res) => res.data)
  },

  /**
   * Actualiza los datos de identidad, fiscales y operativos de la viña.
   */
  actualizarConfiguracion(payload) {
    return apiClient.put('/api/empresa', payload).then((res) => res.data)
  },

  /**
   * Solicita ampliación de capacidad para el monitoreo de cubas IoT.
   * @param {number} extraCubas
   */
  solicitarAmpliacion(extraCubas) {
    return apiClient
      .post('/api/empresa/ampliacion', { extra_cubas: Number(extraCubas) })
      .then((res) => res.data)
  }
}

export default companyService
