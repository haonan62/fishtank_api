import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'

import { api } from '../../api/client'
import type { TemperamentSuggestion } from '../../api/types'
import { useToast } from '../../components/Toasts'
import { Badge, Button, EmptyState, ErrorNotice, LoadingBlock } from '../../components/ui'
import { displayName } from '../../lib/fish'
import { timeAgo } from '../../lib/time'
import { useAdminData } from './AdminLayout'

type Status = 'pending' | 'approved' | 'rejected'

const TABS: { value: Status; label: string }[] = [
  { value: 'pending', label: 'Waiting' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
]

function Value({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-medium">{value ?? '—'}</dd>
    </div>
  )
}

// What users suggested for fish without a temperament. Approving copies the values onto the fish, checked again
export function AdminSuggestions() {
  const { changed, refreshSuggestions } = useAdminData()
  const toast = useToast()
  const [status, setStatus] = useState<Status>('pending')
  const [suggestions, setSuggestions] = useState<TemperamentSuggestion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    api
      .listSuggestions(status)
      .then((answer) => {
        setSuggestions(answer.suggestions)
        setError(null)
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [status])
  useEffect(load, [load])

  const review = async (suggestion: TemperamentSuggestion, approve: boolean) => {
    setBusyId(suggestion.id)
    try {
      if (approve) {
        const answer = await api.approveSuggestion(suggestion.id)
        changed(answer.fish)
        toast({ tone: 'success', title: `${displayName(answer.fish)} has a temperament now`, detail: 'It can share a tank.' })
      } else {
        await api.rejectSuggestion(suggestion.id)
        toast({ tone: 'info', title: 'Suggestion rejected' })
      }
      setSuggestions((current) => current.filter((entry) => entry.id !== suggestion.id))
      refreshSuggestions()
    } catch (reason) {
      toast({ tone: 'danger', title: 'That did not work', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-6">
        <h1 className="font-display text-3xl">Suggestions</h1>
        <p className="mt-1 text-sm text-muted">
          Users suggest the temperament and size of fish that have none yet. Approving one copies its values onto the fish, so it
          can share a tank.
        </p>
      </header>
      <div role="tablist" className="mb-5 flex gap-1.5">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={status === tab.value}
            onClick={() => setStatus(tab.value)}
            className={`h-8 rounded-full px-3 text-sm ${status === tab.value ? 'bg-brand text-on-brand' : 'border border-line bg-surface text-muted hover:text-ink'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && <ErrorNotice message={error} onRetry={load} />}
      {loading ? (
        <LoadingBlock />
      ) : suggestions.length === 0 ? (
        <EmptyState title={status === 'pending' ? 'Nothing waiting' : `No ${status} suggestions`}>
          {status === 'pending' && 'Users can suggest a temperament from the page of any fish that has none.'}
        </EmptyState>
      ) : (
        <ul className="space-y-4">
          {suggestions.map((suggestion) => {
            const known = suggestion.fish.cross_species_temperament !== 'unknown' && suggestion.fish.in_species_temperament !== 'unknown'
            return (
              <li key={suggestion.id} className="rounded-2xl border border-line bg-surface p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Link to={`/admin/fish/${suggestion.fish.id}`} className="font-medium hover:text-brand-strong">
                      {displayName(suggestion.fish)}
                    </Link>
                    {suggestion.fish.common_name && <p className="text-sm text-muted italic">{suggestion.fish.scientific_name}</p>}
                  </div>
                  <p className="text-xs text-muted">
                    from {suggestion.username ?? 'a removed user'} · {timeAgo(suggestion.created_at)}
                    {suggestion.reviewed_by && ` · ${suggestion.status} by ${suggestion.reviewed_by}`}
                  </p>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <Value label="With other species" value={suggestion.cross_species_temperament} />
                  <Value label="With its own kind" value={suggestion.in_species_temperament} />
                  <Value label="Size (cm)" value={suggestion.minimum_size !== null ? `${suggestion.minimum_size}–${suggestion.maximum_size}` : null} />
                  <Value label="Smallest group" value={suggestion.minimum_group_size} />
                </dl>
                {suggestion.note && <p className="mt-3 rounded-lg bg-surface-2 px-3 py-2 text-sm">“{suggestion.note}”</p>}
                {status === 'pending' && (
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <Button size="sm" busy={busyId === suggestion.id} disabled={busyId !== null} onClick={() => review(suggestion, true)}>
                      Approve
                    </Button>
                    <Button variant="secondary" size="sm" disabled={busyId !== null} onClick={() => review(suggestion, false)}>
                      Reject
                    </Button>
                    {known && <Badge tone="warn">The fish has a temperament since, approving replaces it</Badge>}
                    {suggestion.fish.retired && <Badge>Retired</Badge>}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
