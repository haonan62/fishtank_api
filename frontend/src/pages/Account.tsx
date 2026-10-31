import { useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { useToast } from '../components/Toasts'
import { Button, EmptyState, LoadingBlock, Modal, TextField } from '../components/ui'
import { timeAgo } from '../lib/time'

type Errors = Record<string, string | undefined>

// a wrong password or a field the api names is shown next to that field, anything else under the form
function errorsFrom(reason: unknown, fields: Record<string, string>): Errors {
  if (reason instanceof ApiError && reason.field && fields[reason.field]) return { [fields[reason.field]!]: reason.message }
  return { form: reason instanceof Error ? reason.message : String(reason) }
}

function Section({ title, description, children, danger = false }: { title: string; description: string; children: ReactNode; danger?: boolean }) {
  return (
    <section className={`rounded-2xl border bg-surface p-6 shadow-[var(--shadow-card)] ${danger ? 'border-danger/40' : 'border-line'}`}>
      <h2 className={`font-display text-xl ${danger ? 'text-danger' : ''}`}>{title}</h2>
      <p className="mt-1 mb-5 text-sm text-muted">{description}</p>
      {children}
    </section>
  )
}

function FormError({ message }: { message?: string }) {
  if (!message) return null
  return (
    <p role="alert" className="text-sm text-danger">
      {message}
    </p>
  )
}

function ChangePassword() {
  const { changePassword } = useAuth()
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const found: Errors = {}
    if (!current) found.current = 'Enter your current password'
    if (next.length < 8 || next.length > 128) found.next = 'At least 8 characters'
    else if (next !== repeat) found.repeat = 'The two new passwords are not the same'
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      await changePassword(current, next)
      setCurrent('')
      setNext('')
      setRepeat('')
      toast({ tone: 'success', title: 'Your password is changed', detail: 'Other devices are logged out.' })
    } catch (reason) {
      setErrors(errorsFrom(reason, { current_password: 'current', new_password: 'next' }))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title="Change password" description="Every other device you are logged in on is logged out, this one stays logged in.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <TextField
          label="Current password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
          error={errors.current}
        />
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(event) => setNext(event.target.value)}
          error={errors.next}
          hint="At least 8 characters"
        />
        <TextField
          label="New password again"
          type="password"
          autoComplete="new-password"
          value={repeat}
          onChange={(event) => setRepeat(event.target.value)}
          error={errors.repeat}
        />
        <FormError message={errors.form} />
        <Button type="submit" busy={busy}>
          Change password
        </Button>
      </form>
    </Section>
  )
}

function DeleteAccount() {
  const { user, deleteAccount } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)

  const close = () => {
    setOpen(false)
    setPassword('')
    setErrors({})
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!password) {
      setErrors({ password: 'Enter your password to confirm' })
      return
    }
    setBusy(true)
    try {
      await deleteAccount(password)
      toast({ tone: 'info', title: 'Your account is removed', detail: 'Thanks for keeping fish with us.' })
      navigate('/')
    } catch (reason) {
      setErrors(errorsFrom(reason, { password: 'password' }))
      setBusy(false)
    }
  }

  return (
    <Section danger title="Remove account" description="Your account and every tank saved in it are removed for good. This cannot be undone.">
      <Button variant="danger" onClick={() => setOpen(true)}>
        Remove my account
      </Button>
      <Modal open={open} onClose={close} title="Remove your account?">
        <form onSubmit={submit} className="space-y-4" noValidate>
          <p className="text-sm text-muted">
            <span className="font-medium text-ink">{user?.username}</span> and all of its saved tanks will be removed.
            Enter your password to confirm.
          </p>
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={errors.password}
          />
          <FormError message={errors.form} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button type="submit" variant="danger" busy={busy}>
              Remove account
            </Button>
          </div>
        </form>
      </Modal>
    </Section>
  )
}

export function Account() {
  const { user, ready, openDialog } = useAuth()
  if (!ready) return <LoadingBlock />
  if (!user) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <EmptyState title="Log in to see your account" action={<Button onClick={() => openDialog('login')}>Log in</Button>} />
      </div>
    )
  }
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <header className="mb-8">
        <h1 className="font-display text-3xl sm:text-4xl">Account</h1>
        <p className="mt-2 text-muted">
          {user.username}
          {user.role === 'admin' && ' · admin'} · joined {timeAgo(user.created_at)}
        </p>
      </header>
      <div className="space-y-6">
        <ChangePassword />
        <DeleteAccount />
      </div>
    </div>
  )
}
