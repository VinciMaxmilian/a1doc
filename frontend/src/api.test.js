import { describe, expect, it } from 'vitest'
import { mensagemErro } from './api'

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
