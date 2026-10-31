import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useOutletContext } from 'react-router'

import { api } from '../../api/client'
import type { Fish } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { AuthDialog } from '../../components/AuthDialog'
import { Logo } from '../../components/Layout'
import { Button, EmptyState, LoadingBlock, buttonClasses } from '../../components/ui'
import { useCatalogue } from '../../lib/catalogue'
import { isSoloOnly } from '../../lib/fish'

// Every admin page shares the full list of fish, retired ones and fishtank counts included
export interface AdminData {
  fish: Fish[]
  loading: boolean
  error: string | null
  reload: () => void
  // after a change the public catalogue is loaded again as well
  changed: (fish?: Fish) => void
}

export function useAdminData() {
  return useOutletContext<AdminData>()
}

const linkClasses = ({ isActive }: { isActive: boolean }) =>
  `flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors ${
    isActive ? 'bg-brand-soft text-brand-strong' : 'text-muted hover:bg-surface-2 hover:text-ink'
  }`

function AdminPortal() {
  const catalogue = useCatalogue()
  const [fish, setFish] = useState<Fish[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .listFish(true)
      .then((loaded) => {
        if (cancelled) return
        setFish(loaded)
        setError(null)
      })
      .catch((reason: Error) => !cancelled && setError(reason.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [version])

  const reload = useCallback(() => setVersion((current) => current + 1), [])
  const changed = useCallback(
    (updated?: Fish) => {
      if (updated) setFish((current) => [...current.filter((entry) => entry.id !== updated.id), updated].sort((a, b) => a.id - b.id))
      else reload()
      catalogue.reload()
    },
    [catalogue, reload],
  )

  const reviewCount = fish.filter((entry) => !entry.retired && isSoloOnly(entry)).length

  return (
    <div className="flex min-h-dvh flex-col bg-bg lg:flex-row">
      <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:h-dvh lg:w-64 lg:shrink-0 lg:border-r lg:border-b-0">
        <div className="flex h-16 items-center gap-2 px-4">
          <Logo />
          <span className="font-display text-xl sm:hidden">Fishtank</span>
          <span className="rounded-md bg-ink px-1.5 py-0.5 text-[11px] font-semibold tracking-wide text-bg uppercase">Admin</span>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:overflow-visible">
          <NavLink to="/admin/fish" end className={linkClasses}>
            Fish
            <span className="text-xs text-muted">{fish.length || ''}</span>
          </NavLink>
          <NavLink to="/admin/review" className={linkClasses}>
            Needs review
            {reviewCount > 0 && <span className="rounded-full bg-warn-soft px-2 text-xs text-warn">{reviewCount}</span>}
          </NavLink>
          <NavLink to="/admin/users" className={linkClasses}>
            Users
          </NavLink>
          <Link to="/" className="rounded-lg px-3 py-2 text-sm whitespace-nowrap text-muted hover:text-ink lg:mt-6">
            ← Back to the app
          </Link>
        </nav>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-8 sm:px-8">
        <Outlet context={{ fish, loading, error, reload, changed } satisfies AdminData} />
      </main>
    </div>
  )
}

// the server checks every admin request itself, this only keeps others from a page they cannot use
export function AdminLayout() {
  const { user, ready, openDialog } = useAuth()
  if (!ready) return <LoadingBlock />
  if (user?.role === 'admin') return <AdminPortal />
  return (
    <div className="mx-auto max-w-xl px-4 py-20">
      <EmptyState
        title="Admins only"
        action={
          user ? (
            <Link to="/" className={buttonClasses()}>
              Back to the app
            </Link>
          ) : (
            <Button onClick={() => openDialog('login', 'Log in with an admin account.')}>Log in</Button>
          )
        }
      >
        {user ? `${user.username} is not an admin. An admin can promote you under Users.` : 'Please log in with an admin account.'}
      </EmptyState>
      <AuthDialog />
    </div>
  )
}
