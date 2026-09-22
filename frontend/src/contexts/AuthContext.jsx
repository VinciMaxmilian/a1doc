import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { USER_KEY, setUnauthorizedHandler } from '../api'

const Ctx = createContext(null)

export function AuthProvider({ children }) {
  const navigate = useNavigate()
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY)) } catch { return null }
  })

  // A sessão vive nos cookies HttpOnly (FASE 2); aqui guardamos só o perfil
  // exibido na interface, para a tela não piscar enquanto /auth/me responde.
  function login(userData) {
    localStorage.setItem(USER_KEY, JSON.stringify(userData))
    setUser(userData)
  }

  const logout = useCallback(async () => {
    try {
      // Precisa ir ao servidor: é o que revoga a sessão de verdade. Limpar só
      // o estado local deixaria o refresh token vivo no banco.
      await api.post('/auth/logout')
    } catch {
      // Sessão já inválida no servidor — seguir com a limpeza local.
    }
    localStorage.removeItem(USER_KEY)
    setUser(null)
  }, [])

  // Token expirado/revogado: limpa a sessão e volta ao login pelo router,
  // sem recarregar a página (window.location descartava o estado do SPA).
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null)
      navigate('/login', { replace: true })
    })
    return () => setUnauthorizedHandler(null)
  }, [navigate])

  const isAdmin = user?.role === 'admin' || user?.role === 'dev'

  return (
    <Ctx.Provider value={{ user, login, logout, isAdmin }}>
      {children}
    </Ctx.Provider>
  )
}

export const useAuth = () => useContext(Ctx)
