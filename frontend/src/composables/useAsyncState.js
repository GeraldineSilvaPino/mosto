import { ref } from 'vue'

export function useAsyncState() {
  const loading = ref(false)
  const error = ref(null)

  const execute = async (asyncFn) => {
    loading.value = true
    error.value = null
    try {
      return await asyncFn()
    } catch (err) {
      error.value = err.message || 'Ocurrió un error inesperado al procesar la solicitud'
      throw err
    } finally {
      loading.value = false
    }
  }

  return { loading, error, execute }
}

export default useAsyncState

