import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import api from '../api'

const LIMIT = 20

export default function Documentos() {
  const [docs, setDocs] = useState([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [loading, setLoading] = useState(false)

  const [filtro, setFiltro] = useState({
    nome: '', ambiente_id: '', area_id: '', projeto_id: '', tipo_documento_id: '',
  })
  const [ambientes, setAmbientes] = useState([])
  const [areas, setAreas] = useState([])
  const [projetos, setProjetos] = useState([])
  const [tipos, setTipos] = useState([])

  useEffect(() => {
    api.get('/hierarquia/ambientes').then(r => setAmbientes(r.data))
    api.get('/hierarquia/tipos-documento').then(r => setTipos(r.data))
    buscar(0)
  }, [])

  const buscar = useCallback(async (skipOverride = 0) => {
    setLoading(true)
    const s = skipOverride
    setSkip(s)
    try {
      const params = { skip: s, limit: LIMIT }
      if (filtro.nome)              params.nome             = filtro.nome
      if (filtro.ambiente_id)       params.ambiente_id       = filtro.ambiente_id
      if (filtro.area_id)           params.area_id           = filtro.area_id
      if (filtro.projeto_id)        params.projeto_id        = filtro.projeto_id
      if (filtro.tipo_documento_id) params.tipo_documento_id = filtro.tipo_documento_id
      const res = await api.get('/documentos', { params })
      setDocs(res.data.itens)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }, [filtro])

  async function onAmbiente(id) {
    setFiltro(p => ({ ...p, ambiente_id: id, area_id: '', projeto_id: '' }))
    setAreas([]); setProjetos([])
    if (id) {
      const r = await api.get('/hierarquia/areas', { params: { ambiente_id: id } })
      setAreas(r.data)
    }
  }

  async function onArea(id) {
    setFiltro(p => ({ ...p, area_id: id, projeto_id: '' }))
    setProjetos([])
    if (id) {
      const r = await api.get('/hierarquia/projetos', { params: { area_id: id } })
      setProjetos(r.data)
    }
  }

  function limpar() {
    setFiltro({ nome: '', ambiente_id: '', area_id: '', projeto_id: '', tipo_documento_id: '' })
    setAreas([]); setProjetos([])
    setTimeout(() => buscar(0), 0)
  }

  function badgeFluxo(doc) {
    if (!doc.atividade_atual) return <span className="badge badge-gray">Sem fluxo</span>
    const n = doc.atividade_atual.fluxo?.numero
    const nome = doc.atividade_atual.nome
    const cor = n === 0 ? 'badge-orange' : 'badge-blue'
    return (
      <span className={`badge ${cor}`}>
        <span className={`status-dot ${n === 0 ? 'orange' : 'blue'}`}></span>
        F{n} · {nome}
      </span>
    )
  }

  const pagAtual = Math.floor(skip / LIMIT) + 1
  const totalPags = Math.ceil(total / LIMIT)

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1>Documentos</h1>
          <div className="sub">{total > 0 ? `${total} documento${total !== 1 ? 's' : ''}` : 'Nenhum resultado'}</div>
        </div>
        <Link to="/documentos/upload" className="btn btn-primary">+ Novo Upload</Link>
      </div>

      <div className="page-body">
        {/* ── Filtros ── */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="filter-bar">
            <div className="filter-item">
              <div className="form-group">
                <label className="form-label">Ambiente</label>
                <select className="form-control" value={filtro.ambiente_id}
                  onChange={e => onAmbiente(e.target.value)}>
                  <option value="">Todos</option>
                  {ambientes.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
                </select>
              </div>
            </div>
            <div className="filter-item">
              <div className="form-group">
                <label className="form-label">Área</label>
                <select className="form-control" value={filtro.area_id}
                  onChange={e => onArea(e.target.value)} disabled={!areas.length}>
                  <option value="">Todas</option>
                  {areas.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
                </select>
              </div>
            </div>
            <div className="filter-item">
              <div className="form-group">
                <label className="form-label">Projeto</label>
                <select className="form-control" value={filtro.projeto_id}
                  onChange={e => setFiltro(p => ({ ...p, projeto_id: e.target.value }))}
                  disabled={!projetos.length}>
                  <option value="">Todos</option>
                  {projetos.map(p => <option key={p.id} value={p.id}>{p.nome}</option>)}
                </select>
              </div>
            </div>
            <div className="filter-item">
              <div className="form-group">
                <label className="form-label">Tipo</label>
                <select className="form-control" value={filtro.tipo_documento_id}
                  onChange={e => setFiltro(p => ({ ...p, tipo_documento_id: e.target.value }))}>
                  <option value="">Todos</option>
                  {tipos.map(t => <option key={t.id} value={t.id}>{t.nome}</option>)}
                </select>
              </div>
            </div>
            <div style={{ flex: 2, minWidth: 180 }}>
              <div className="form-group">
                <label className="form-label">Nome</label>
                <input className="form-control" placeholder="Buscar por nome..."
                  value={filtro.nome}
                  onChange={e => setFiltro(p => ({ ...p, nome: e.target.value }))}
                  onKeyDown={e => e.key === 'Enter' && buscar(0)} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', paddingBottom: 0 }}>
              <button className="btn btn-primary" onClick={() => buscar(0)}>Buscar</button>
              <button className="btn btn-secondary" onClick={limpar}>Limpar</button>
            </div>
          </div>

          {/* ── Tabela ── */}
          {loading ? (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--muted)' }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
              Carregando...
            </div>
          ) : (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Código</th>
                      <th>Nome</th>
                      <th>Rev.</th>
                      <th>Fluxo / Atividade</th>
                      <th>Responsável</th>
                      <th>Data</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {docs.length === 0 && (
                      <tr>
                        <td colSpan={7}>
                          <div className="empty-state">
                            <span className="empty-icon">📭</span>
                            <strong>Nenhum documento encontrado</strong>
                            <p>Tente ajustar os filtros ou faça um novo upload.</p>
                          </div>
                        </td>
                      </tr>
                    )}
                    {docs.map(d => (
                      <tr key={d.id}>
                        <td><code>{d.codigo}</code></td>
                        <td style={{ fontWeight: 500 }}>{d.nome}</td>
                        <td>
                          <span className="badge badge-green">Rev {d.revisao_label}</span>
                        </td>
                        <td>{badgeFluxo(d)}</td>
                        <td className="text-sm text-muted">{d.responsavel?.username}</td>
                        <td className="text-sm text-muted">
                          {new Date(d.created_at).toLocaleDateString('pt-BR')}
                        </td>
                        <td>
                          <Link to={`/documentos/${d.id}`} className="btn btn-secondary btn-sm">
                            Ver →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* ── Paginação ── */}
              {total > 0 && (
                <div className="pagination">
                  <span className="pagination-info">
                    {skip + 1}–{Math.min(skip + LIMIT, total)} de <strong>{total}</strong> documentos
                    {totalPags > 1 && ` · Página ${pagAtual} de ${totalPags}`}
                  </span>
                  <div className="flex gap-2">
                    <button
                      className="pagination-btn"
                      disabled={skip === 0}
                      onClick={() => buscar(skip - LIMIT)}
                    >
                      ← Anterior
                    </button>
                    <button
                      className="pagination-btn"
                      disabled={skip + LIMIT >= total}
                      onClick={() => buscar(skip + LIMIT)}
                    >
                      Próxima →
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Layout>
  )
}
