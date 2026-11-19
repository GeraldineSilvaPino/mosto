import apiClient from './api.js'

export const profileService = {
  /**
   * Lista todos los perfiles de fermentación y bandas enológicas
   * @param {Object} [params={}] - Filtros opcionales { cepa_id, bodega_id, activo }
   * @returns {Promise<Array>} Lista de perfiles DTO PerfilOut
   */
  listarPerfiles(params = {}) {
    return apiClient.get('/api/perfiles', { params }).then((res) => res.data)
  },

  /**
   * Alias estándar para listar perfiles
   */
  listar(params = {}) {
    return profileService.listarPerfiles(params)
  },

  /**
   * Obtiene la configuración detallada de un perfil enológico por ID
   * @param {number|string} id - ID del perfil
   * @returns {Promise<Object>} DTO PerfilOut
   */
  obtenerPerfil(id) {
    return apiClient.get(`/api/perfiles/${id}`).then((res) => res.data)
  },

  /**
   * Alias estándar para obtener perfil
   */
  obtener(id) {
    return profileService.obtenerPerfil(id)
  },

  /**
   * Crea un nuevo perfil enológico con sus bandas térmicas y de acidez
   * @param {Object} payload - { nomb_perfil, temp_min, temp_max, ph_min, ph_max, brix_caida_min_dia, cepa_id, bodega_id, activo }
   * @returns {Promise<Object>} DTO PerfilOut
   */
  crearPerfil(payload) {
    return apiClient.post('/api/perfiles', payload).then((res) => res.data)
  },

  /**
   * Alias estándar para crear perfil
   */
  crear(payload) {
    return profileService.crearPerfil(payload)
  },

  /**
   * Actualiza umbrales de temperatura y pH de un perfil existente
   * @param {number|string} id - ID del perfil
   * @param {Object} payload - Campos a modificar
   * @returns {Promise<Object>} DTO PerfilOut
   */
  actualizarPerfil(id, payload) {
    return apiClient.put(`/api/perfiles/${id}`, payload).then((res) => res.data)
  },

  /**
   * Alias estándar para actualizar perfil
   */
  actualizar(id, payload) {
    return profileService.actualizarPerfil(id, payload)
  },

  /**
   * Desactiva (soft-delete) un perfil de fermentación
   * Si está en uso por un proceso activo, el backend retornará error 400
   * @param {number|string} id - ID del perfil
   * @returns {Promise<Object>} { status: 'ok', mensaje: string }
   */
  desactivarPerfil(id) {
    return apiClient.delete(`/api/perfiles/${id}`).then((res) => res.data)
  },

  /**
   * Alias estándar para desactivar perfil
   */
  desactivar(id) {
    return profileService.desactivarPerfil(id)
  },

  /**
   * Alias para eliminar perfil (soft-delete)
   */
  eliminar(id) {
    return profileService.desactivarPerfil(id)
  }
}

export const listarPerfiles = (params) => profileService.listarPerfiles(params)
export const listar = (params) => profileService.listar(params)
export const obtenerPerfil = (id) => profileService.obtenerPerfil(id)
export const obtener = (id) => profileService.obtener(id)
export const crearPerfil = (payload) => profileService.crearPerfil(payload)
export const crear = (payload) => profileService.crear(payload)
export const actualizarPerfil = (id, payload) => profileService.actualizarPerfil(id, payload)
export const actualizar = (id, payload) => profileService.actualizar(id, payload)
export const desactivarPerfil = (id) => profileService.desactivarPerfil(id)
export const desactivar = (id) => profileService.desactivar(id)
export const eliminar = (id) => profileService.eliminar(id)

export default profileService
