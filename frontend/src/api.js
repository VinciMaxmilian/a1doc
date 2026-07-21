import axios from 'axios'

export const TOKEN_KEY = 'indoc_token'
export const USER_KEY = 'indoc_user'

const api = axios.create({ baseURL: '/api' })

// Registrado pelo AuthContext para que o 401 use a navegação do router
// em vez de window.location (que recarrega a página e perde o estado do SPA).
let onUnauthorized = null
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

api.interceptors.request.use(config => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      if (onUnauthorized) onUnauthorized()
      else window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

/**
 * Baixa um arquivo do documento. Os arquivos não são públicos: a requisição
 * passa pelo interceptor que injeta o token e o navegador recebe um blob.
 */
export async function baixarArquivo(arquivoId, nomeSugerido) {
  const { data } = await api.get(`/documentos/arquivos/${arquivoId}/download`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(data)
  try {
    const link = document.createElement('a')
    link.href = url
    link.download = nomeSugerido || 'arquivo'
    document.body.appendChild(link)
    link.click()
    link.remove()
  } finally {
    // Revoga no próximo tick: o download já foi iniciado pelo clique.
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }
}

/** Extrai a mensagem de erro da API, com fallback legível. */
export function mensagemErro(err, padrao = 'Erro inesperado') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map(d => d.msg || '').filter(Boolean).join('; ') || padrao
  }
  return err?.message || padrao
}

export default api
