import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import GlassTabs from '../components/GlassTabs'
import ConfirmModal from '../components/ConfirmModal'
import api, { mensagemErro } from '../api'

const ABAS = [
  { key: 'fluxos',     label: 'Fluxos',     icon: '🔵' },
  { key: 'atividades', label: 'Atividades',  icon: '⚡' },
  { key: 'transicoes', label: 'Transições',  icon: '🔀' },
]

function SkeletonRows({ cols, count = 3 }) {
  const ws = ['75%', '55%', '85%', '45%', '65%']
  return Array.from({ length: count }, (_, i) => (
    <tr key={i} className="skeleton">
      {Array.from({ length: cols }, (_, j) => (
        <td key={j}><span className="skeleton-line" style={{ width: ws[(i * cols + j) % ws.length] }} /></td>
      ))}
    </tr>
  ))
}

export default function AdminWorkflow() {
  const [aba, setAba] = useState('fluxos')
  const [fluxos, setFluxos] = useState([])
  const [atividades, setAtividades] = useState([])
  const [transicoes, setTransicoes] = useState([])
  const [msg, setMsg] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(false)
  const [confirmDel, setConfirmDel] = useState(null) // { endpoint, label }
  const [deletando, setDeletando] = useState(false)

  const [novoFluxo, setNovoFluxo] = useState({ nome: '', descricao: '' })
  const [novaAtiv, setNovaAtiv] = useState({ nome: '', fluxo_id: '', ordem: '', role_requerido: '' })
  const [novaTrans, setNovaTrans] = useState({
    atividade_origem_id: '', acao: 'aprovado', atividade_destino_id: '', gera_nova_revisao: false,
  })

  useEffect(() => { carregar() }, [])

  async function carregar() {
    setCarregando(true)
    try {
      const [f, a, t] = await Promise.all([
        api.get('/workflow/fluxos'),
        api.get('/workflow/atividades'),
        api.get('/workflow/transicoes'),
      ])
      setFluxos(f.data); setAtividades(a.data); setTransicoes(t.data)
    } finally {
      setCarregando(false)
    }
  }

  function flash(m) { setMsg(m); setTimeout(() => setMsg(''), 3000) }

  async function criarFluxo() {
    if (!novoFluxo.nome) return
    setSalvando(true)
    try {
      await api.post('/workflow/fluxos', { nome: novoFluxo.nome, descricao: novoFluxo.descricao || null })
      setNovoFluxo({ nome: '', descricao: '' })
      await carregar(); flash('Fluxo criado!')
    } finally { setSalvando(false) }
  }

  async function criarAtiv() {
    if (!novaAtiv.nome || !novaAtiv.fluxo_id) return
    setSalvando(true)
    try {
      await api.post('/workflow/atividades', {
        nome: novaAtiv.nome,
        fluxo_id: parseInt(novaAtiv.fluxo_id),
        ordem: novaAtiv.ordem === '' ? 0 : parseInt(novaAtiv.ordem),
        role_requerido: novaAtiv.role_requerido || null,
      })
      setNovaAtiv({ nome: '', fluxo_id: '', ordem: '', role_requerido: '' })
      await carregar(); flash('Atividade criada!')
    } catch (err) {
      flash(mensagemErro(err, 'Erro ao criar atividade'))
    } finally { setSalvando(false) }
  }

  async function criarTrans() {
    if (!novaTrans.atividade_origem_id || !novaTrans.atividade_destino_id) return
    setSalvando(true)
    try {
      await api.post('/workflow/transicoes', {
        atividade_origem_id: parseInt(novaTrans.atividade_origem_id),
        acao: novaTrans.acao,
        atividade_destino_id: parseInt(novaTrans.atividade_destino_id),
        gera_nova_revisao: novaTrans.gera_nova_revisao,
      })
      setNovaTrans({ atividade_origem_id: '', acao: 'aprovado', atividade_destino_id: '', gera_nova_revisao: false })
      await carregar(); flash('Transição salva!')
    } catch (err) {
      flash(err.response?.data?.detail || 'Erro ao salvar')
    } finally { setSalvando(false) }
  }

  async function confirmarDelete() {
    if (!confirmDel) return
    setDeletando(true)
    try {
      await api.delete(confirmDel.endpoint)
      await carregar()
      flash('Excluído.')
    } finally {
      setDeletando(false)
      setConfirmDel(null)
    }
  }

  function labelAtiv(id) {
    const a = atividades.find(x => x.id === parseInt(id))
    if (!a) return String(id)
    const f = fluxos.find(x => x.id === a.fluxo_id)
    return f ? `[Fluxo ${f.numero}] ${a.nome}` : a.nome
  }

  return (
    <Layout>
      <div className="page-header"><h1>⚙️ Configuração de Workflow</h1></div>
      <div className="page-body">
        {msg && <div className={`alert ${msg.includes('Erro') ? 'alert-error' : 'alert-success'}`}>{msg}</div>}

        <div className="alert alert-info" style={{ marginBottom: 20 }}>
          Ordem: <strong>1. Criar Fluxos → 2. Criar Atividades → 3. Configurar Transições</strong>.
          O <strong>Fluxo 0</strong> é o estado inicial dos documentos após upload.
        </div>

        <div className="card">
          <GlassTabs tabs={ABAS} active={aba} onChange={setAba} />

          {/* ── Fluxos ── */}
          {aba === 'fluxos' && (
            <div>
              <div className="flex gap-2 mb-4 flex-wrap">
                <input className="form-control" placeholder="Nome do fluxo" style={{ maxWidth: 260 }}
                  value={novoFluxo.nome}
                  onChange={e => setNovoFluxo(p => ({ ...p, nome: e.target.value }))}
                  onKeyDown={e => e.key === 'Enter' && criarFluxo()} />
                <input className="form-control" placeholder="Descrição (opcional)" style={{ maxWidth: 220 }}
                  value={novoFluxo.descricao}
                  onChange={e => setNovoFluxo(p => ({ ...p, descricao: e.target.value }))} />
                <button
                  className={`btn btn-primary${salvando ? ' btn-loading' : ''}`}
                  onClick={criarFluxo}
                  disabled={salvando || !novoFluxo.nome}
                >
                  {!salvando && '+ Adicionar'}
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Nº</th><th>Nome</th><th>Descrição</th><th>Atividades</th><th></th></tr></thead>
                  <tbody>
                    {carregando
                      ? <SkeletonRows cols={5} />
                      : fluxos.length
                        ? fluxos.map(f => (
                          <tr key={f.id}>
                            <td><span className="badge badge-blue">Fluxo {f.numero}</span></td>
                            <td style={{ fontWeight: 500 }}>{f.nome}</td>
                            <td className="text-muted text-sm">{f.descricao || '—'}</td>
                            <td className="text-sm text-muted">{f.atividades?.length || 0} atividade(s)</td>
                            <td>
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => setConfirmDel({ endpoint: `/workflow/fluxos/${f.id}`, label: `Fluxo ${f.numero} — ${f.nome}` })}
                              >
                                Excluir
                              </button>
                            </td>
                          </tr>
                        ))
                        : <tr><td colSpan={5}><div className="empty-state" style={{ padding: 28 }}>Nenhum fluxo criado</div></td></tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Atividades ── */}
          {aba === 'atividades' && (
            <div>
              <div className="flex gap-2 mb-4 flex-wrap">
                <select className="form-control" style={{ maxWidth: 240 }} value={novaAtiv.fluxo_id}
                  onChange={e => setNovaAtiv(p => ({ ...p, fluxo_id: e.target.value }))}>
                  <option value="">Selecione o Fluxo</option>
                  {fluxos.map(f => <option key={f.id} value={f.id}>Fluxo {f.numero} — {f.nome}</option>)}
                </select>
                <input className="form-control" placeholder="Nome da atividade" style={{ maxWidth: 260 }}
                  value={novaAtiv.nome}
                  onChange={e => setNovaAtiv(p => ({ ...p, nome: e.target.value }))}
                  onKeyDown={e => e.key === 'Enter' && criarAtiv()} />
                <input className="form-control" type="number" placeholder="Ordem" style={{ maxWidth: 100 }}
                  title="Define a sequência das atividades no fluxo"
                  value={novaAtiv.ordem}
                  onChange={e => setNovaAtiv(p => ({ ...p, ordem: e.target.value }))} />
                <select className="form-control" style={{ maxWidth: 200 }}
                  title="Papel exigido para aprovar/reprovar nesta atividade"
                  value={novaAtiv.role_requerido}
                  onChange={e => setNovaAtiv(p => ({ ...p, role_requerido: e.target.value }))}>
                  <option value="">Qualquer usuário</option>
                  <option value="user">Somente user</option>
                  <option value="admin">Somente admin</option>
                  <option value="dev">Somente dev</option>
                </select>
                <button
                  className={`btn btn-primary${salvando ? ' btn-loading' : ''}`}
                  onClick={criarAtiv}
                  disabled={salvando || !novaAtiv.nome || !novaAtiv.fluxo_id}
                >
                  {!salvando && '+ Adicionar'}
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Fluxo</th><th>Ordem</th><th>Atividade</th><th>Quem pode aprovar</th><th></th></tr></thead>
                  <tbody>
                    {carregando
                      ? <SkeletonRows cols={5} />
                      : atividades.length
                        ? fluxos.flatMap(f =>
                          (f.atividades || []).map(a => (
                            <tr key={a.id}>
                              <td><span className="badge badge-blue">Fluxo {f.numero}</span></td>
                              <td className="text-sm text-muted">{a.ordem ?? 0}</td>
                              <td style={{ fontWeight: 500 }}>{a.nome}</td>
                              <td className="text-sm">
                                {a.role_requerido
                                  ? <span className="badge badge-blue" style={{ fontSize: 11 }}>{a.role_requerido}</span>
                                  : <span className="text-muted">qualquer usuário</span>}
                              </td>
                              <td>
                                <button
                                  className="btn btn-danger btn-sm"
                                  onClick={() => setConfirmDel({ endpoint: `/workflow/atividades/${a.id}`, label: a.nome })}
                                >
                                  Excluir
                                </button>
                              </td>
                            </tr>
                          ))
                        )
                        : <tr><td colSpan={5}><div className="empty-state" style={{ padding: 28 }}>Nenhuma atividade criada</div></td></tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Transições ── */}
          {aba === 'transicoes' && (
            <div>
              <div style={{ background: 'rgba(248,250,252,0.7)', backdropFilter: 'blur(12px)', border: '1px solid rgba(226,232,240,0.7)', borderRadius: 12, padding: 20, marginBottom: 24 }}>
                <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--muted)', marginBottom: 14 }}>Nova Regra de Transição</div>
                <div className="grid-2" style={{ gap: 12 }}>
                  <div className="form-group">
                    <label className="form-label">Atividade Origem</label>
                    <select className="form-control" value={novaTrans.atividade_origem_id}
                      onChange={e => setNovaTrans(p => ({ ...p, atividade_origem_id: e.target.value }))}>
                      <option value="">Selecione...</option>
                      {atividades.map(a => <option key={a.id} value={a.id}>{labelAtiv(a.id)}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Ação</label>
                    <select className="form-control" value={novaTrans.acao}
                      onChange={e => setNovaTrans(p => ({ ...p, acao: e.target.value }))}>
                      <option value="aprovado">✓ Aprovado</option>
                      <option value="reprovado">✗ Reprovado</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Atividade Destino</label>
                    <select className="form-control" value={novaTrans.atividade_destino_id}
                      onChange={e => setNovaTrans(p => ({ ...p, atividade_destino_id: e.target.value }))}>
                      <option value="">Selecione...</option>
                      {atividades.map(a => <option key={a.id} value={a.id}>{labelAtiv(a.id)}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Gera Nova Revisão?</label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 10, cursor: 'pointer', userSelect: 'none' }}>
                      <input type="checkbox" style={{ width: 16, height: 16, accentColor: 'var(--blue)' }}
                        checked={novaTrans.gera_nova_revisao}
                        onChange={e => setNovaTrans(p => ({ ...p, gera_nova_revisao: e.target.checked }))} />
                      <span>Sim — Rev 1 → 2 → 3...</span>
                    </label>
                  </div>
                </div>
                <button
                  className={`btn btn-primary${salvando ? ' btn-loading' : ''}`}
                  onClick={criarTrans}
                  disabled={salvando || !novaTrans.atividade_origem_id || !novaTrans.atividade_destino_id}
                >
                  {!salvando && '+ Salvar Transição'}
                </button>
              </div>

              <div className="table-wrap">
                <table>
                  <thead><tr><th>Origem</th><th>Ação</th><th>Destino</th><th>Nova Rev.</th><th></th></tr></thead>
                  <tbody>
                    {carregando
                      ? <SkeletonRows cols={5} />
                      : transicoes.length
                        ? transicoes.map(t => (
                          <tr key={t.id}>
                            <td className="text-sm">{t.atividade_origem_nome}</td>
                            <td>
                              <span className={`badge ${t.acao === 'aprovado' ? 'badge-green' : 'badge-red'}`}>
                                {t.acao === 'aprovado' ? '✓' : '✗'} {t.acao}
                              </span>
                            </td>
                            <td className="text-sm">{t.atividade_destino_nome}</td>
                            <td>
                              {t.gera_nova_revisao
                                ? <span className="badge badge-orange">↑ Sim</span>
                                : <span className="text-muted">—</span>}
                            </td>
                            <td>
                              <button
                                className="btn btn-danger btn-sm"
                                onClick={() => setConfirmDel({ endpoint: `/workflow/transicoes/${t.id}`, label: `${t.atividade_origem_nome} → ${t.acao} → ${t.atividade_destino_nome}` })}
                              >
                                Excluir
                              </button>
                            </td>
                          </tr>
                        ))
                        : <tr><td colSpan={5}><div className="empty-state" style={{ padding: 28 }}>Nenhuma transição configurada</div></td></tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      {confirmDel && (
        <ConfirmModal
          title="Excluir item"
          message={`"${confirmDel.label}" será removido permanentemente.`}
          confirmLabel="Excluir"
          loading={deletando}
          onConfirm={confirmarDelete}
          onCancel={() => !deletando && setConfirmDel(null)}
        />
      )}
    </Layout>
  )
}
