import { beforeEach, describe, expect, it, vi } from 'vitest'
import api, { mensagemErro, USER_KEY } from './api'

describe('mensagemErro', () => {
  it('usa o detail em texto vindo da API', () => {
    const err = { response: { data: { detail: 'Credenciais inválidas' } } }
    expect(mensagemErro(err)).toBe('Credenciais inválidas')
  })

  it('junta os erros de validação do FastAPI', () => {
    const err = {
      response: {
        data: {
          detail: [
            { msg: 'campo obrigatório' },
            { msg: 'valor inválido' },
          ],
        },
      },
    }
    expect(mensagemErro(err)).toBe('campo obrigatório; valor inválido')
  })

  it('cai no message do axios quando não há detail', () => {
    expect(mensagemErro({ message: 'Network Error' })).toBe('Network Error')
  })

  it('usa o padrão quando não há nada aproveitável', () => {
    expect(mensagemErro({}, 'Falhou')).toBe('Falhou')
    expect(mensagemErro({ response: { data: { detail: [] } } }, 'Falhou')).toBe('Falhou')
  })
})

describe('sessão por cookie (FASE 2)', () => {
  beforeEach(() => {
    document.cookie = 'indoc_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
  })

  it('não guarda token no localStorage', () => {
    // A regressão que importa: se o token voltar para cá, um XSS leva a sessão.
    expect(localStorage.getItem('indoc_token')).toBeNull()
    // Só o perfil exibido na interface é local, e não é segredo.
    expect(USER_KEY).toBe('indoc_user')
  })

  it('envia cookies nas requisições', () => {
    expect(api.defaults.withCredentials).toBe(true)
  })

  it('anexa o header CSRF em método que muda estado', async () => {
    document.cookie = 'indoc_csrf=abc123; path=/'
    const handler = api.interceptors.request.handlers[0].fulfilled
    const config = await handler({ method: 'post', headers: {} })
    expect(config.headers['X-CSRF-Token']).toBe('abc123')
  })

  it('não anexa o header CSRF em leitura', async () => {
    document.cookie = 'indoc_csrf=abc123; path=/'
    const handler = api.interceptors.request.handlers[0].fulfilled
    const config = await handler({ method: 'get', headers: {} })
    expect(config.headers['X-CSRF-Token']).toBeUndefined()
  })

  it('não quebra quando o cookie CSRF não existe', async () => {
    const handler = api.interceptors.request.handlers[0].fulfilled
    const config = await handler({ method: 'post', headers: {} })
    expect(config.headers['X-CSRF-Token']).toBeUndefined()
  })
})

describe('renovação automática no 401', () => {
  it('não tenta renovar a partir do próprio /auth/refresh', async () => {
    const rejeitado = api.interceptors.response.handlers[0].rejected
    const erro = {
      config: { url: '/auth/refresh' },
      response: { status: 401 },
    }
    await expect(rejeitado(erro)).rejects.toBe(erro)
  })

  it('não tenta renovar duas vezes a mesma requisição', async () => {
    const rejeitado = api.interceptors.response.handlers[0].rejected
    const erro = {
      config: { url: '/documentos', _jaTentou: true },
      response: { status: 401 },
    }
    await expect(rejeitado(erro)).rejects.toBe(erro)
  })

  it('limpa o perfil local quando a sessão acaba de vez', async () => {
    localStorage.setItem(USER_KEY, JSON.stringify({ username: 'ana' }))
    const rejeitado = api.interceptors.response.handlers[0].rejected
    const erro = {
      config: { url: '/documentos', _jaTentou: true },
      response: { status: 401 },
    }
    await expect(rejeitado(erro)).rejects.toBe(erro)
    expect(localStorage.getItem(USER_KEY)).toBeNull()
  })

  it('deixa passar erro que não é 401', async () => {
    const rejeitado = api.interceptors.response.handlers[0].rejected
    const erro = { config: { url: '/documentos' }, response: { status: 500 } }
    await expect(rejeitado(erro)).rejects.toBe(erro)
    expect(vi.isMockFunction(api.get)).toBe(false)
  })
})
