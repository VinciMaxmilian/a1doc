import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import GlassTabs from '../components/GlassTabs'
import ConfirmModal from '../components/ConfirmModal'
import api from '../api'

const ABAS = [
  { key: 'ambientes', label: 'Ambientes',    icon: '🌍' },
  { key: 'areas',     label: 'Áreas',        icon: '🏭' },
  { key: 'projetos',  label: 'Projetos',      icon: '📁' },
  { key: 'tipos',     label: 'Tipos de Doc.', icon: '📄' },
]

const SK_WIDTHS = ['75%', '55%', '85%', '45%', '65%']

function SkeletonRows({ cols, count = 3 }) {
  return Array.from({ length: count }, (_, i) => (
    <tr key={i} className="skeleton">
      {Array.from({ length: cols }, (_, j) => (
        <td key={j}><span className="skeleton-line" style={{ width: SK_WIDTHS[(i * cols + j) % SK_WIDTHS.length] }} /></td>
      ))}
    </tr>
  ))
}

export default function AdminHierarquia() {
  const [aba, setAba] = useState('ambientes')
  const [ambientes, setAmbientes] = useState([])
  const [areas, setAreas] = useState([])
  const [projetos, setProjetos] = useState([])
  const [tipos, setTipos] = useState([])
  const [campos, setCampos] = useState([])
  const [tipoSel, setTipoSel] = useState(null)
  const [selAmb, setSelAmb] = useState('')
  const [selArea, setSelArea] = useState('')
  const [novoNome, setNovoNome] = useState('')
  const [novoCampo, setNovoCampo] = useState({ nome: '', tipo: 'text', opcoes: '', ordem: 0 })
  const [msg, setMsg] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [salvando, setSalvando] = useState(false)
  const [confirmDel, setConfirmDel] = useState(null) // { endpoint, reload, label }
  const [deletando, setDeletando] = useState(false)

  useEffect(() => {
    Promise.all([
      api.get('/hierarquia/ambientes'),
      api.get('/hierarquia/tipos-documento'),
    ]).then(([a, t]) => {
      setAmbientes(a.data); setTipos(t.data)
    }).finally(() => setCarregando(false))
  }, [])

  function flash(m) { setMsg(m); setTimeout(() => setMsg(''), 3000) }

  async function rA()  { const r = await api.get('/hierarquia/ambientes'); setAmbientes(r.data) }
  async function rAr() { if (selAmb) { const r = await api.get('/hierarquia/areas', { params: { ambiente_id: selAmb } }); setAreas(r.data) } }
  async function rP()  { if (selArea) { const r = await api.get('/hierarquia/projetos', { params: { area_id: selArea } }); setProjetos(r.data) } }
  async function rT()  { const r = await api.get('/hierarquia/tipos-documento'); setTipos(r.data) }
  async function rC()  { if (tipoSel) { const r = await api.get(`/hierarquia/tipos-documento/${tipoSel.id}/campos`); setCampos(r.data) } }

  async function criar(endpoint, body, reload) {
    if (!novoNome.trim()) return
    setSalvando(true)
    try {
      await api.post(endpoint, body)
      setNovoNome(''); await reload(); flash('Criado com sucesso!')
    } finally { setSalvando(false) }
  }

  async function confirmarDelete() {
    if (!confirmDel) return
    setDeletando(true)
    try {
      await api.delete(confirmDel.endpoint)
      await confirmDel.reload()
      flash('Excluído.')
    } finally {
      setDeletando(false)
      setConfirmDel(null)
    }
  }

  async function loadAreas(id) {
    setSelAmb(id); setAreas([]); setProjetos([])
    if (id) { const r = await api.get('/hierarquia/areas', { params: { ambiente_id: id } }); setAreas(r.data) }
  }

  async function loadProj(id) {
    setSelArea(id); setProjetos([])
    if (id) { const r = await api.get('/hierarquia/projetos', { params: { area_id: id } }); setProjetos(r.data) }
  }

  async function loadCampos(tipo) {
    setTipoSel(tipo)
    const r = await api.get(`/hierarquia/tipos-documento/${tipo.id}/campos`)
    setCampos(r.data)
  }

  async function criarCampo() {
    if (!novoCampo.nome || !tipoSel) return
    setSalvando(true)
    try {
      const opts = novoCampo.tipo === 'select' && novoCampo.opcoes
        ? novoCampo.opcoes.split(',').map(s => s.trim()).filter(Boolean) : null
      await api.post(`/hierarquia/tipos-documento/${tipoSel.id}/campos`, {
        tipo_documento_id: tipoSel.id, nome: novoCampo.nome,
        tipo: novoCampo.tipo, opcoes: opts, ordem: parseInt(novoCampo.ordem) || 0,
      })
      setNovoCampo({ nome: '', tipo: 'text', opcoes: '', ordem: 0 })
      await rC(); flash('Campo criado!')
    } finally { setSalvando(false) }
  }

  return (
    <Layout>
      <div className="page-header"><h1>🏗️ Hierarquia Organizacional</h1></div>
      <div className="page-body">
        {msg && <div className="alert alert-success">{msg}</div>}

        <div className="card">
          <GlassTabs tabs={ABAS} active={aba} onChange={t => { setAba(t); setNovoNome('') }} />

          {/* ── Ambientes ── */}
          {aba === 'ambientes' && (
            <div>
              <div className="flex gap-2 mb-4 flex-wrap">
                <input className="form-control" style={{ maxWidth: 300 }} placeholder="Nome do ambiente"
                  value={novoNome} onChange={e => setNovoNome(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && criar('/hierarquia/ambientes', { nome: novoNome }, rA)} />
                <button
                  className={`btn btn-primary${salvando ? ' btn-loading' : ''}`}
                  disabled={salvando || !novoNome.trim()}
                  onClick={() => criar('/hierarquia/ambientes', { nome: novoNome }, rA)}
                >
                  {!salvando && '+ Adicionar'}
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>ID</th><th>Nome</th><th></th></tr></thead>
                  <tbody>
                    {carregando
                      ? <SkeletonRows cols={3} />
                      : ambientes.length
                        ? ambientes.map(a => (
                          <tr key={a.id}>
                            <td><code>{a.id}</code></td>
                            <td style={{ fontWeight: 500 }}>{a.nome}</td>
                            <td>
                              <button className="btn btn-danger btn-sm"
                                onClick={() => setConfirmDel({ endpoint: `/hierarquia/ambientes/${a.id}`, reload: rA, label: a.nome })}>
                                Excluir
                              </button>
                            </td>
                          </tr>
                        ))
                        : <tr><td colSpan={3}><div className="empty-state" style={{ padding: 28 }}>Nenhum ambiente cadastrado</div></td></tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Areas ── */}
          {aba === 'areas' && (
            <div>
              <div className="flex gap-2 mb-4 flex-wrap">
                <select className="form-control" style={{ maxWidth: 220 }} value={selAmb} onChange={e => loadAreas(e.target.value)}>
                  <option value="">Selecione o Ambiente</option>
                  {ambientes.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
                </select>
                <input className="form-control" style={{ maxWidth: 220 }} placeholder="Nome da área"
                  value={novoNome} onChange={e => setNovoNome(e.target.value)} disabled={!selAmb}
                  onKeyDown={e => e.key === 'Enter' && criar('/hierarquia/areas', { nome: novoNome, ambiente_id: parseInt(selAmb) }, rAr)} />
                <button
                  className={`btn btn-primary${salvando ? ' btn-loading' : ''}`}
                  disabled={salvando || !selAmb || !novoNome.trim()}
                  onClick={() => criar('/hierarquia/areas', { nome: novoNome, ambiente_id: parseInt(selAmb) }, rAr)}
                >
                  {!salvando && '+ Adicionar'}
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>ID</th><th>Nome</th><th></th></tr></thead>
                  <tbody>
                    {!selAmb
                      ? <tr><td colSpan={3}><div style={{ padding: 16, color: 'var(--muted)', textAlign: 'center' }}>Selecione um ambiente acima</div></td></tr>
                      : areas.length
                        ? areas.map(a => (
                          <tr key={a.id}>
                            <td><code>{a.id}</code></td>
                            <td style={{ fontWeight: 500 }}>{a.nome}</td>
                            <td>
                              <button className="btn btn-danger btn-sm"
                                onClick={() => setConfirmDel({ endpoint: `/hierarquia/areas/${a.id}`, reload: rAr, label: a.nome })}>
                                Excluir
                              </button>
                            </td>
                          </tr>
                        ))
                        : <tr><td colSpan={3}><div className="empty-state" style={{ padding: 28 }}>Nenhuma área neste ambiente</div></td></tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Projetos ── */}
          {aba === 'projetos' && (
            <div>
              <div className="flex gap-2 mb-4 flex-wrap">
                <select className="form-control" style={{ maxWidth: 180 }} value={selAmb}
                  onChange={e => { loadAreas(e.target.value); setSelArea('') }}>
                  <option value="">Ambiente</option>
                  {ambientes.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
                </select>
                <select className="form-control" style={{ maxWidth: 180 }} value={selArea}
                  onChange={e => loadProj(e.target.value)} disabled={!areas.length}>
                  <option value="">Área</option>
                  {areas.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
                </select>
                <input className="form-control" style={{ maxWidth: 200 }} placeholder="Nome do projeto"
                  value={novoNome} onChange={e => setNovoNome(e.target.value)} disabled={!selArea}
                  onKeyDown={e => e.key === 'Enter' && criar('/hierarquia/projetos', { nome: novoNome, area_id: parseInt(selArea) }, rP)} />
                <button
                  className={`btn btn-primary${salvando ? ' btn-loading' : ''}`}
                  disabled={salvando || !selArea || !novoNome.trim()}
                  onClick={() => criar('/hierarquia/projetos', { nome: novoNome, area_id: parseInt(selArea) }, rP)}
                >
                  {!salvando && '+ Adicionar'}
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>ID</th><th>Nome</th><th></th></tr></thead>
                  <tbody>
                    {!selArea
                      ? <tr><td colSpan={3}><div style={{ padding: 16, color: 'var(--muted)', textAlign: 'center' }}>Selecione Ambiente → Área acima</div></td></tr>
                      : projetos.length
                        ? projetos.map(p => (
                          <tr key={p.id}>
                            <td><code>{p.id}</code></td>
                            <td style={{ fontWeight: 500 }}>{p.nome}</td>
                            <td>
                              <button className="btn btn-danger btn-sm"
                                onClick={() => setConfirmDel({ endpoint: `/hierarquia/projetos/${p.id}`, reload: rP, label: p.nome })}>
                                Excluir
                              </button>
                            </td>
                          </tr>
                        ))
                        : <tr><td colSpan={3}><div className="empty-state" style={{ padding: 28 }}>Nenhum projeto nesta área</div></td></tr>
                    }
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Tipos de Doc ── */}
          {aba === 'tipos' && (
            <div className="grid-2" style={{ gap: 20, alignItems: 'start' }}>
              <div>
                <div className="flex gap-2 mb-4">
                  <input className="form-control" placeholder="Nome do tipo"
                    value={novoNome} onChange={e => setNovoNome(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && criar('/hierarquia/tipos-documento', { nome: novoNome }, rT)} />
                  <button
                    className={`btn btn-primary${salvando ? ' btn-loading' : ''}`}
                    disabled={salvando || !novoNome.trim()}
                    onClick={() => criar('/hierarquia/tipos-documento', { nome: novoNome }, rT)}
                  >
                    {!salvando && '+ Add'}
                  </button>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Nome</th><th></th><th></th></tr></thead>
                    <tbody>
                      {carregando
                        ? <SkeletonRows cols={3} />
                        : tipos.length
                          ? tipos.map(t => (
                            <tr key={t.id} style={{ cursor: 'pointer' }}>
                              <td
                                onClick={() => loadCampos(t)}
                                style={{ fontWeight: tipoSel?.id === t.id ? 700 : 500, color: tipoSel?.id === t.id ? 'var(--blue)' : 'inherit' }}
                              >
                                {tipoSel?.id === t.id ? '▶ ' : ''}{t.nome}
                              </td>
                              <td>
                                <button className="btn btn-secondary btn-sm" onClick={() => loadCampos(t)}>Campos</button>
                              </td>
                              <td>
                                <button className="btn btn-danger btn-sm"
                                  onClick={() => setConfirmDel({ endpoint: `/hierarquia/tipos-documento/${t.id}`, reload: rT, label: t.nome })}>
                                  Excluir
                                </button>
                              </td>
                            </tr>
                          ))
                          : <tr><td colSpan={3}><div className="empty-state" style={{ padding: 28 }}>Nenhum tipo cadastrado</div></td></tr>
                      }
                    </tbody>
                  </table>
                </div>
              </div>

              {tipoSel && (
                <div style={{ background: 'rgba(248,250,252,0.7)', backdropFilter: 'blur(12px)', border: '1px solid rgba(226,232,240,0.7)', borderRadius: 12, padding: 20 }}>
                  <div style={{ fontWeight: 700, marginBottom: 16, color: 'var(--blue)' }}>
                    📝 Campos: {tipoSel.nome}
                  </div>
                  <div className="form-group">
                    <label className="form-label">Nome do Campo</label>
                    <input className="form-control" value={novoCampo.nome}
                      onChange={e => setNovoCampo(p => ({ ...p, nome: e.target.value }))} />
                  </div>
                  <div className="grid-2">
                    <div className="form-group">
                      <label className="form-label">Tipo</label>
                      <select className="form-control" value={novoCampo.tipo}
                        onChange={e => setNovoCampo(p => ({ ...p, tipo: e.target.value }))}>
                        <option value="text">Texto</option>
                        <option value="number">Número</option>
                        <option value="date">Data</option>
                        <option value="select">Seleção</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Ordem</label>
                      <input className="form-control" type="number" value={novoCampo.ordem}
                        onChange={e => setNovoCampo(p => ({ ...p, ordem: e.target.value }))} />
                    </div>
                  </div>
                  {novoCampo.tipo === 'select' && (
                    <div className="form-group">
                      <label className="form-label">Opções (separar por vírgula)</label>
                      <input className="form-control" value={novoCampo.opcoes} placeholder="Op1, Op2, Op3"
                        onChange={e => setNovoCampo(p => ({ ...p, opcoes: e.target.value }))} />
                    </div>
                  )}
                  <button
                    className={`btn btn-primary mb-4${salvando ? ' btn-loading' : ''}`}
                    disabled={salvando || !novoCampo.nome}
                    onClick={criarCampo}
                  >
                    {!salvando && '+ Adicionar Campo'}
                  </button>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>Nome</th><th>Tipo</th><th>Ord.</th><th></th></tr></thead>
                      <tbody>
                        {campos.map(c => (
                          <tr key={c.id}>
                            <td style={{ fontWeight: 500 }}>{c.nome}</td>
                            <td className="text-sm text-muted">{c.tipo}</td>
                            <td className="text-sm">{c.ordem}</td>
                            <td>
                              <button className="btn btn-danger btn-sm"
                                onClick={() => setConfirmDel({ endpoint: `/hierarquia/campos/${c.id}`, reload: rC, label: c.nome })}>
                                Excluir
                              </button>
                            </td>
                          </tr>
                        ))}
                        {!campos.length && (
                          <tr><td colSpan={4}><div style={{ padding: '12px 0', color: 'var(--muted)', textAlign: 'center', fontSize: 13 }}>Nenhum campo ainda</div></td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {confirmDel && (
        <ConfirmModal
          title="Excluir item"
          message={`"${confirmDel.label}" será removido permanentemente. Itens filhos também serão excluídos.`}
          confirmLabel="Excluir"
          loading={deletando}
          onConfirm={confirmarDelete}
          onCancel={() => !deletando && setConfirmDel(null)}
        />
      )}
    </Layout>
  )
}
