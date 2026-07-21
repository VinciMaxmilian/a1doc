import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import ConfirmModal from '../components/ConfirmModal'
import { useAuth } from '../contexts/AuthContext'
import api, { mensagemErro } from '../api'

const ROLES = ['user', 'admin', 'dev']

const ROLE_BADGE = {
  dev:   'badge-blue',
  admin: 'badge-orange',
  user:  'badge-gray',
}

export default function AdminUsuarios() {
  const { user: me } = useAuth()
  const [usuarios, setUsuarios] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(false)
  const [confirmDel, setConfirmDel] = useState(null)
  const [deletando, setDeletando] = useState(false)
  const [msg, setMsg] = useState({ tipo: '', texto: '' })
  const [form, setForm] = useState({ username: '', email: '', password: '', role: 'user' })
  const [editando, setEditando] = useState(null) // { id, role, is_active }

  useEffect(() => { carregar() }, [])

  async function carregar() {
    setCarregando(true)
    try { const r = await api.get('/usuarios'); setUsuarios(r.data) }
    finally { setCarregando(false) }
  }

  function flash(tipo, texto) { setMsg({ tipo, texto }); setTimeout(() => setMsg({ tipo: '', texto: '' }), 4000) }

  async function criar(e) {
    e.preventDefault()
    setSalvando(true)
    try {
      await api.post('/usuarios', form)
      setForm({ username: '', email: '', password: '', role: 'user' })
      await carregar()
      flash('success', `Usuário "${form.username}" criado!`)
    } catch (err) {
      flash('error', mensagemErro(err, 'Erro ao criar usuário'))
    } finally { setSalvando(false) }
  }

  async function salvarEdicao(uid) {
    try {
      await api.put(`/usuarios/${uid}`, { role: editando.role, is_active: editando.is_active })
      setEditando(null)
      await carregar()
      flash('success', 'Usuário atualizado.')
    } catch (err) {
      flash('error', mensagemErro(err, 'Erro ao atualizar'))
    }
  }

  async function confirmarDelete() {
    setDeletando(true)
    try {
      await api.delete(`/usuarios/${confirmDel.id}`)
      await carregar()
      flash('success', `Usuário "${confirmDel.username}" removido.`)
    } catch (err) {
      flash('error', mensagemErro(err, 'Erro ao excluir'))
    } finally { setDeletando(false); setConfirmDel(null) }
  }

  return (
    <Layout>
      <div className="page-header"><h1>👤 Gerenciar Usuários</h1></div>
      <div className="page-body">
        {msg.texto && (
          <div className={`alert alert-${msg.tipo === 'error' ? 'error' : 'success'}`}>
            {msg.texto}
          </div>
        )}

        {/* ── Formulário de criação ── */}
        <div className="card" style={{ maxWidth: 680, marginBottom: 24 }}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 18 }}>Novo Usuário</div>
          <form onSubmit={criar}>
            <div className="grid-2" style={{ gap: 14 }}>
              <div className="form-group">
                <label className="form-label">Username *</label>
                <input className="form-control" required autoComplete="off"
                  value={form.username} onChange={e => setForm(p => ({ ...p, username: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">E-mail *</label>
                <input className="form-control" type="email" required autoComplete="off"
                  value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Senha *</label>
                <input className="form-control" type="password" required autoComplete="new-password"
                  value={form.password} onChange={e => setForm(p => ({ ...p, password: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Perfil</label>
                <select className="form-control" value={form.role}
                  onChange={e => setForm(p => ({ ...p, role: e.target.value }))}>
                  {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </div>
            <button type="submit" className={`btn btn-primary${salvando ? ' btn-loading' : ''}`} disabled={salvando}>
              {!salvando && '+ Criar Usuário'}
            </button>
          </form>
        </div>

        {/* ── Tabela de usuários ── */}
        <div className="card">
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 18 }}>
            Usuários cadastrados <span className="text-muted" style={{ fontWeight: 400, fontSize: 13 }}>({usuarios.length})</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>E-mail</th>
                  <th>Perfil</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {carregando
                  ? [1, 2, 3].map(i => (
                    <tr key={i} className="skeleton">
                      {[70, 90, 120, 50, 50, 40].map((w, j) => (
                        <td key={j}><span className="skeleton-line" style={{ width: w }} /></td>
                      ))}
                    </tr>
                  ))
                  : usuarios.map(u => (
                    <tr key={u.id}>
                      <td><code>{u.id}</code></td>
                      <td style={{ fontWeight: 600 }}>
                        {u.username}
                        {u.id === me?.id && <span className="text-muted" style={{ fontSize: 11, marginLeft: 6 }}>(você)</span>}
                      </td>
                      <td className="text-sm text-muted">{u.email}</td>
                      <td>
                        {editando?.id === u.id
                          ? (
                            <select className="form-control" style={{ padding: '4px 8px', fontSize: 13 }}
                              value={editando.role}
                              onChange={e => setEditando(p => ({ ...p, role: e.target.value }))}>
                              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                            </select>
                          )
                          : <span className={`badge ${ROLE_BADGE[u.role] || 'badge-gray'}`}>{u.role}</span>
                        }
                      </td>
                      <td>
                        {editando?.id === u.id
                          ? (
                            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 13 }}>
                              <input type="checkbox" checked={editando.is_active}
                                onChange={e => setEditando(p => ({ ...p, is_active: e.target.checked }))} />
                              Ativo
                            </label>
                          )
                          : (
                            <span className={`badge ${u.is_active ? 'badge-green' : 'badge-red'}`}>
                              {u.is_active ? 'Ativo' : 'Inativo'}
                            </span>
                          )
                        }
                      </td>
                      <td>
                        {u.id === me?.id
                          ? null
                          : editando?.id === u.id
                            ? (
                              <div className="flex gap-1">
                                <button className="btn btn-success btn-sm" onClick={() => salvarEdicao(u.id)}>Salvar</button>
                                <button className="btn btn-secondary btn-sm" onClick={() => setEditando(null)}>✕</button>
                              </div>
                            )
                            : (
                              <div className="flex gap-1">
                                <button className="btn btn-secondary btn-sm"
                                  onClick={() => setEditando({ id: u.id, role: u.role, is_active: u.is_active })}>
                                  Editar
                                </button>
                                <button className="btn btn-danger btn-sm"
                                  onClick={() => setConfirmDel({ id: u.id, username: u.username })}>
                                  Excluir
                                </button>
                              </div>
                            )
                        }
                      </td>
                    </tr>
                  ))
                }
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {confirmDel && (
        <ConfirmModal
          title="Excluir usuário"
          message={`O usuário "${confirmDel.username}" será removido permanentemente.`}
          confirmLabel="Excluir"
          loading={deletando}
          onConfirm={confirmarDelete}
          onCancel={() => !deletando && setConfirmDel(null)}
        />
      )}
    </Layout>
  )
}
