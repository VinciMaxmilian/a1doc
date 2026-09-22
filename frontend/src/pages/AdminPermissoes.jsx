import { useState, useEffect, Fragment } from 'react'
import Layout from '../components/Layout'
import ConfirmModal from '../components/ConfirmModal'
import GlassTabs from '../components/GlassTabs'
import api, { mensagemErro } from '../api'

const ABAS = [
  { key: 'grupos', label: 'Grupos', icon: '👥' },
  { key: 'perfis', label: 'Perfis', icon: '🎭' },
  { key: 'acl', label: 'Permissões por recurso', icon: '🔐' },
]

export default function AdminPermissoes() {
  const [aba, setAba] = useState('grupos')
  const [catalogo, setCatalogo] = useState({ permissoes: [], subject_types: [], resource_types: [] })
  const [msg, setMsg] = useState({ tipo: '', texto: '' })

  // O vocabulário vem do backend: a UI não duplica a lista de permissões.
  useEffect(() => {
    api.get('/permissoes/catalogo').then(r => setCatalogo(r.data)).catch(() => {})
  }, [])

  function flash(tipo, texto) {
    setMsg({ tipo, texto })
    setTimeout(() => setMsg({ tipo: '', texto: '' }), 4000)
  }

  return (
    <Layout>
      <h1 className="page-title">Permissões</h1>
      {msg.texto && <div className={`alert alert-${msg.tipo}`}>{msg.texto}</div>}

      <GlassTabs tabs={ABAS} active={aba} onChange={setAba} />

      {aba === 'grupos' && <Grupos flash={flash} />}
      {aba === 'perfis' && <Perfis catalogo={catalogo} flash={flash} />}
      {aba === 'acl' && <AclPorRecurso catalogo={catalogo} flash={flash} />}
    </Layout>
  )
}

// ────────────────────────── grupos ──────────────────────────

