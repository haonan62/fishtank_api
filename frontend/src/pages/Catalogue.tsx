import { useCallback, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'

import type { Fish } from '../api/types'
import { FishImage } from '../components/FishArt'
import { TemperamentBadge, WaterBadges } from '../components/FishBadges'
import { FishPanel } from '../components/FishDetail'
import { EMPTY_FILTER, FishFilters, filterFish, type FishFilter } from '../components/FishFilters'
import { Button, EmptyState, ErrorNotice, LoadingBlock, inputClasses } from '../components/ui'
import { useCatalogue } from '../lib/catalogue'
import { displayName } from '../lib/fish'

const PAGE_SIZE = 48

type Sort = 'name' | 'family' | 'temperature'

const SORTERS: Record<Sort, (a: Fish, b: Fish) => number> = {
  name: (a, b) => displayName(a).localeCompare(displayName(b)),
  family: (a, b) => a.family_name.localeCompare(b.family_name) || displayName(a).localeCompare(displayName(b)),
  temperature: (a, b) => a.minimum_temperature - b.minimum_temperature || a.maximum_temperature - b.maximum_temperature,
}

export function FishCard({ fish, onOpen }: { fish: Fish; onOpen: (fish: Fish) => void }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(fish)}
      className="group flex flex-col overflow-hidden rounded-2xl border border-line bg-surface text-left shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:border-brand/50"
    >
      <FishImage fish={fish} className="aspect-[4/3] w-full" showCredit />
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="min-w-0">
          <h3 className="truncate font-medium group-hover:text-brand-strong">{displayName(fish)}</h3>
          <p className="truncate text-sm text-muted italic">{fish.common_name ? fish.scientific_name : fish.family_name}</p>
        </div>
        <div className="mt-auto flex flex-wrap gap-1.5">
          <TemperamentBadge fish={fish} />
          <WaterBadges fish={fish} />
        </div>
      </div>
    </button>
  )
}

export function Catalogue() {
  const { fish, byId, loading, error, reload } = useCatalogue()
  const [filter, setFilter] = useState<FishFilter>(EMPTY_FILTER)
  const [sort, setSort] = useState<Sort>('name')
  const [shown, setShown] = useState(PAGE_SIZE)
  const [searchParams, setSearchParams] = useSearchParams()

  const results = useMemo(() => filterFish(fish, filter).sort(SORTERS[sort]), [fish, filter, sort])
  // the open fish is in the address, so it can be shared and the back button closes it
  const openId = Number(searchParams.get('fish'))
  const openFish = openId ? (byId.get(openId) ?? null) : null
  const open = (entry: Fish) => setSearchParams({ fish: String(entry.id) })
  const close = useCallback(() => setSearchParams({}), [setSearchParams])

  const changeFilter = (next: FishFilter) => {
    setFilter(next)
    setShown(PAGE_SIZE)
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <header className="mb-8">
        <h1 className="font-display text-3xl sm:text-4xl">Fish catalogue</h1>
        <p className="mt-2 text-muted">
          {fish.length ? `${fish.length.toLocaleString()} species` : 'Every species'} from FishBase and aqua-fish.net. Open one to
          see the water it needs and who it gets along with.
        </p>
      </header>

      <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <FishFilters fish={fish} filter={filter} onChange={changeFilter} />
        </aside>

        <section aria-label="Results">
          {error && <ErrorNotice message={error} onRetry={reload} />}
          {loading && !fish.length ? (
            <LoadingBlock label="Loading the catalogue…" />
          ) : (
            <>
              <div className="mb-4 flex items-center justify-between gap-4">
                <p className="text-sm text-muted" aria-live="polite">
                  {results.length.toLocaleString()} {results.length === 1 ? 'fish' : 'fish'}
                </p>
                <label className="flex items-center gap-2 text-sm whitespace-nowrap text-muted">
                  Sort by
                  <select value={sort} onChange={(event) => setSort(event.target.value as Sort)} className={`${inputClasses} h-9 w-auto`}>
                    <option value="name">Name</option>
                    <option value="family">Family</option>
                    <option value="temperature">Temperature</option>
                  </select>
                </label>
              </div>
              {results.length === 0 ? (
                <EmptyState title="No fish match" action={<Button variant="secondary" onClick={() => changeFilter(EMPTY_FILTER)}>Clear filters</Button>}>
                  Try a shorter name or fewer filters.
                </EmptyState>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {results.slice(0, shown).map((entry) => (
                    <FishCard key={entry.id} fish={entry} onOpen={open} />
                  ))}
                </div>
              )}
              {shown < results.length && (
                <div className="mt-8 flex justify-center">
                  <Button variant="secondary" onClick={() => setShown(shown + PAGE_SIZE)}>
                    Show more ({(results.length - shown).toLocaleString()} left)
                  </Button>
                </div>
              )}
            </>
          )}
        </section>
      </div>

      <FishPanel fish={openFish} onClose={close} />
    </div>
  )
}
