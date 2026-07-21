import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import api, { mensagemErro } from '../api'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [erro, setErro] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setErro(''); setLoading(true)
    try {
      const params = new URLSearchParams()
      params.append('username', form.username)
      params.append('password', form.password)
      const res = await api.post('/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      login(res.data.user, res.data.access_token)
      navigate('/documentos')
    } catch (err) {
      setErro(mensagemErro(err, 'Credenciais inválidas'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <div className="login-brand">A1<span>Doc</span></div>
        <p className="login-sub">Gestão Eletrônica de Documentos</p>

        {erro && <div className="alert alert-error">{erro}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Usuário</label>
            <input
              className="form-control"
              autoFocus
              autoComplete="username"
              value={form.username}
              onChange={e => setForm(p => ({ ...p, username: e.target.value }))}
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: 24 }}>
            <label className="form-label">Senha</label>
            <input
              className="form-control"
              type="password"
              autoComplete="current-password"
              value={form.password}
              onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
              required
            />
          </div>
          <button
            className="btn btn-primary w-full"
            style={{ justifyContent: 'center', padding: '12px', fontSize: 15 }}
            type="submit"
            disabled={loading}
          >
            {loading ? '⏳ Entrando...' : 'Entrar'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 20, fontSize: 12, color: 'var(--muted)' }}>
          Indoc · GED corporativo
        </p>
      </div>
    </div>
  )
}
