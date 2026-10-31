import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, hasSession, setLoginExpiredHandler } from '../api/client'
import type { User } from '../api/types'

export type AuthDialog = { mode: 'login' | 'register'; reason?: string } | null

interface AuthState {
  user: User | null
  // false until the login cookie is checked, so pages do not flash the logged out state
  ready: boolean
  dialog: AuthDialog
  openDialog: (mode: 'login' | 'register', reason?: string) => void
  closeDialog: () => void
  login: (username: string, password: string) => Promise<User>
  register: (username: string, password: string) => Promise<User>
  logout: () => Promise<void>
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>
  deleteAccount: (password: string) => Promise<void>
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
    if (!hasSession()) {
      setReady(true)
      return () => setLoginExpiredHandler(null)
    }
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setReady(true))
    return () => setLoginExpiredHandler(null)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const answer = await api.login(username, password)
    setUser(answer.user)
    return answer.user
  }, [])

  const register = useCallback(async (username: string, password: string) => {
    const answer = await api.register(username, password)
    setUser(answer.user)
    return answer.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setUser(null)
    }
  }, [])

  // other devices are logged out, this one stays logged in
  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    setUser(await api.changePassword(currentPassword, newPassword))
  }, [])

  const deleteAccount = useCallback(async (password: string) => {
    await api.deleteAccount(password)
    setUser(null)
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
      changePassword,
      deleteAccount,
    }),
    [user, ready, dialog, login, register, logout, changePassword, deleteAccount],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const state = useContext(AuthContext)
  if (!state) throw new Error('useAuth needs an AuthProvider')
  return state
}
