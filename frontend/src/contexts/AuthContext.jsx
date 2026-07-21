import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TOKEN_KEY, USER_KEY, setUnauthorizedHandler } from '../api'

const Ctx = createContext(null)

export function AuthProvider({ children }) {
  const navigate = useNavigate()
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY)) } catch { return null }
  })

  function login(userData, token) {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(userData))
    setUser(userData)
  }

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
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
