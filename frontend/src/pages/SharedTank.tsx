import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError, api } from '../api/client'
import type { Fish, SharedFishtank } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Aquarium } from '../components/Aquarium'
import { FishArt } from '../components/FishArt'
import { TemperamentBadge } from '../components/FishBadges'
import { FishPanel } from '../components/FishDetail'
import { skippedDetail } from '../components/ShareTank'
import { StockingPanel } from '../components/StockingPanel'
import { WaterPanel, type Resident } from '../components/TankParts'
import { useToast } from '../components/Toasts'
import { Button, EmptyState, ErrorNotice, LoadingBlock, buttonClasses } from '../components/ui'
import { useCatalogue } from '../lib/catalogue'
import { displayName } from '../lib/fish'
import { timeAgo } from '../lib/time'
import { rememberVisitorTank, setLastTankKey } from '../lib/visitorTanks'

// A tank someone shared: to look at, and to copy into a tank of your own
export function SharedTank() {
  const { token = '' } = useParams()
  const { user } = useAuth()
  const { byId, lookup } = useCatalogue()
  const toast = useToast()
  const navigate = useNavigate()
  const [tank, setTank] = useState<SharedFishtank | null>(null)
  const [missing, setMissing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copying, setCopying] = useState(false)
  const [openFish, setOpenFish] = useState<Fish | null>(null)

  useEffect(() => {
    setTank(null)
    api
      .getSharedTank(token)
      .then(setTank)
      .catch((reason) => {
        if (reason instanceof ApiError && reason.status === 404) setMissing(true)
        else setError(reason instanceof Error ? reason.message : String(reason))
      })
  }, [token])

  // retired fish are not in the catalogue, they are looked up one by one
  useEffect(() => {
    tank?.fish.filter((entry) => !byId.has(entry.id)).forEach((entry) => lookup(entry.id))
  }, [tank, byId, lookup])

  const residents: Resident[] = useMemo(
    () =>
      (tank?.fish ?? []).flatMap((entry) => {
        const fish = byId.get(entry.id)
        return fish ? [{ fish, count: entry.count }] : []
      }),
    [tank, byId],
  )

  const copy = async () => {
    setCopying(true)
    try {
      const { fishtank, skipped } = await api.copySharedTank(token)
      if (!fishtank.saved) rememberVisitorTank(fishtank.key)
      setLastTankKey(fishtank.key)
      toast({ tone: 'success', title: 'Copied, this is your tank now', detail: skippedDetail(skipped) })
      navigate(`/tanks/${fishtank.key}`)
    } catch (reason) {
      toast({ tone: 'danger', title: 'Could not copy the tank', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setCopying(false)
    }
  }

  if (missing) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <EmptyState title="This tank is not shared anymore" action={<Link to="/" className={buttonClasses()}>Build your own</Link>}>
          Its owner stopped sharing it, or it expired.
        </EmptyState>
      </div>
    )
  }
  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <ErrorNotice message={error} />
      </div>
    )
  }
  if (!tank) return <LoadingBlock label="Filling the tank…" />

  const total = tank.fish.reduce((sum, entry) => sum + entry.count, 0)
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted">Shared {tank.owner ? `by ${tank.owner}` : 'tank'} · changed {timeAgo(tank.updated_at)}</p>
          <h1 className="mt-1 font-display text-3xl sm:text-4xl">{tank.name ?? 'A shared tank'}</h1>
          <p className="mt-1 text-sm text-muted">
            {tank.size.length} × {tank.size.width} × {tank.size.height} cm · {tank.fish.length} species · {total} fish
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button onClick={copy} busy={copying}>
            Copy to my tanks
          </Button>
          <span className="text-xs text-muted">{user ? 'Saved to your account' : 'Kept for a day, or sign up to keep it'}</span>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <Aquarium entries={residents} className="h-[20rem] sm:h-[26rem]" />
          <section className="rounded-2xl border border-line bg-surface p-5">
            <h2 className="font-display text-lg">In this tank</h2>
            {residents.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted">No fish yet.</p>
            ) : (
              <ul className="mt-2 divide-y divide-line">
                {residents.map(({ fish, count }) => (
                  <li key={fish.id}>
                    <button type="button" onClick={() => setOpenFish(fish)} className="flex w-full items-center gap-3 py-2.5 text-left">
                      <span className="flex h-10 w-14 shrink-0 items-center justify-center rounded-lg bg-surface-2">
                        <FishArt fish={fish} className="w-11" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{displayName(fish)}</span>
                        <TemperamentBadge fish={fish} />
                      </span>
                      <span className="text-sm text-muted tabular-nums">× {count}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
        <aside className="space-y-6">
          <StockingPanel tank={tank} byId={byId} />
          <WaterPanel residents={residents} />
        </aside>
      </div>
      <FishPanel fish={openFish} onClose={() => setOpenFish(null)} />
    </div>
  )
}
