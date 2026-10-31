import { useCallback, useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { Role, User } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { SearchBox } from '../../components/FishFilters'
import { useToast } from '../../components/Toasts'
import { Badge, Button, ConfirmDialog, ErrorNotice, LoadingBlock } from '../../components/ui'

export function AdminUsers() {
  const { user: me } = useAuth()
  const toast = useToast()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [changing, setChanging] = useState<{ user: User; role: Role } | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    api
      .listUsers()
      .then((loaded) => {
        setUsers(loaded)
        setError(null)
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [])
  useEffect(load, [load])

  const shown = useMemo(
    () => users.filter((user) => user.username.toLowerCase().includes(search.trim().toLowerCase())),
    [users, search],
  )
  const admins = users.filter((user) => user.role === 'admin').length

  const changeRole = async () => {
    if (!changing) return
    setBusy(true)
    try {
      const updated = await api.setRole(changing.user.id, changing.role)
      setUsers((current) => current.map((user) => (user.id === updated.id ? updated : user)))
      toast({ tone: 'success', title: `${updated.username} is now ${updated.role === 'admin' ? 'an admin' : 'a user'}` })
      // demoting yourself ends your admin rights, the app reloads to show it
      if (updated.id === me?.id && updated.role !== 'admin') window.location.assign('/')
    } catch (reason) {
      toast({ tone: 'danger', title: 'Could not change the role', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setBusy(false)
      setChanging(null)
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-6">
        <h1 className="font-display text-3xl">Users</h1>
        <p className="mt-1 text-sm text-muted">
          {users.length} {users.length === 1 ? 'user' : 'users'}, {admins} {admins === 1 ? 'admin' : 'admins'}. Admins manage the fish
          catalogue and the roles of others. There is always at least one admin.
        </p>
      </header>
      <div className="mb-4 max-w-sm">
        <SearchBox value={search} onChange={setSearch} placeholder="Search usernames" />
      </div>
      {error && <ErrorNotice message={error} onRetry={load} />}
      {loading && users.length === 0 ? (
        <LoadingBlock label="Loading users…" />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="border-b border-line text-xs text-muted">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-medium">Username</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Role</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Joined</th>
                <th scope="col" className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {shown.map((user) => {
                const lastAdmin = user.role === 'admin' && admins <= 1
                return (
                  <tr key={user.id}>
                    <td className="px-4 py-3 font-medium">
                      {user.username} {user.id === me?.id && <span className="text-xs font-normal text-muted">(you)</span>}
                    </td>
                    <td className="px-4 py-3">{user.role === 'admin' ? <Badge tone="brand">Admin</Badge> : <Badge>User</Badge>}</td>
                    <td className="px-4 py-3 text-muted">{new Date(user.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={lastAdmin}
                        title={lastAdmin ? 'The last admin cannot become a user' : undefined}
                        onClick={() => setChanging({ user, role: user.role === 'admin' ? 'user' : 'admin' })}
                      >
                        {user.role === 'admin' ? 'Make user' : 'Make admin'}
                      </Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <ConfirmDialog
        open={changing !== null}
        title={changing?.role === 'admin' ? `Make ${changing.user.username} an admin?` : `Make ${changing?.user.username} a user?`}
        confirmLabel={changing?.role === 'admin' ? 'Make admin' : 'Make user'}
        danger={changing?.role === 'user'}
        busy={busy}
        onConfirm={changeRole}
        onClose={() => setChanging(null)}
      >
        {changing?.role === 'admin'
          ? 'They will be able to add, change, retire and remove fish, and change the roles of other users.'
          : changing?.user.id === me?.id
            ? 'You will lose access to the admin pages straight away.'
            : 'They will lose access to the admin pages straight away.'}
      </ConfirmDialog>
    </div>
  )
}
