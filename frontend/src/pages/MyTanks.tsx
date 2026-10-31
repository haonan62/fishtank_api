import { useState } from 'react'
import { Link } from 'react-router'

import { api } from '../api/client'
import type { Fishtank } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { FishArt } from '../components/FishArt'
import { useToast } from '../components/Toasts'
import { Badge, Button, ConfirmDialog, EmptyState, ErrorNotice, LoadingBlock } from '../components/ui'
import { useCatalogue } from '../lib/catalogue'
import { displayName } from '../lib/fish'
import { timeAgo, timeLeft } from '../lib/time'
import { tankTitle, useMyTanks } from '../lib/useMyTanks'
import { forgetVisitorTank } from '../lib/visitorTanks'
import { useBuildTank } from './Home'

function TankCard({ tank, onRemove }: { tank: Fishtank; onRemove: (tank: Fishtank) => void }) {
  const { byId } = useCatalogue()
  const total = tank.fish.reduce((sum, entry) => sum + entry.count, 0)
  return (
    <div className="group relative flex flex-col rounded-2xl border border-line bg-surface shadow-[var(--shadow-card)] transition hover:border-brand/50">
      <Link to={`/tanks/${tank.key}`} className="flex flex-1 flex-col p-5">
        <div
          className="mb-4 flex h-24 items-center justify-center gap-1 overflow-hidden rounded-xl px-3"
          style={{ background: 'linear-gradient(180deg, var(--color-water-top), var(--color-water-bottom))' }}
        >
          {tank.fish.slice(0, 5).map((entry) => {
            const fish = byId.get(entry.id)
            return fish ? <FishArt key={entry.id} fish={fish} className="w-12 shrink-0" /> : null
          })}
          {tank.fish.length === 0 && <span className="text-sm text-white/90">Empty</span>}
        </div>
        <div className="flex items-start justify-between gap-2">
          <h2 className="truncate font-medium group-hover:text-brand-strong">{tankTitle(tank)}</h2>
          {!tank.saved && <Badge tone="warn">Not saved</Badge>}
        </div>
        <p className="mt-1 truncate text-sm text-muted">
          {tank.fish.length === 0
            ? 'No fish yet'
            : `${total} fish · ${tank.fish.map((entry) => (byId.get(entry.id) ? displayName(byId.get(entry.id)!) : entry.scientific_name)).join(', ')}`}
        </p>
        <p className="mt-3 text-xs text-muted">
          {tank.size.length} × {tank.size.width} × {tank.size.height} cm · changed {timeAgo(tank.updated_at)}
          {tank.expires_at && ` · expires in ${timeLeft(tank.expires_at)}`}
        </p>
      </Link>
      <button
        type="button"
        onClick={() => onRemove(tank)}
        aria-label={`Remove ${tankTitle(tank)}`}
        className="absolute top-3 right-3 size-8 rounded-full bg-surface/80 text-lg leading-none text-muted opacity-0 backdrop-blur transition group-hover:opacity-100 hover:text-danger focus:opacity-100"
      >
        ×
      </button>
    </div>
  )
}

export function MyTanks() {
  const { user, ready, openDialog } = useAuth()
  const { saved, visitor, loading, error, reload } = useMyTanks()
  const { build, busy } = useBuildTank()
  const toast = useToast()
  const [removing, setRemoving] = useState<Fishtank | null>(null)
  const [removeBusy, setRemoveBusy] = useState(false)

  const remove = async () => {
    if (!removing) return
    setRemoveBusy(true)
    try {
      await api.deleteTank(removing.key)
      forgetVisitorTank(removing.key)
      toast({ tone: 'info', title: `${tankTitle(removing)} was removed` })
      reload()
    } catch (reason) {
      toast({ tone: 'danger', title: 'Could not remove the tank', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setRemoveBusy(false)
      setRemoving(null)
    }
  }

  const buildButton = (
    <Button onClick={build} busy={busy}>
      + Build a tank
    </Button>
  )

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl">My tanks</h1>
          <p className="mt-2 text-muted">{user ? 'Your saved tanks, latest change first.' : 'Tanks you built on this device.'}</p>
        </div>
        {buildButton}
      </header>

      {error && <ErrorNotice message={error} onRetry={reload} />}
      {!ready || loading ? (
        <LoadingBlock label="Finding your tanks…" />
      ) : (
        <div className="space-y-10">
          {visitor.length > 0 && (
            <section>
              <div className="mb-4 flex flex-col gap-3 rounded-2xl bg-brand-soft px-5 py-4 text-sm text-brand-strong sm:flex-row sm:items-center sm:justify-between">
                <p>
                  {visitor.length === 1 ? 'This tank is' : 'These tanks are'} not saved and expire a day after the last change.
                </p>
                {!user && (
                  <Button size="sm" onClick={() => openDialog('register', 'Create an account to keep your tanks.')}>
                    Sign up to keep {visitor.length === 1 ? 'it' : 'them'}
                  </Button>
                )}
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {visitor.map((tank) => (
                  <TankCard key={tank.key} tank={tank} onRemove={setRemoving} />
                ))}
              </div>
            </section>
          )}

          {user && saved.length > 0 && (
            <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {saved.map((tank) => (
                <TankCard key={tank.key} tank={tank} onRemove={setRemoving} />
              ))}
            </section>
          )}

          {saved.length === 0 && visitor.length === 0 && (
            <EmptyState title="No tanks yet" action={buildButton}>
              {user ? 'Build your first tank and it is saved here.' : 'Build a tank to try which fish get along. '}
              {!user && (
                <>
                  Already have tanks?{' '}
                  <button type="button" onClick={() => openDialog('login')} className="font-medium text-brand hover:underline">
                    Log in
                  </button>
                </>
              )}
            </EmptyState>
          )}
        </div>
      )}

      <ConfirmDialog
        open={removing !== null}
        title="Remove this tank?"
        confirmLabel="Remove tank"
        danger
        busy={removeBusy}
        onConfirm={remove}
        onClose={() => setRemoving(null)}
      >
        {removing && `${tankTitle(removing)} and its fish will be gone for good.`}
      </ConfirmDialog>
    </div>
  )
}
