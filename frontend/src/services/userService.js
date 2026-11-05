import apiClient from './api.js'

export const userService = {
  /**
   * Lista todos los usuarios de la viña con sus roles y estados.
   * @param {Object} [params={}] - { rol, activo }
   */
  listar(params = {}) {
    const cleanParams = {}
    Object.keys(params || {}).forEach((key) => {
      const val = params[key]
      if (val !== null && val !== undefined && val !== '' && val !== 'todos' && val !== 'all') {
        cleanParams[key] = val
      }
    })
    return apiClient.get('/api/usuarios', { params: cleanParams }).then((res) => res.data)
  },

  /**
   * Invita o crea un nuevo usuario.
   * @param {Object} payload - { name, email, role, password, phone, bodega_id }
   */
  crear(payload) {
    return apiClient.post('/api/usuarios', payload).then((res) => res.data)
  },

  /**
   * Actualiza el rol de un usuario (admin, enologo, operario).
   */
  actualizarRol(id, role) {
    return apiClient.patch(`/api/usuarios/${id}/rol`, { role }).then((res) => res.data)
  },

  /**
   * Activa o suspende el acceso de un usuario.
   */
  actualizarEstado(id, active) {
    return apiClient.patch(`/api/usuarios/${id}/estado`, { active }).then((res) => res.data)
  },

  /**
   * Desactiva un usuario (soft-delete).
   */
  eliminar(id) {
    return apiClient.delete(`/api/usuarios/${id}`).then((res) => res.data)
  }
}

export default userService
