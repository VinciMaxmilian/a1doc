import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import api from '../api'

const MAX_SIZE = 100 * 1024 * 1024 // 100 MB

function extIcon(name) {
  const ext = name.split('.').pop().toLowerCase()
  if (['pdf'].includes(ext)) return '📕'
  if (['doc', 'docx'].includes(ext)) return '📝'
  if (['xls', 'xlsx'].includes(ext)) return '📊'
  if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext)) return '🖼️'
  if (['zip', 'rar', '7z'].includes(ext)) return '🗜️'
  return '📄'
}

function fmtSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

function stripExt(name) {
  return name.replace(/\.[^/.]+$/, '')
}

export default function Upload() {
  const nav = useNavigate()
  const fileRef = useRef()
  const [form, setForm] = useState({
    nome: '', ambiente_id: '', area_id: '', projeto_id: '', tipo_documento_id: '', observacao: '',
  })
  const [nomeManual, setNomeManual] = useState(false)
  const [arquivos, setArquivos] = useState([])
  const [over, setOver] = useState(false)
  const [ambientes, setAmbientes] = useState([])
  const [areas, setAreas] = useState([])
  const [projetos, setProjetos] = useState([])
  const [tipos, setTipos] = useState([])
  const [fase, setFase] = useState('form') // form | uploading | queued | erro
  const [erro, setErro] = useState('')
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)

  useEffect(() => {
    api.get('/hierarquia/ambientes').then(r => setAmbientes(r.data))
    api.get('/hierarquia/tipos-documento').then(r => setTipos(r.data))
  }, [])

  // Poll job status while queued
  useEffect(() => {
    if (fase !== 'queued' || !jobId) return
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/documentos/jobs/${jobId}`)
        setJobStatus(res.data)
        if (res.data.status === 'concluido') {
          clearInterval(interval)
          nav(`/documentos/${res.data.documento_id}`)
        } else if (res.data.status === 'erro') {
          clearInterval(interval)
          setErro(res.data.erro_msg || 'Erro no processamento do upload')
          setFase('erro')
        }
      } catch (_) {}
    }, 2000)
    return () => clearInterval(interval)
  }, [fase, jobId, nav])

  async function onAmbiente(id) {
    setForm(p => ({ ...p, ambiente_id: id, area_id: '', projeto_id: '' }))
    setAreas([]); setProjetos([])
    if (id) {
      const r = await api.get('/hierarquia/areas', { params: { ambiente_id: id } })
      setAreas(r.data)
    }
  }

  async function onArea(id) {
    setForm(p => ({ ...p, area_id: id, projeto_id: '' }))
    setProjetos([])
    if (id) {
      const r = await api.get('/hierarquia/projetos', { params: { area_id: id } })
      setProjetos(r.data)
    }
  }

  function addFiles(fileList) {
    const novos = []
    const erros = []
    Array.from(fileList).forEach(f => {
      if (f.size > MAX_SIZE) {
        erros.push(`"${f.name}" excede 100MB e foi ignorado`)
        return
      }
      // Dedup by name+size
      if (!arquivos.find(a => a.name === f.name && a.size === f.size)) {
        novos.push(f)
      }
    })
    if (erros.length) setErro(erros.join(' | '))
    setArquivos(prev => {
      const merged = [...prev, ...novos]
      // Auto-fill nome from first file if nome is empty or not manually edited
      if (!nomeManual && merged.length > 0 && merged.length === novos.length + prev.length) {
        if (prev.length === 0 && novos.length > 0) {
          setForm(p => ({ ...p, nome: stripExt(novos[0].name) }))
        }
      }
      return merged
    })
  }

  function removeArquivo(idx) {
    setArquivos(prev => {
      const next = prev.filter((_, i) => i !== idx)
      if (!nomeManual && next.length === 0) {
        setForm(p => ({ ...p, nome: '' }))
      }
      return next
    })
  }

  function onDrop(e) {
    e.preventDefault(); setOver(false)
    addFiles(e.dataTransfer.files)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!arquivos.length) { setErro('Selecione pelo menos um arquivo'); return }
    setErro('')
    setFase('uploading')
    try {
      const fd = new FormData()
      fd.append('nome', form.nome)
      fd.append('ambiente_id', form.ambiente_id)
      fd.append('area_id', form.area_id)
      fd.append('projeto_id', form.projeto_id)
      fd.append('tipo_documento_id', form.tipo_documento_id)
      if (form.observacao.trim()) fd.append('observacao', form.observacao.trim())
      arquivos.forEach(f => fd.append('arquivos', f))
      const res = await api.post('/documentos/upload', fd)
      setJobId(res.data.job_id)
      setJobStatus({ status: 'pendente' })
      setFase('queued')
    } catch (err) {
      setErro(err.response?.data?.detail || 'Erro ao enviar arquivos')
      setFase('form')
    }
  }

  const statusLabel = {
    pendente: 'Na fila',
    processando: 'Processando',
    concluido: 'Concluído',
    erro: 'Erro',
  }

  return (
    <Layout>
      <div className="page-header"><h1>Novo Documento</h1></div>
      <div className="page-body">
        <div className="card" style={{ maxWidth: 720 }}>

          {/* ── Queued / Processing ── */}
          {(fase === 'queued' || fase === 'uploading') && (
            <div className="upload-queue-panel">
              <div className="spinner" />
              <h3>
                {fase === 'uploading' ? 'Enviando arquivos...' : 'Processando em segundo plano...'}
              </h3>
              <p>
                {fase === 'uploading'
                  ? 'Aguarde enquanto os arquivos são transferidos.'
                  : 'O upload está na fila Celery. Você será redirecionado quando concluir.'}
              </p>
              {jobStatus && (
                <span className="status-badge">
                  {statusLabel[jobStatus.status] || jobStatus.status}
                </span>
              )}
            </div>
          )}

          {/* ── Error state ── */}
          {fase === 'erro' && (
            <div>
              <div className="alert alert-error" style={{ marginBottom: 16 }}>{erro}</div>
              <button className="btn btn-secondary" onClick={() => { setFase('form'); setErro('') }}>
                Tentar novamente
              </button>
            </div>
          )}

          {/* ── Form ── */}
          {fase === 'form' && (
            <form onSubmit={handleSubmit}>
              {erro && <div className="alert alert-error" style={{ marginBottom: 16 }}>{erro}</div>}

              <div className="form-group">
                <label className="form-label">Nome do Documento *</label>
                <input
                  className="form-control"
                  value={form.nome}
                  required
                  placeholder="Preenchido automaticamente pelo nome do arquivo"
                  onChange={e => { setNomeManual(true); setForm(p => ({ ...p, nome: e.target.value })) }}
                />
              </div>

              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Ambiente *</label>
                  <select className="form-control" value={form.ambiente_id} required
                    onChange={e => onAmbiente(e.target.value)}>
                    <option value="">Selecione...</option>
                    {ambientes.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Área *</label>
                  <select className="form-control" value={form.area_id} required
                    onChange={e => onArea(e.target.value)} disabled={!areas.length}>
                    <option value="">Selecione...</option>
                    {areas.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Projeto *</label>
                  <select className="form-control" value={form.projeto_id} required
                    onChange={e => setForm(p => ({ ...p, projeto_id: e.target.value }))}
                    disabled={!projetos.length}>
                    <option value="">Selecione...</option>
                    {projetos.map(p => <option key={p.id} value={p.id}>{p.nome}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Tipo de Documento *</label>
                  <select className="form-control" value={form.tipo_documento_id} required
                    onChange={e => setForm(p => ({ ...p, tipo_documento_id: e.target.value }))}>
                    <option value="">Selecione...</option>
                    {tipos.map(t => <option key={t.id} value={t.id}>{t.nome}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Arquivos * <span style={{ color: 'var(--muted)', fontWeight: 400 }}>— limite 100 MB por arquivo</span>
                </label>
                <div
                  className={`drop-zone${over ? ' over' : ''}`}
                  onDragOver={e => { e.preventDefault(); setOver(true) }}
                  onDragLeave={() => setOver(false)}
                  onDrop={onDrop}
                  onClick={() => fileRef.current.click()}
                >
                  <div className="icon">📂</div>
                  <p>
                    Arraste arquivos aqui ou <strong>clique para selecionar</strong>
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                    Múltiplos arquivos permitidos
                  </p>
                </div>
                <input
                  ref={fileRef}
                  type="file"
                  multiple
                  style={{ display: 'none' }}
                  onChange={e => { addFiles(e.target.files); e.target.value = '' }}
                />

                {arquivos.length > 0 && (
                  <div className="file-list">
                    {arquivos.map((f, i) => (
                      <div key={i} className="file-item">
                        <span className="file-item-icon">{extIcon(f.name)}</span>
                        <div className="file-item-info">
                          <div className="file-item-name" title={f.name}>{f.name}</div>
                          <div className="file-item-size">{fmtSize(f.size)}</div>
                        </div>
                        <button
                          type="button"
                          className="file-item-remove"
                          title="Remover"
                          onClick={() => removeArquivo(i)}
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">
                  Observação <span style={{ color: 'var(--muted)', fontWeight: 400 }}>(opcional)</span>
                </label>
                <textarea
                  className="form-control"
                  rows={3}
                  placeholder="Descreva o conteúdo ou contexto do upload..."
                  value={form.observacao}
                  onChange={e => setForm(p => ({ ...p, observacao: e.target.value }))}
                  style={{ resize: 'vertical' }}
                />
              </div>

              <div className="flex gap-2" style={{ marginTop: 8 }}>
                <button type="submit" className="btn btn-primary" disabled={!arquivos.length}>
                  Enviar para Fila
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => nav(-1)}>
                  Cancelar
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </Layout>
  )
}
