import { createContext, useContext, useState } from 'react'

const Ctx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('a1doc_user')) } catch { return null }
  })

  function login(userData, token) {
    localStorage.setItem('a1doc_token', token)
    localStorage.setItem('a1doc_user', JSON.stringify(userData))
    setUser(userData)
  }

  function logout() {
    localStorage.removeItem('a1doc_token')
    localStorage.removeItem('a1doc_user')
    setUser(null)
  }

  const isAdmin = user?.role === 'admin' || user?.role === 'dev'

  return (
    <Ctx.Provider value={{ user, login, logout, isAdmin }}>
      {children}
    </Ctx.Provider>
  )
}

export const useAuth = () => useContext(Ctx)
