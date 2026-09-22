import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import ConfirmModal from '../components/ConfirmModal'
import api, { mensagemErro } from '../api'

function quando(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR')
}

/** Resume o user-agent: a string crua não diz nada a quem está lendo. */
function dispositivo(ua) {
  if (!ua) return 'Desconhecido'
  const so =
    /Windows/i.test(ua) ? 'Windows' :
    /Macintosh|Mac OS/i.test(ua) ? 'macOS' :
    /Android/i.test(ua) ? 'Android' :
    /iPhone|iPad/i.test(ua) ? 'iOS' :
    /Linux/i.test(ua) ? 'Linux' : 'Outro'
  const navegador =
    /Edg\//i.test(ua) ? 'Edge' :
    /Chrome\//i.test(ua) ? 'Chrome' :
    /Safari\//i.test(ua) && !/Chrome/i.test(ua) ? 'Safari' :
    /Firefox\//i.test(ua) ? 'Firefox' : 'Outro'
  return `${navegador} · ${so}`
}

export default function MinhasSessoes() {
  const [sessoes, setSessoes] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [msg, setMsg] = useState({ tipo: '', texto: '' })
  const [confirmTodas, setConfirmTodas] = useState(false)

  useEffect(() => { carregar() }, [])

  function flash(tipo, texto) {
    setMsg({ tipo, texto })
    setTimeout(() => setMsg({ tipo: '', texto: '' }), 4000)
  }

  async function carregar() {
    setCarregando(true)
    try { setSessoes((await api.get('/auth/sessoes')).data) }
    catch (err) { flash('error', mensagemErro(err, 'Erro ao carregar sessões')) }
    finally { setCarregando(false) }
  }

  async function revogar(id) {
    try {
      await api.delete(`/auth/sessoes/${id}`)
      flash('success', 'Sessão encerrada.')
      await carregar()
    } catch (err) {
      flash('error', mensagemErro(err, 'Erro ao encerrar a sessão'))
    }
  }

  async function revogarTodas() {
    try {
      const r = await api.post('/auth/sessoes/revogar-todas')
      flash('success', `${r.data.revogadas} sessão(ões) encerrada(s).`)
      await carregar()
    } catch (err) {
      flash('error', mensagemErro(err, 'Erro ao encerrar as sessões'))
    } finally {
      setConfirmTodas(false)
    }
  }

  const ativas = sessoes.filter(s => s.ativa)

  return (
    <Layout>
      <h1 className="page-title">Minhas sessões</h1>
      <p className="muted">
        Onde a sua conta está conectada. Encerrar uma sessão invalida o acesso
        dela imediatamente.
      </p>

      {msg.texto && <div className={`alert alert-${msg.tipo}`}>{msg.texto}</div>}

      {ativas.length > 1 && (
        <button className="btn btn-danger" onClick={() => setConfirmTodas(true)}>
          Encerrar as outras sessões
        </button>
      )}

      {carregando ? <p>Carregando…</p> : (
        <table className="table">
          <thead>
            <tr>
              <th>Dispositivo</th><th>IP</th><th>Início</th>
              <th>Último uso</th><th>Situação</th><th></th>
            </tr>
          </thead>
          <tbody>
            {sessoes.map(s => (
              <tr key={s.id}>
                <td>
                  {dispositivo(s.user_agent)}
                  {s.atual && <span className="badge badge-green" style={{ marginLeft: 8 }}>esta sessão</span>}
                  {s.provider !== 'local' && (
                    <span className="badge badge-blue" style={{ marginLeft: 8 }}>{s.provider}</span>
                  )}
                </td>
                <td>{s.ip || '—'}</td>
                <td>{quando(s.created_at)}</td>
                <td>{quando(s.last_used_at)}</td>
                <td>
                  <span className={`badge ${s.ativa ? 'badge-green' : 'badge-gray'}`}>
                    {s.ativa ? 'ativa' : 'encerrada'}
                  </span>
                </td>
                <td>
                  {s.ativa && !s.atual && (
                    <button className="btn btn-danger btn-sm" onClick={() => revogar(s.id)}>
                      Encerrar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {confirmTodas && (
        <ConfirmModal
          title="Encerrar as outras sessões?"
          message="Esta sessão continua ativa. As demais precisarão entrar de novo."
          confirmLabel="Encerrar"
          danger={false}
          onCancel={() => setConfirmTodas(false)}
          onConfirm={revogarTodas}
        />
      )}
    </Layout>
  )
}
