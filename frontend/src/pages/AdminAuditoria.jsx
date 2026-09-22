import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import Modal from '../components/Modal'
import api, { mensagemErro } from '../api'

const POR_PAGINA = 25

const FILTROS_VAZIOS = {
  action: '', user_id: '', entity_type: '', document_id: '',
  project_id: '', ip: '', request_id: '', de: '', ate: '',
}

function quando(iso) {
  return iso ? new Date(iso).toLocaleString('pt-BR') : '—'
}

export default function AdminAuditoria() {
  const [acoes, setAcoes] = useState([])
  const [usuarios, setUsuarios] = useState([])
  const [filtros, setFiltros] = useState(FILTROS_VAZIOS)
  const [pagina, setPagina] = useState({ total: 0, skip: 0, limit: POR_PAGINA, itens: [] })
  const [carregando, setCarregando] = useState(true)
  const [detalhe, setDetalhe] = useState(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    api.get('/auditoria/catalogo').then(r => setAcoes(r.data.acoes)).catch(() => {})
    api.get('/usuarios').then(r => setUsuarios(r.data)).catch(() => {})
  }, [])

  useEffect(() => { carregar(0) }, [filtros])

  async function carregar(skip) {
    setCarregando(true)
    setErro('')
    // Campo vazio não vira filtro — senão `action=` filtraria por string vazia.
    const params = Object.fromEntries(
      Object.entries(filtros).filter(([, v]) => v !== '' && v !== null)
    )
    try {
      const r = await api.get('/auditoria', {
        params: { ...params, skip, limit: POR_PAGINA },
      })
      setPagina(r.data)
    } catch (err) {
      setErro(mensagemErro(err, 'Erro ao consultar a auditoria'))
    } finally {
      setCarregando(false)
    }
  }

  function mudar(campo, valor) {
    setFiltros(f => ({ ...f, [campo]: valor }))
  }

  const temFiltro = Object.values(filtros).some(v => v !== '')
  const inicio = pagina.skip + 1
  const fim = Math.min(pagina.skip + pagina.limit, pagina.total)

  return (
    <Layout>
      <h1 className="page-title">Auditoria</h1>
      <p className="muted">
        Registro somente-leitura de tudo que aconteceu no sistema. Nada aqui
        pode ser alterado ou removido.
      </p>

      {erro && <div className="alert alert-error">{erro}</div>}

      <div className="card form-inline">
        <select value={filtros.action} onChange={e => mudar('action', e.target.value)}>
          <option value="">Todas as ações</option>
          {acoes.map(a => <option key={a} value={a}>{a}</option>)}
        </select>

        <select value={filtros.user_id} onChange={e => mudar('user_id', e.target.value)}>
          <option value="">Todos os usuários</option>
          {usuarios.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>

        <input type="number" placeholder="id do documento" value={filtros.document_id}
               onChange={e => mudar('document_id', e.target.value)} />
        <input type="number" placeholder="id do projeto" value={filtros.project_id}
               onChange={e => mudar('project_id', e.target.value)} />
        <input placeholder="IP" value={filtros.ip}
               onChange={e => mudar('ip', e.target.value)} />

        <label className="form-label">De
          <input type="datetime-local" value={filtros.de}
                 onChange={e => mudar('de', e.target.value)} />
        </label>
        <label className="form-label">Até
          <input type="datetime-local" value={filtros.ate}
                 onChange={e => mudar('ate', e.target.value)} />
        </label>

        {temFiltro && (
          <button className="btn btn-secondary" onClick={() => setFiltros(FILTROS_VAZIOS)}>
            Limpar filtros
          </button>
        )}
      </div>

      {carregando ? <p>Carregando…</p> : (
        <>
          <p className="muted">
            {pagina.total === 0
              ? 'Nenhum evento encontrado.'
              : `Mostrando ${inicio}–${fim} de ${pagina.total}`}
          </p>

          <table className="table">
            <thead>
              <tr>
                <th>Quando</th><th>Quem</th><th>Ação</th>
                <th>Entidade</th><th>IP</th><th></th>
              </tr>
            </thead>
            <tbody>
              {pagina.itens.map(item => (
                <tr key={item.id}>
                  <td>{quando(item.timestamp)}</td>
                  <td>{item.username || <em className="muted">—</em>}</td>
                  <td><span className="badge badge-gray">{item.action}</span></td>
                  <td>
                    {item.entity_type
                      ? `${item.entity_type}${item.entity_id ? ` #${item.entity_id}` : ''}`
                      : '—'}
                  </td>
                  <td>{item.ip || '—'}</td>
                  <td>
                    <button className="btn btn-link" onClick={() => setDetalhe(item)}>
                      Detalhes
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
            <button className="btn btn-secondary" disabled={pagina.skip === 0}
                    onClick={() => carregar(Math.max(0, pagina.skip - POR_PAGINA))}>
              Anterior
            </button>
            <button className="btn btn-secondary"
                    disabled={pagina.skip + pagina.limit >= pagina.total}
                    onClick={() => carregar(pagina.skip + POR_PAGINA)}>
              Próxima
            </button>
          </div>
        </>
      )}

      {detalhe && (
        <Modal title={`Evento #${detalhe.id} — ${detalhe.action}`}
               onClose={() => setDetalhe(null)} maxWidth={760}>
          <dl className="detalhe-grid">
            <dt>Quando</dt><dd>{quando(detalhe.timestamp)}</dd>
            <dt>Usuário</dt>
            <dd>{detalhe.username || '—'}{detalhe.user_id ? ` (#${detalhe.user_id})` : ''}</dd>
            <dt>Sessão</dt><dd>{detalhe.session_id ?? '—'}</dd>
            <dt>Entidade</dt>
            <dd>{detalhe.entity_type || '—'}{detalhe.entity_id ? ` #${detalhe.entity_id}` : ''}</dd>
            <dt>Projeto</dt><dd>{detalhe.project_id ?? '—'}</dd>
            <dt>Documento</dt><dd>{detalhe.document_id ?? '—'}</dd>
            <dt>IP</dt><dd>{detalhe.ip || '—'}</dd>
            <dt>Request ID</dt><dd><code>{detalhe.request_id || '—'}</code></dd>
            <dt>User-Agent</dt><dd className="quebra">{detalhe.user_agent || '—'}</dd>
          </dl>

          {detalhe.before && (
            <>
              <h4>Antes</h4>
              <pre className="json-box">{JSON.stringify(detalhe.before, null, 2)}</pre>
            </>
          )}
          {detalhe.after && (
            <>
              <h4>Depois</h4>
              <pre className="json-box">{JSON.stringify(detalhe.after, null, 2)}</pre>
            </>
          )}
          {detalhe.detalhes && (
            <>
              <h4>Contexto</h4>
              <pre className="json-box">{JSON.stringify(detalhe.detalhes, null, 2)}</pre>
            </>
          )}
        </Modal>
      )}
    </Layout>
  )
}
