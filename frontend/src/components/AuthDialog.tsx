import { useEffect, useState, type FormEvent } from 'react'

import { ApiError, api } from '../api/client'
import type { Fishtank } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { tankTitle } from '../lib/useMyTanks'
import { forgetVisitorTank, visitorTankKeys } from '../lib/visitorTanks'
import { useToast } from './Toasts'
import { Button, Modal, TextField } from './ui'

const USERNAME_PATTERN = /^[A-Za-z0-9_.-]{3,32}$/

// Log in or sign up without leaving the page, then offer to keep the tanks built as a visitor
export function AuthDialog() {
  const { dialog, closeDialog, openDialog, login, register } = useAuth()
  const toast = useToast()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ username?: string; password?: string; form?: string }>({})
  const [busy, setBusy] = useState(false)
  const [visitorTanks, setVisitorTanks] = useState<Fishtank[] | null>(null)

  const mode = dialog?.mode ?? 'login'
  useEffect(() => {
    setErrors({})
    setPassword('')
  }, [dialog?.mode])

  const checkLocally = () => {
    if (mode === 'login') return {}
    const found: typeof errors = {}
    if (!USERNAME_PATTERN.test(username)) found.username = '3 to 32 letters, digits, dots, dashes or underscores'
    if (password.length < 8 || password.length > 128) found.password = 'At least 8 characters'
    return found
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const found = checkLocally()
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      const user = mode === 'login' ? await login(username, password) : await register(username, password)
      toast({ tone: 'success', title: mode === 'login' ? `Welcome back, ${user.username}` : `Welcome, ${user.username}` })
      setPassword('')
      await offerToKeepTanks()
    } catch (reason) {
      if (reason instanceof ApiError && (reason.field === 'username' || reason.field === 'password')) {
        setErrors({ [reason.field]: reason.message })
      } else {
        setErrors({ form: reason instanceof Error ? reason.message : String(reason) })
      }
    } finally {
      setBusy(false)
    }
  }

  const offerToKeepTanks = async () => {
    const tanks = await Promise.all(visitorTankKeys().map((key) => api.getTank(key).catch(() => null)))
    const open = tanks.filter((tank): tank is Fishtank => tank !== null && !tank.saved && tank.fish.length > 0)
    if (open.length) setVisitorTanks(open)
    else closeDialog()
  }

  const keepTanks = async () => {
    if (!visitorTanks) return
    setBusy(true)
    let kept = 0
    for (const tank of visitorTanks) {
      try {
        await api.saveTank(tank.key)
        forgetVisitorTank(tank.key)
        kept++
      } catch {
        // an expired tank cannot be kept, the others still are
      }
    }
    setBusy(false)
    setVisitorTanks(null)
    closeDialog()
    toast({ tone: 'success', title: kept === 1 ? 'Your tank is saved' : `${kept} tanks are saved`, detail: 'Find them under My tanks.' })
    window.dispatchEvent(new Event('fishtank:tanks-changed'))
  }

  if (visitorTanks) {
    return (
      <Modal open onClose={() => { setVisitorTanks(null); closeDialog() }} title="Keep the tanks you built?">
        <p className="text-sm text-muted">
          You built {visitorTanks.length === 1 ? 'a tank' : `${visitorTanks.length} tanks`} before logging in. Keep{' '}
          {visitorTanks.length === 1 ? 'it' : 'them'} in your account, so {visitorTanks.length === 1 ? 'it does' : 'they do'} not expire.
        </p>
        <ul className="mt-4 space-y-1 text-sm">
          {visitorTanks.map((tank) => (
            <li key={tank.key} className="flex justify-between rounded-lg bg-surface-2 px-3 py-2">
              <span>{tankTitle(tank)}</span>
              <span className="text-muted">{tank.fish.reduce((total, entry) => total + entry.count, 0)} fish</span>
            </li>
          ))}
        </ul>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => { setVisitorTanks(null); closeDialog() }}>
            Not now
          </Button>
          <Button busy={busy} onClick={keepTanks}>
            Keep {visitorTanks.length === 1 ? 'it' : 'them'}
          </Button>
        </div>
      </Modal>
    )
  }

  return (
    <Modal open={dialog !== null} onClose={closeDialog} title={mode === 'login' ? 'Log in' : 'Create your account'}>
      {dialog?.reason && <p className="mb-4 rounded-lg bg-brand-soft px-3 py-2 text-sm text-brand-strong">{dialog.reason}</p>}
      <form onSubmit={submit} className="space-y-4" noValidate>
        <TextField
          label="Username"
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          error={errors.username}
          hint={mode === 'register' ? 'Letters, digits, dots, dashes or underscores' : undefined}
          required
        />
        <TextField
          label="Password"
          type="password"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={errors.password}
          hint={mode === 'register' ? 'At least 8 characters' : undefined}
          required
        />
        {errors.form && (
          <p role="alert" className="text-sm text-danger">
            {errors.form}
          </p>
        )}
        <Button type="submit" busy={busy} className="w-full">
          {mode === 'login' ? 'Log in' : 'Create account'}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        {mode === 'login' ? 'New here? ' : 'Already have an account? '}
        <button
          type="button"
          onClick={() => openDialog(mode === 'login' ? 'register' : 'login')}
          className="font-medium text-brand hover:underline"
        >
          {mode === 'login' ? 'Create an account' : 'Log in'}
        </button>
      </p>
    </Modal>
  )
}
