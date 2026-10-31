import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, getToken, setLoginExpiredHandler, setToken } from '../api/client'
import type { User } from '../api/types'

export type AuthDialog = { mode: 'login' | 'register'; reason?: string } | null

interface AuthState {
  user: User | null
  // false until the stored token is checked, so pages do not flash the logged out state
  ready: boolean
  dialog: AuthDialog
  openDialog: (mode: 'login' | 'register', reason?: string) => void
  closeDialog: () => void
  login: (username: string, password: string) => Promise<User>
  register: (username: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  const [dialog, setDialog] = useState<AuthDialog>(null)

  useEffect(() => {
    setLoginExpiredHandler(() => {
      setUser(null)
      setDialog({ mode: 'login', reason: 'Your login has expired, please log in again.' })
    })
    if (!getToken()) {
      setReady(true)
      return () => setLoginExpiredHandler(null)
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setReady(true))
    return () => setLoginExpiredHandler(null)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const answer = await api.login(username, password)
    setToken(answer.token)
    setUser(answer.user)
    return answer.user
  }, [])

  const register = useCallback(async (username: string, password: string) => {
    const answer = await api.register(username, password)
    setToken(answer.token)
    setUser(answer.user)
    return answer.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setToken(null)
      setUser(null)
    }
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user,
      ready,
      dialog,
      openDialog: (mode, reason) => setDialog({ mode, reason }),
      closeDialog: () => setDialog(null),
      login,
      register,
      logout,
    }),
    [user, ready, dialog, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const state = useContext(AuthContext)
  if (!state) throw new Error('useAuth needs an AuthProvider')
  return state
}