function Grupos({ flash }) {
  const [grupos, setGrupos] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [nome, setNome] = useState('')
  const [descricao, setDescricao] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [confirmDel, setConfirmDel] = useState(null)
  const [membros, setMembros] = useState({})
  const [usuarios, setUsuarios] = useState([])

  useEffect(() => {
    carregar()
    api.get('/usuarios').then(r => setUsuarios(r.data)).catch(() => {})
  }, [])

  async function carregar() {
    setCarregando(true)
    try { setGrupos((await api.get('/permissoes/grupos')).data) }
    finally { setCarregando(false) }
  }

  async function criar(e) {
    e.preventDefault()
    setSalvando(true)
    try {
      await api.post('/permissoes/grupos', { nome, descricao: descricao || null })
      setNome(''); setDescricao('')
      await carregar()
      flash('success', `Grupo "${nome}" criado.`)
    } catch (err) {
      flash('error', mensagemErro(err, 'Erro ao criar grupo'))
    } finally { setSalvando(false) }
  }

  async function verMembros(gid) {
    if (membros[gid]) { setMembros(m => ({ ...m, [gid]: null })); return }
    const r = await api.get(`/permissoes/grupos/${gid}/membros`)
    setMembros(m => ({ ...m, [gid]: r.data }))
  }

  async function adicionar(gid, uid) {
    if (!uid) return
    await api.post(`/permissoes/grupos/${gid}/membros/${uid}`)
    const r = await api.get(`/permissoes/grupos/${gid}/membros`)
    setMembros(m => ({ ...m, [gid]: r.data }))
    await carregar()
  }

  async function remover(gid, uid) {
    await api.delete(`/permissoes/grupos/${gid}/membros/${uid}`)
    const r = await api.get(`/permissoes/grupos/${gid}/membros`)
    setMembros(m => ({ ...m, [gid]: r.data }))
    await carregar()
  }

  return (
    <>
      <form className="card form-inline" onSubmit={criar}>
        <input value={nome} onChange={e => setNome(e.target.value)}
               placeholder="Nome do grupo (ex.: Engenharia Mecânica)" required />
        <input value={descricao} onChange={e => setDescricao(e.target.value)}
               placeholder="Descrição (opcional)" />
        <button className="btn btn-primary" disabled={salvando || !nome.trim()}>
          Criar grupo
        </button>
      </form>

      {carregando ? <p>Carregando…</p> : (
        <table className="table">
          <thead>
            <tr><th>Grupo</th><th>Descrição</th><th>Membros</th><th></th></tr>
          </thead>
          <tbody>
            {grupos.map(g => (
              <Fragment key={g.id}>
                <tr>
                  <td><strong>{g.nome}</strong></td>
                  <td>{g.descricao || '—'}</td>
                  <td>
                    <button className="btn btn-link" onClick={() => verMembros(g.id)}>
                      {g.total_membros} {g.total_membros === 1 ? 'membro' : 'membros'}
                    </button>
                  </td>
                  <td>
                    <button className="btn btn-danger btn-sm"
                            onClick={() => setConfirmDel(g)}>Excluir</button>
                  </td>
                </tr>
                {membros[g.id] && (
                  <tr>
                    <td colSpan={4} className="subrow">
                      <div className="chips">
                        {membros[g.id].length === 0 && <em>Sem membros.</em>}
                        {membros[g.id].map(m => (
                          <span className="chip" key={m.id}>
                            {m.username}
                            <button onClick={() => remover(g.id, m.id)} aria-label="Remover">✕</button>
                          </span>
                        ))}
                      </div>
                      <select defaultValue="" onChange={e => { adicionar(g.id, e.target.value); e.target.value = '' }}>
                        <option value="">+ Adicionar usuário…</option>
                        {usuarios
                          .filter(u => !membros[g.id].some(m => m.id === u.id))
                          .map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
                      </select>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}

      {confirmDel && (
        <ConfirmModal
          title={`Excluir o grupo "${confirmDel.nome}"?`}
          message="As permissões concedidas a este grupo também serão removidas."
          onCancel={() => setConfirmDel(null)}
          onConfirm={async () => {
            try {
              await api.delete(`/permissoes/grupos/${confirmDel.id}`)
              flash('success', 'Grupo excluído.')
              await carregar()
            } catch (err) {
              flash('error', mensagemErro(err, 'Erro ao excluir'))
            } finally { setConfirmDel(null) }
          }}
        />
      )}
    </>
  )
}

// ────────────────────────── perfis ──────────────────────────

function Perfis({ catalogo, flash }) {
  const [perfis, setPerfis] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [nome, setNome] = useState('')
  const [selecionadas, setSelecionadas] = useState([])
  const [editando, setEditando] = useState(null)
  const [confirmDel, setConfirmDel] = useState(null)

  useEffect(() => { carregar() }, [])

  async function carregar() {
    setCarregando(true)
    try { setPerfis((await api.get('/permissoes/perfis')).data) }
    finally { setCarregando(false) }
  }

  function alternar(lista, perm, set) {
    set(lista.includes(perm) ? lista.filter(p => p !== perm) : [...lista, perm])
  }

  async function criar(e) {
    e.preventDefault()
    try {
      await api.post('/permissoes/perfis', { nome, permissoes: selecionadas })
      setNome(''); setSelecionadas([])
      await carregar()
      flash('success', `Perfil "${nome}" criado.`)
    } catch (err) {
      flash('error', mensagemErro(err, 'Erro ao criar perfil'))
    }
  }

  async function salvar(p) {
    try {
      await api.put(`/permissoes/perfis/${p.id}`, { permissoes: editando.permissoes })
      setEditando(null)
      await carregar()
      flash('success', 'Perfil atualizado.')
    } catch (err) {
      flash('error', mensagemErro(err, 'Erro ao salvar'))
    }
  }

  return (
    <>
      <form className="card" onSubmit={criar}>
        <input value={nome} onChange={e => setNome(e.target.value)}
               placeholder="Nome do perfil (ex.: auditor)" required />
        <div className="perm-grid">
          {catalogo.permissoes.map(perm => (
            <label key={perm} className="perm-check">
              <input type="checkbox" checked={selecionadas.includes(perm)}
                     onChange={() => alternar(selecionadas, perm, setSelecionadas)} />
              {perm}
            </label>
          ))}
        </div>
        <button className="btn btn-primary" disabled={!nome.trim()}>Criar perfil</button>
      </form>

      {carregando ? <p>Carregando…</p> : perfis.map(p => (
        <div className="card" key={p.id}>
          <div className="card-head">
            <strong>{p.nome}</strong>
            {p.sistema && <span className="badge badge-blue">sistema</span>}
            <span className="muted">{p.descricao}</span>
            <div className="spacer" />
            {editando?.id === p.id ? (
              <>
                <button className="btn btn-primary btn-sm" onClick={() => salvar(p)}>Salvar</button>
                <button className="btn btn-secondary btn-sm" onClick={() => setEditando(null)}>Cancelar</button>
              </>
            ) : (
              <>
                <button className="btn btn-secondary btn-sm"
                        onClick={() => setEditando({ id: p.id, permissoes: [...p.permissoes] })}>
                  Editar
                </button>
                {!p.sistema && (
                  <button className="btn btn-danger btn-sm" onClick={() => setConfirmDel(p)}>
                    Excluir
                  </button>
                )}
              </>
            )}
          </div>

          {editando?.id === p.id ? (
            <div className="perm-grid">
              {catalogo.permissoes.map(perm => (
                <label key={perm} className="perm-check">
                  <input type="checkbox" checked={editando.permissoes.includes(perm)}
                         onChange={() => setEditando(e => ({
                           ...e,
                           permissoes: e.permissoes.includes(perm)
                             ? e.permissoes.filter(x => x !== perm)
                             : [...e.permissoes, perm],
                         }))} />
                  {perm}
                </label>
              ))}
            </div>
          ) : (
            <div className="chips">
              {p.permissoes.length === 0 && <em>Nenhuma permissão.</em>}
              {p.permissoes.map(perm => <span className="chip" key={perm}>{perm}</span>)}
            </div>
          )}
        </div>
      ))}

      {confirmDel && (
        <ConfirmModal
          title={`Excluir o perfil "${confirmDel.nome}"?`}
          message="Só é possível excluir perfis sem usuários atribuídos."
          onCancel={() => setConfirmDel(null)}
          onConfirm={async () => {
            try {
              await api.delete(`/permissoes/perfis/${confirmDel.id}`)
              flash('success', 'Perfil excluído.')
              await carregar()
            } catch (err) {
              flash('error', mensagemErro(err, 'Erro ao excluir'))
            } finally { setConfirmDel(null) }
          }}
        />
      )}
    </>
  )
}

// ────────────────────────── ACL por recurso ──────────────────────────

function AclPorRecurso({ catalogo, flash }) {
  const [resourceType, setResourceType] = useState('projeto')
  const [resourceId, setResourceId] = useState('')
  const [entradas, setEntradas] = useState(null)
  const [arvore, setArvore] = useState([])
  const [usuarios, setUsuarios] = useState([])
  const [grupos, setGrupos] = useState([])
  const [perfis, setPerfis] = useState([])
  const [nova, setNova] = useState({ subject_type: 'usuario', subject_id: '', permission: 'read', allow: true })

  useEffect(() => {
    api.get('/hierarquia').then(r => setArvore(r.data)).catch(() => {})
    api.get('/usuarios').then(r => setUsuarios(r.data)).catch(() => {})
    api.get('/permissoes/grupos').then(r => setGrupos(r.data)).catch(() => {})
    api.get('/permissoes/perfis').then(r => setPerfis(r.data)).catch(() => {})
  }, [])

  const global = resourceType === 'global'

  async function carregar() {
    if (!global && !resourceId) return
    try {
      const r = await api.get('/permissoes/acl', {
        params: { resource_type: resourceType, ...(global ? {} : { resource_id: resourceId }) },
      })
      setEntradas(r.data)
    } catch (err) {
      setEntradas([])
      flash('error', mensagemErro(err, 'Não foi possível listar as permissões'))
    }
  }

  useEffect(() => { carregar() }, [resourceType, resourceId])

  const sujeitos = { usuario: usuarios, grupo: grupos, perfil: perfis }[nova.subject_type] || []

  function rotuloSujeito(tipo, id) {
    const lista = { usuario: usuarios, grupo: grupos, perfil: perfis }[tipo] || []
    const achado = lista.find(x => x.id === id)
    return achado ? (achado.username || achado.nome) : `#${id}`
  }

  async function conceder(allow) {
    try {
      await api.post('/permissoes/acl', {
        subject_type: nova.subject_type,
        subject_id: Number(nova.subject_id),
        resource_type: resourceType,
        resource_id: global ? null : Number(resourceId),
        permission: nova.permission,
        allow,
      })
      await carregar()
      flash('success', allow ? 'Permissão concedida.' : 'Permissão negada.')
    } catch (err) {
      flash('error', mensagemErro(err, 'Erro ao gravar a permissão'))
    }
  }

  // Opções de recurso a partir da árvore Ambiente → Área → Projeto.
  const opcoes = []
  if (resourceType === 'ambiente') arvore.forEach(a => opcoes.push({ id: a.id, nome: a.nome }))
  if (resourceType === 'area') arvore.forEach(a => a.areas.forEach(ar => opcoes.push({ id: ar.id, nome: `${a.nome} / ${ar.nome}` })))
  if (resourceType === 'projeto') arvore.forEach(a => a.areas.forEach(ar => ar.projetos.forEach(p => opcoes.push({ id: p.id, nome: `${a.nome} / ${ar.nome} / ${p.nome}` }))))

  return (
    <>
      <div className="card form-inline">
        <select value={resourceType} onChange={e => { setResourceType(e.target.value); setResourceId('') }}>
          {catalogo.resource_types.filter(t => t !== 'documento').map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        {!global && (
          resourceType === 'documento' ? (
            <input type="number" value={resourceId} placeholder="id do documento"
                   onChange={e => setResourceId(e.target.value)} />
          ) : (
            <select value={resourceId} onChange={e => setResourceId(e.target.value)}>
              <option value="">Selecione…</option>
              {opcoes.map(o => <option key={o.id} value={o.id}>{o.nome}</option>)}
            </select>
          )
        )}
      </div>

      {(global || resourceId) && (
        <div className="card form-inline">
          <select value={nova.subject_type}
                  onChange={e => setNova(n => ({ ...n, subject_type: e.target.value, subject_id: '' }))}>
            {catalogo.subject_types.map(t => <option key={t} value={t}>{t}</option>)}
          </select>

          <select value={nova.subject_id}
                  onChange={e => setNova(n => ({ ...n, subject_id: e.target.value }))}>
            <option value="">Selecione…</option>
            {sujeitos.map(s => (
              <option key={s.id} value={s.id}>{s.username || s.nome}</option>
            ))}
          </select>

          <select value={nova.permission}
                  onChange={e => setNova(n => ({ ...n, permission: e.target.value }))}>
            {catalogo.permissoes.map(p => <option key={p} value={p}>{p}</option>)}
          </select>

          <button className="btn btn-primary" disabled={!nova.subject_id}
                  onClick={() => conceder(true)}>Permitir</button>
          <button className="btn btn-danger" disabled={!nova.subject_id}
                  onClick={() => conceder(false)}>Negar</button>
        </div>
      )}

      {entradas && (
        <table className="table">
          <thead>
            <tr><th>Sujeito</th><th>Permissão</th><th>Efeito</th><th></th></tr>
          </thead>
          <tbody>
            {entradas.length === 0 && (
              <tr><td colSpan={4}><em>Nenhuma regra própria neste recurso — vale o que for herdado.</em></td></tr>
            )}
            {entradas.map(e => (
              <tr key={e.id}>
                <td>{e.subject_type}: <strong>{rotuloSujeito(e.subject_type, e.subject_id)}</strong></td>
                <td>{e.permission}</td>
                <td>
                  <span className={`badge ${e.allow ? 'badge-green' : 'badge-orange'}`}>
                    {e.allow ? 'permitido' : 'negado'}
                  </span>
                </td>
                <td>
                  <button className="btn btn-danger btn-sm" onClick={async () => {
                    await api.delete(`/permissoes/acl/${e.id}`)
                    await carregar()
                  }}>Remover</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}
