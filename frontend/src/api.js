import axios from 'axios'

// O token NÃO mora mais no localStorage (FASE 2). A sessão vem em cookies
// HttpOnly, que JavaScript nenhum consegue ler — um XSS deixa de entregar a
// credencial. Aqui só fica o perfil exibido na interface, que não é segredo.
export const USER_KEY = 'indoc_user'
const CSRF_COOKIE = 'indoc_csrf'
const CSRF_HEADER = 'X-CSRF-Token'

const METODOS_SEGUROS = ['get', 'head', 'options']

const api = axios.create({
  baseURL: '/api',
  // Sem isto o navegador não envia os cookies de sessão.
  withCredentials: true,
})

function lerCookie(nome) {
  const achado = document.cookie
    .split('; ')
    .find(linha => linha.startsWith(`${nome}=`))
  return achado ? decodeURIComponent(achado.slice(nome.length + 1)) : null
}

// Registrado pelo AuthContext para que o 401 use a navegação do router
// em vez de window.location (que recarrega a página e perde o estado do SPA).
let onUnauthorized = null
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

api.interceptors.request.use(config => {
  // Double-submit: o cookie CSRF é legível por JS de propósito, e o servidor
  // confere se o header bate com ele. Só é exigido em método que muda estado.
  if (!METODOS_SEGUROS.includes((config.method || 'get').toLowerCase())) {
    const csrf = lerCookie(CSRF_COOKIE)
    if (csrf) config.headers[CSRF_HEADER] = csrf
  }
  return config
})

// ── Renovação automática ────────────────────────────────────────────────
// O access token agora dura minutos. Em vez de deslogar o usuário quando ele
// expira, o primeiro 401 dispara um /auth/refresh e a requisição é repetida.
// As chamadas concorrentes esperam a MESMA renovação, senão N requisições
// simultâneas disparariam N refreshes — e o segundo derrubaria a sessão, já
// que a rotação invalida o token anterior.
let renovacaoEmAndamento = null

function renovar() {
  if (!renovacaoEmAndamento) {
    renovacaoEmAndamento = api
      .post('/auth/refresh')
      .finally(() => { renovacaoEmAndamento = null })
  }
  return renovacaoEmAndamento
}

api.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config
    const status = err.response?.status
    const url = original?.url || ''

    // Não tentar renovar a partir do próprio refresh/login: daria laço.
    const rotaDeSessao = url.includes('/auth/refresh') || url.includes('/auth/login')

    if (status === 401 && original && !original._jaTentou && !rotaDeSessao) {
      original._jaTentou = true
      try {
        await renovar()
        return api(original)
      } catch {
        // Renovação falhou: a sessão acabou de verdade.
      }
    }

    if (status === 401) {
      localStorage.removeItem(USER_KEY)
      if (onUnauthorized) onUnauthorized()
      else window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

/**
 * Baixa um arquivo do documento. Os arquivos não são públicos: a requisição
 * leva os cookies de sessão e o navegador recebe um blob.
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
