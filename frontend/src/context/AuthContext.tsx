import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { login as apiLogin, getMe } from '../api/client'

interface User { user_id: string; username: string; role: string }

interface AuthCtx {
  user: User | null
  token: string | null
  login: (u: string, p: string) => Promise<void>
  logout: () => void
  loading: boolean
}

const Ctx = createContext<AuthCtx>({} as AuthCtx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]   = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (token) {
      getMe()
        .then(r => setUser(r.data))
        .catch(() => logout())
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (username: string, password: string) => {
    const { data } = await apiLogin(username, password)
    localStorage.setItem('token', data.access_token)
    setToken(data.access_token)
    setUser({ user_id: data.user_id, username: data.username, role: data.role })
  }

  const logout = () => {
    localStorage.clear()
    setToken(null)
    setUser(null)
  }

  return <Ctx.Provider value={{ user, token, login, logout, loading }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
