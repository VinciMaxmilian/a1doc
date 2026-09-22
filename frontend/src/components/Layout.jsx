import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">A1<span>Doc</span></div>
        <nav className="sidebar-nav">
          <span className="nav-section">Documentos</span>
          <NavLink
            to="/documentos"
            end
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span>📄</span> Consultar
          </NavLink>
          <NavLink
            to="/documentos/upload"
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span>⬆️</span> Novo Upload
          </NavLink>
          <NavLink
            to="/sessoes"
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span>🖥️</span> Minhas sessões
          </NavLink>

          {isAdmin && (
            <>
              <span className="nav-section">Administração</span>
              <NavLink
                to="/admin/hierarquia"
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <span>🏗️</span> Hierarquia
              </NavLink>
              <NavLink
                to="/admin/workflow"
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <span>⚙️</span> Workflow
              </NavLink>
              <NavLink
                to="/admin/usuarios"
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <span>👤</span> Usuários
              </NavLink>
              <NavLink
                to="/admin/permissoes"
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <span>🔐</span> Permissões
              </NavLink>
              <NavLink
                to="/admin/auditoria"
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <span>📋</span> Auditoria
              </NavLink>
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          <strong>{user?.username}</strong>
          <span>{user?.role}</span>
          <button
            onClick={handleLogout}
            className="btn btn-secondary btn-sm"
            style={{ marginTop: 12, width: '100%', justifyContent: 'center', fontSize: 13 }}
          >
            Sair
          </button>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  )
}
