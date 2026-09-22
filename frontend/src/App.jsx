import { Routes, Route, Navigate } from 'react-router-dom'
import PrivateRoute from './components/PrivateRoute'
import Login from './pages/Login'
import Documentos from './pages/Documentos'
import Upload from './pages/Upload'
import DocumentoDetalhe from './pages/DocumentoDetalhe'
import AdminHierarquia from './pages/AdminHierarquia'
import AdminWorkflow from './pages/AdminWorkflow'
import AdminUsuarios from './pages/AdminUsuarios'
import AdminPermissoes from './pages/AdminPermissoes'
import AdminAuditoria from './pages/AdminAuditoria'
import MinhasSessoes from './pages/MinhasSessoes'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/documentos" replace />} />
      <Route path="/documentos" element={<PrivateRoute><Documentos /></PrivateRoute>} />
      <Route path="/documentos/upload" element={<PrivateRoute><Upload /></PrivateRoute>} />
      <Route path="/documentos/:id" element={<PrivateRoute><DocumentoDetalhe /></PrivateRoute>} />
      <Route path="/admin/hierarquia" element={<PrivateRoute adminOnly><AdminHierarquia /></PrivateRoute>} />
      <Route path="/admin/workflow" element={<PrivateRoute adminOnly><AdminWorkflow /></PrivateRoute>} />
      <Route path="/admin/usuarios" element={<PrivateRoute adminOnly><AdminUsuarios /></PrivateRoute>} />
      <Route path="/admin/permissoes" element={<PrivateRoute adminOnly><AdminPermissoes /></PrivateRoute>} />
      <Route path="/admin/auditoria" element={<PrivateRoute adminOnly><AdminAuditoria /></PrivateRoute>} />
      <Route path="/sessoes" element={<PrivateRoute><MinhasSessoes /></PrivateRoute>} />
    </Routes>
  )
}
