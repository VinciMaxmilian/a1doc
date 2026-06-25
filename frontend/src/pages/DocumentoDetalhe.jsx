import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import GlassTabs from '../components/GlassTabs'
import Modal from '../components/Modal'
import { useAuth } from '../contexts/AuthContext'
import api from '../api'

const ABAS = [
  { key: 'arquivos',   label: 'Arquivos',            icon: '📎' },
  { key: 'historico',  label: 'Histórico Workflow',   icon: '🔄' },
  { key: 'formulario', label: 'Formulário de Dados',  icon: '📝' },
]

const MAX_SIZE = 100 * 1024 * 1024

export default function DocumentoDetalhe() {
  const { id } = useParams()
  const { isAdmin } = useAuth()
  const nav = useNavigate()
  const fileRef = useRef()

  const [doc, setDoc] = useState(null)
  const [aba, setAba] = useState('arquivos')
  const [loading, setLoading] = useState(true)
  const [editando, setEditando] = useState(false)
  const [valores, setValores] = useState({})
  const [salvandoCampos, setSalvandoCampos] = useState(false)

  const [modalUpload, setModalUpload] = useState(false)
  const [arquivoNovo, setArquivoNovo] = useState(null)
  const [obsUpload, setObsUpload] = useState('')
  const [uploadOver, setUploadOver] = useState(false)
  const [uploading, setUploading] = useState(false)

  const [msg, setMsg] = useState({ tipo: '', texto: '' })

  useEffect(() => { carregar() }, [id])

  async function carregar() {
    setLoading(true)
    try {
      const res = await api.get(`/documentos/${id}`)
      setDoc(res.data)
      const v = {}
      res.data.valores_campos?.forEach(c => { v[c.campo_id] = c.valor || '' })
      setValores(v)
    } finally { setLoading(false) }
  }

  function flash(tipo, texto) {
    setMsg({ tipo, texto })
    setTimeout(() => setMsg({ tipo: '', texto: '' }), 4000)
  }

  async function salvarCampos() {
    setSalvandoCampos(true)
    try {
      const lista = Object.entries(valores).map(([campo_id, valor]) => ({
        campo_id: parseInt(campo_id), valor,
      }))
      await api.put(`/documentos/${id}/campos`, { valores: lista })
      setEditando(false)
      flash('success', 'Campos salvos!')
      carregar()
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Erro ao salvar')
    } finally { setSalvandoCampos(false) }
  }

  async function enviarNovoArquivo() {
    if (!arquivoNovo) return
    if (arquivoNovo.size > MAX_SIZE) { flash('error', 'Arquivo excede 100MB'); return }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('arquivo', arquivoNovo)
      if (obsUpload.trim()) fd.append('observacao', obsUpload.trim())
      const res = await api.post(`/documentos/${id}/upload-revisao`, fd)
      setDoc(res.data)
      setModalUpload(false)
      setArquivoNovo(null)
      setObsUpload('')
      flash('success', `Arquivo Rev ${res.data.revisao_label} enviado!`)
    } catch (err) {
      flash('error', err.response?.data?.detail || 'Erro no upload')
    } finally { setUploading(false) }
  }

  function fecharModal() {
    if (uploading) return
    setModalUpload(false)
    setArquivoNovo(null)
    setObsUpload('')
  }

  function dotColor(acao) {
    if (acao === 'aprovado')  return 'green'
    if (acao === 'reprovado') return 'red'
    return ''
  }

  if (loading) return (
    <Layout>
      <div className="page-body" style={{ textAlign: 'center', paddingTop: 80 }}>
        <div className="spinner" />
        <p className="text-muted">Carregando documento...</p>
      </div>
    </Layout>
  )

  if (!doc) return (
    <Layout>
      <div className="page-body">
        <div className="alert alert-error">Documento não encontrado.</div>
      </div>
    </Layout>
  )

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1>{doc.nome}</h1>
          <div className="sub">
            <code style={{ background: 'rgba(59,130,246,0.08)', color: '#1d4ed8', border: '1px solid rgba(59,130,246,0.2)' }}>
              {doc.codigo}
            </code>
            {' '}
            <span className="badge badge-green" style={{ fontSize: 12 }}>Rev {doc.revisao_label}</span>
          </div>
        </div>
        <button className="btn btn-secondary" onClick={() => nav(-1)}>← Voltar</button>
      </div>

      <div className="page-body">
        {msg.texto && (
          <div className={`alert alert-${msg.tipo === 'error' ? 'error' : 'success'}`}
            onClick={() => setMsg({ tipo: '', texto: '' })}>
            {msg.texto}
          </div>
        )}

        {/* ── Info card ── */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
            {/* Campos info — grid evita sobreposição */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, auto)', gap: '0 32px', alignItems: 'start' }}>
              <div>
                <div className="text-sm text-muted" style={{ marginBottom: 4 }}>Responsável</div>
                <div style={{ fontWeight: 600, fontSize: 15 }}>{doc.responsavel?.username}</div>
              </div>
              <div>
                <div className="text-sm text-muted" style={{ marginBottom: 4 }}>Criado em</div>
                <div style={{ fontWeight: 500, fontSize: 14 }}>
                  {new Date(doc.created_at).toLocaleDateString('pt-BR')}
                </div>
              </div>
              <div>
                <div className="text-sm text-muted" style={{ marginBottom: 4 }}>Revisão atual</div>
                <span className="badge badge-green">
                  Rev {doc.revisao_label}
                  {doc.revisao_indice > 0 && ` (${doc.revisao_indice + 1}ª)`}
                </span>
              </div>
            </div>

            {/* Ações */}
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              {doc.atividade_atual ? (
                <span className="badge badge-blue" style={{ fontSize: 13, padding: '7px 16px' }}>
                  <span className="status-dot blue" />
                  Fluxo {doc.atividade_atual.fluxo?.numero} · {doc.atividade_atual.nome}
                </span>
              ) : (
                <span className="badge badge-gray">Sem fluxo</span>
              )}
              <button className="btn btn-orange btn-sm" onClick={() => setModalUpload(true)}>
                ⬆ Nova Revisão
              </button>
            </div>
          </div>
        </div>

        {/* ── Tabs ── */}
        <div className="card">
          <GlassTabs tabs={ABAS} active={aba} onChange={setAba} />

          {/* ── Aba Arquivos ── */}
          {aba === 'arquivos' && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 50 }}>ID</th>
                    <th>Nome do Arquivo</th>
                    <th>Revisão</th>
                    <th>Atividade</th>
                    <th>Observação</th>
                    <th>Responsável</th>
                    <th>Data</th>
                    <th style={{ width: 90 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {!doc.arquivos?.length
                    ? <tr><td colSpan={8}><div className="empty-state" style={{ padding: 28 }}>Nenhum arquivo enviado</div></td></tr>
                    : doc.arquivos.map(a => (
                      <tr key={a.id}>
                        <td><code style={{ fontSize: 12 }}>{a.id}</code></td>
                        <td style={{ fontWeight: 500, maxWidth: 220 }}>
                          <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={a.arquivo_nome}>
                            {a.arquivo_nome}
                          </div>
                        </td>
                        <td><span className="badge badge-green">Rev {a.revisao_label}</span></td>
                        <td className="text-sm">
                          {a.atividade
                            ? <span className="badge badge-blue" style={{ fontSize: 11 }}>{a.atividade.nome}</span>
                            : <span className="text-muted">—</span>}
                        </td>
                        <td className="text-sm" style={{ maxWidth: 180 }}>
                          {a.observacao
                            ? <span style={{ color: '#374151' }} title={a.observacao}>
                                {a.observacao.length > 60 ? a.observacao.slice(0, 60) + '…' : a.observacao}
                              </span>
                            : <span className="text-muted">—</span>}
                        </td>
                        <td className="text-sm text-muted">{a.uploaded_by?.username}</td>
                        <td className="text-sm text-muted" style={{ whiteSpace: 'nowrap' }}>
                          {new Date(a.created_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}
                        </td>
                        <td>
                          <a href={`/uploads/${a.arquivo_path}`} target="_blank" rel="noreferrer"
                            className="btn btn-secondary btn-sm">
                            ↓ Baixar
                          </a>
                        </td>
                      </tr>
                    ))
                  }
                </tbody>
              </table>
            </div>
          )}

          {/* ── Aba Histórico ── */}
          {aba === 'historico' && (
            <div>
              {!doc.historico?.length
                ? (
                  <div className="empty-state" style={{ padding: '40px 0' }}>
                    <span className="empty-icon">📭</span>
                    <p>Nenhum histórico ainda</p>
                  </div>
                )
                : (
                  <div className="timeline">
                    {doc.historico.map(h => (
                      <div key={h.id} className="timeline-item">
                        <div className={`timeline-dot ${dotColor(h.acao)}`} />
                        <div className="timeline-content">
                          <div className="flex justify-between items-center gap-2" style={{ flexWrap: 'wrap' }}>
                            <strong style={{ fontSize: 14 }}>
                              {h.atividade_origem
                                ? <>{h.atividade_origem.nome} <span style={{ color: 'var(--muted)' }}>→</span> </>
                                : ''}
                              {h.atividade_destino?.nome}
                            </strong>
                            <span className={`badge ${
                              h.acao === 'aprovado'       ? 'badge-green' :
                              h.acao === 'reprovado'      ? 'badge-red'   :
                              h.acao === 'upload_inicial' ? 'badge-blue'  : 'badge-gray'
                            }`}>
                              {h.acao?.replace('_', ' ')}
                            </span>
                          </div>
                          {h.observacao && (
                            <p className="text-sm" style={{ marginTop: 6, color: '#374151' }}>
                              💬 {h.observacao}
                            </p>
                          )}
                          <div className="timeline-meta">
                            por <strong>{h.user?.username}</strong> · {new Date(h.created_at).toLocaleString('pt-BR')}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )
              }
            </div>
          )}

          {/* ── Aba Formulário ── */}
          {aba === 'formulario' && (
            <div>
              {!doc.valores_campos?.length
                ? (
                  <div className="empty-state">
                    <span className="empty-icon">📋</span>
                    <strong>Nenhum campo configurado</strong>
                    <p>Configure campos em Admin → Hierarquia → Tipos de Doc.</p>
                  </div>
                )
                : (
                  <>
                    <div className="grid-2">
                      {doc.valores_campos.map(c => (
                        <div key={c.campo_id} className="form-group">
                          <label className="form-label">{c.campo_nome}</label>
                          {editando && isAdmin
                            ? c.campo_tipo === 'select'
                              ? (
                                <select className="form-control" value={valores[c.campo_id] || ''}
                                  onChange={e => setValores(p => ({ ...p, [c.campo_id]: e.target.value }))}>
                                  <option value="">Selecione...</option>
                                  {c.opcoes?.map(o => <option key={o} value={o}>{o}</option>)}
                                </select>
                              ) : (
                                <input className="form-control" type={c.campo_tipo}
                                  value={valores[c.campo_id] || ''}
                                  onChange={e => setValores(p => ({ ...p, [c.campo_id]: e.target.value }))} />
                              )
                            : (
                              <div style={{
                                padding: '10px 13px',
                                background: 'rgba(248,250,252,0.8)',
                                border: '1.5px solid rgba(226,232,240,0.8)',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: 14,
                                color: c.valor ? 'var(--text)' : 'var(--muted)',
                                minHeight: 42, display: 'flex', alignItems: 'center',
                              }}>
                                {c.valor || '—'}
                              </div>
                            )
                          }
                        </div>
                      ))}
                    </div>
                    {isAdmin && (
                      <div className="flex gap-2 mt-4">
                        {editando
                          ? <>
                              <button
                                className={`btn btn-primary${salvandoCampos ? ' btn-loading' : ''}`}
                                disabled={salvandoCampos}
                                onClick={salvarCampos}
                              >
                                {!salvandoCampos && 'Salvar'}
                              </button>
                              <button className="btn btn-secondary" onClick={() => setEditando(false)} disabled={salvandoCampos}>
                                Cancelar
                              </button>
                            </>
                          : <button className="btn btn-secondary" onClick={() => setEditando(true)}>
                              ✏️ Editar Campos
                            </button>
                        }
                      </div>
                    )}
                  </>
                )
              }
            </div>
          )}
        </div>
      </div>

      {/* ── Modal upload nova revisão ── */}
      {modalUpload && (
        <Modal title={`Nova Revisão — Rev ${doc.revisao_label}`} onClose={fecharModal}>
          <p className="text-sm text-muted" style={{ marginBottom: 16 }}>
            Envie um arquivo atualizado para a revisão atual <strong>Rev {doc.revisao_label}</strong>.
          </p>

          <div
            className={`drop-zone${uploadOver ? ' over' : ''}`}
            style={{ marginBottom: 16 }}
            onDragOver={e => { e.preventDefault(); setUploadOver(true) }}
            onDragLeave={() => setUploadOver(false)}
            onDrop={e => { e.preventDefault(); setUploadOver(false); setArquivoNovo(e.dataTransfer.files[0]) }}
            onClick={() => fileRef.current.click()}
          >
            <span className="icon">{arquivoNovo ? '✅' : '📄'}</span>
            {arquivoNovo
              ? <p><strong>{arquivoNovo.name}</strong> — {(arquivoNovo.size / 1024).toFixed(0)} KB</p>
              : <p>Arraste ou <strong>clique para selecionar</strong></p>
            }
          </div>
          <input ref={fileRef} type="file" style={{ display: 'none' }}
            onChange={e => setArquivoNovo(e.target.files[0])} />

          <div className="form-group" style={{ marginBottom: 20 }}>
            <label className="form-label">Observação <span className="text-muted" style={{ fontWeight: 400 }}>(opcional)</span></label>
            <textarea
              className="form-control"
              rows={3}
              placeholder="Descreva o que foi alterado nesta revisão..."
              value={obsUpload}
              onChange={e => setObsUpload(e.target.value)}
              style={{ resize: 'vertical' }}
            />
          </div>

          <div className="flex gap-2">
            <button
              className={`btn btn-primary${uploading ? ' btn-loading' : ''}`}
              onClick={enviarNovoArquivo}
              disabled={!arquivoNovo || uploading}
            >
              {!uploading && '⬆ Enviar'}
            </button>
            <button className="btn btn-secondary" onClick={fecharModal} disabled={uploading}>
              Cancelar
            </button>
          </div>
        </Modal>
      )}
    </Layout>
  )
}
