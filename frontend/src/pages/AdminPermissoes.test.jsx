import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AdminPermissoes from './AdminPermissoes'
import api from '../api'

vi.mock('../api', async () => {
  const real = await vi.importActual('../api')
  return { ...real, default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }
})

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'admin', role: 'admin' }, logout: vi.fn(), isAdmin: true }),
}))

const CATALOGO = {
  permissoes: ['read', 'download', 'approve', 'manage_permissions'],
  subject_types: ['usuario', 'grupo', 'perfil'],
  resource_types: ['global', 'ambiente', 'area', 'projeto', 'documento'],
}

function respostas(overrides = {}) {
  const base = {
    '/permissoes/catalogo': CATALOGO,
    '/permissoes/grupos': [
      { id: 1, nome: 'Engenharia Mecânica', descricao: 'Disciplina', ativo: true, total_membros: 2 },
    ],
    '/permissoes/perfis': [
      { id: 7, nome: 'consulta', descricao: 'Somente leitura', sistema: true, ativo: true, permissoes: ['read'] },
      { id: 8, nome: 'auditor', descricao: null, sistema: false, ativo: true, permissoes: ['read', 'download'] },
    ],
    '/usuarios': [{ id: 3, username: 'ana', email: 'ana@indoc.local', role: 'user' }],
    '/hierarquia': [],
    ...overrides,
  }
  api.get.mockImplementation(url => Promise.resolve({ data: base[url] ?? [] }))
}

function montar() {
  return render(<MemoryRouter><AdminPermissoes /></MemoryRouter>)
}

describe('AdminPermissoes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    respostas()
  })

  it('lista os grupos vindos da API', async () => {
    montar()
    expect(await screen.findByText('Engenharia Mecânica')).toBeInTheDocument()
    expect(screen.getByText('2 membros')).toBeInTheDocument()
  })

  it('monta as permissões a partir do catálogo do backend, sem hardcodar', async () => {
    montar()
    await userEvent.click(await screen.findByRole('button', { name: /Perfis/ }))
    for (const perm of CATALOGO.permissoes) {
      expect(await screen.findByLabelText(perm)).toBeInTheDocument()
    }
  })

  it('não oferece excluir perfil de sistema', async () => {
    montar()
    await userEvent.click(await screen.findByRole('button', { name: /Perfis/ }))
    await screen.findByText('consulta')
    // 'auditor' não é de sistema, então há exatamente um botão Excluir.
    const excluir = screen.getAllByRole('button', { name: 'Excluir' })
    expect(excluir).toHaveLength(1)
  })

  it('cria grupo e recarrega a lista', async () => {
    api.post.mockResolvedValue({ data: { id: 2, nome: 'Elétrica', total_membros: 0 } })
    montar()
    await screen.findByText('Engenharia Mecânica')

    await userEvent.type(screen.getByPlaceholderText(/Nome do grupo/), 'Elétrica')
    await userEvent.click(screen.getByRole('button', { name: 'Criar grupo' }))

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/permissoes/grupos',
        { nome: 'Elétrica', descricao: null })
    })
  })

  it('na aba de ACL, o recurso global não pede id', async () => {
    montar()
    await userEvent.click(await screen.findByRole('button', { name: /Permissões por recurso/ }))

    const seletorTipo = screen.getAllByRole('combobox')[0]
    await userEvent.selectOptions(seletorTipo, 'global')

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/permissoes/acl',
        { params: { resource_type: 'global' } })
    })
  })
})
