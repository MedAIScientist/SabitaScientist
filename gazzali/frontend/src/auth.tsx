import React, { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

interface AuthCtx {
  token: string | null
  username: string | null
  isAdmin: boolean
  role: string
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(sessionStorage.getItem('pm_token'))
  const [username, setUsername] = useState<string | null>(sessionStorage.getItem('pm_username'))
  const [isAdmin, setIsAdmin] = useState(sessionStorage.getItem('pm_admin') === 'true')
  const [role, setRole] = useState<string>(sessionStorage.getItem('pm_role') || 'student')

  /**
   * Ask the server who this session belongs to.
   *
   * sessionStorage seeds the first paint, but it cannot be trusted as the source of
   * truth: the Microsoft sign-in callback only hands back a token, and a role is
   * decided server-side from the e-mail domain, so it can change while a session is
   * open. Reading the role from storage alone left every professor who signed in
   * with Microsoft looking like a student until they logged in again with a password.
   */
  useEffect(() => {
    if (!token) return
    let cancelled = false
    api
      .me()
      .then(me => {
        if (cancelled) return
        sessionStorage.setItem('pm_username', me.username)
        sessionStorage.setItem('pm_admin', String(me.is_admin))
        sessionStorage.setItem('pm_role', me.role || 'student')
        setUsername(me.username)
        setIsAdmin(Boolean(me.is_admin))
        setRole(me.role || 'student')
      })
      // An expired token is already handled by the api client, which clears it and
      // returns to the sign-in page; anything else keeps the seeded values.
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [token])

  async function login(u: string, p: string) {
    const data = await api.login(u, p)
    sessionStorage.setItem('pm_token', data.token)
    sessionStorage.setItem('pm_username', data.username)
    sessionStorage.setItem('pm_admin', String(data.is_admin))
    sessionStorage.setItem('pm_role', data.role || 'student')
    setToken(data.token)
    setUsername(data.username)
    setIsAdmin(data.is_admin)
    setRole(data.role || 'student')
  }

  function logout() {
    sessionStorage.clear()
    setToken(null)
    setUsername(null)
    setIsAdmin(false)
    setRole('student')
  }

  return <AuthContext.Provider value={{ token, username, isAdmin, role, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
