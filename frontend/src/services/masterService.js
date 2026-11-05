import apiClient from './api.js'

export const masterService = {
  /**
   * Obtiene el catálogo de cepas viníferas
   */
  listarCepas() {
    return apiClient.get('/api/cepas').then((res) => res.data)
  },

  /**
   * Obtiene los tipos de material para cubas
   */
  listarMateriales() {
    return apiClient.get('/api/materiales-cuba').then((res) => res.data)
  }
}

export default masterService

