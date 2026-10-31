import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import type { Fish } from '../../api/types'
import { FishImage } from '../../components/FishArt'
import { TemperamentBadge } from '../../components/FishBadges'
import { SearchBox } from '../../components/FishFilters'
import { Badge, Button, EmptyState, ErrorNotice, LoadingBlock, buttonClasses, inputClasses } from '../../components/ui'
import { displayName, isSoloOnly, matchesSearch } from '../../lib/fish'
import { useAdminData } from './AdminLayout'

const PAGE_SIZE = 50

type Status = 'active' | 'retired' | 'all'
type SortKey = 'id' | 'name' | 'family' | 'tanks'

const SORTERS: Record<SortKey, (a: Fish, b: Fish) => number> = {
  id: (a, b) => a.id - b.id,
  name: (a, b) => displayName(a).localeCompare(displayName(b)),
  family: (a, b) => a.family_name.localeCompare(b.family_name) || a.id - b.id,
  tanks: (a, b) => (b.fishtank_count ?? 0) - (a.fishtank_count ?? 0) || a.id - b.id,
}

function SortHeader({ label, sortKey, sort, onSort, className = '' }: { label: string; sortKey: SortKey; sort: SortKey; onSort: (key: SortKey) => void; className?: string }) {
  return (
    <th scope="col" aria-sort={sort === sortKey ? 'ascending' : undefined} className={`px-3 py-2.5 font-medium ${className}`}>
      <button type="button" onClick={() => onSort(sortKey)} className={`hover:text-ink ${sort === sortKey ? 'text-ink' : ''}`}>
        {label}
        {sort === sortKey && ' ↓'}
      </button>
    </th>
  )
}

// The admin's list of every fish, or with review set the fish whose temperament is not known yet
export function AdminFishList({ review = false }: { review?: boolean }) {
  const { fish, loading, error, reload } = useAdminData()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<Status>('active')
  const [source, setSource] = useState('')
  const [sort, setSort] = useState<SortKey>(review ? 'name' : 'id')
  const [page, setPage] = useState(0)

  useEffect(() => {
    setPage(0)
  }, [search, status, source, sort, review])
  useEffect(() => setSort(review ? 'name' : 'id'), [review])

  const sources = useMemo(() => [...new Set(fish.map((entry) => entry.data_source))].sort(), [fish])
  const results = useMemo(
    () =>
      fish
        .filter(
          (entry) =>
            matchesSearch(entry, search) &&
            (review ? !entry.retired && isSoloOnly(entry) : status === 'all' || (status === 'retired') === entry.retired) &&
            (!source || entry.data_source === source),
        )
        .sort(SORTERS[sort]),
    [fish, search, status, source, sort, review],
  )
  const pages = Math.max(1, Math.ceil(results.length / PAGE_SIZE))
  const visible = results.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  return (
    <div className="mx-auto max-w-6xl">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">{review ? 'Needs review' : 'Fish'}</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            {review
              ? 'These fish came from FishBase without a temperament, so they can only be kept alone. Add their temperament and size to let them share a tank.'
              : 'Every fish in the database. Retired fish are out of the catalogue but stay in the tanks that keep them.'}
          </p>
        </div>
        <Link to="/admin/fish/new" className={buttonClasses()}>
          + Add fish
        </Link>
      </header>

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <SearchBox value={search} onChange={setSearch} placeholder="Search name or family" />
        {!review && (
          <select aria-label="Status" value={status} onChange={(event) => setStatus(event.target.value as Status)} className={`${inputClasses} sm:w-36`}>
            <option value="active">In catalogue</option>
            <option value="retired">Retired</option>
            <option value="all">All</option>
          </select>
        )}
        <select aria-label="Data source" value={source} onChange={(event) => setSource(event.target.value)} className={`${inputClasses} sm:w-44`}>
          <option value="">Every source</option>
          {sources.map((entry) => (
            <option key={entry} value={entry}>
              {entry}
            </option>
          ))}
        </select>
      </div>

      {error && <ErrorNotice message={error} onRetry={reload} />}
      {loading && fish.length === 0 ? (
        <LoadingBlock label="Loading every fish…" />
      ) : results.length === 0 ? (
        <EmptyState title={review ? 'Nothing to review' : 'No fish match'}>
          {review ? 'Every fish in the catalogue has a known temperament.' : 'Try another search or status.'}
        </EmptyState>
      ) : (
        <>
          <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-line text-xs text-muted">
                <tr>
                  <SortHeader label="#" sortKey="id" sort={sort} onSort={setSort} className="w-14" />
                  <SortHeader label="Fish" sortKey="name" sort={sort} onSort={setSort} />
                  <SortHeader label="Family" sortKey="family" sort={sort} onSort={setSort} />
                  <th scope="col" className="px-3 py-2.5 font-medium">Temperament</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">Source</th>
                  <SortHeader label="Tanks" sortKey="tanks" sort={sort} onSort={setSort} className="text-right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {visible.map((entry) => (
                  <tr
                    key={entry.id}
                    onClick={() => navigate(`/admin/fish/${entry.id}`)}
                    className={`cursor-pointer hover:bg-surface-2 ${entry.retired ? 'text-muted' : ''}`}
                  >
                    <td className="px-3 py-2 text-muted tabular-nums">{entry.id}</td>
                    <td className="px-3 py-2">
                      <Link to={`/admin/fish/${entry.id}`} className="flex items-center gap-3" onClick={(event) => event.stopPropagation()}>
                        <FishImage fish={entry} className="h-9 w-12 shrink-0 rounded-md" />
                        <span className="min-w-0">
                          <span className="block truncate font-medium text-ink">{displayName(entry)}</span>
                          {entry.common_name && <span className="block truncate text-xs text-muted italic">{entry.scientific_name}</span>}
                        </span>
                        {entry.retired && <Badge>Retired</Badge>}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{entry.family_name}</td>
                    <td className="px-3 py-2">
                      <TemperamentBadge fish={entry} />
                    </td>
                    <td className="px-3 py-2 text-muted">{entry.data_source}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{entry.fishtank_count ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex items-center justify-between text-sm text-muted">
            <span>
              {page * PAGE_SIZE + 1}–{Math.min(results.length, (page + 1) * PAGE_SIZE)} of {results.length.toLocaleString()}
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
                Previous
              </Button>
              <Button variant="secondary" size="sm" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
