import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'

import { api } from '../../api/client'
import type { AuditEvent } from '../../api/types'
import { Button, EmptyState, ErrorNotice, LoadingBlock } from '../../components/ui'
import { ACTION_LABELS, fieldLabel, orderedChanges, showValue } from '../../lib/fishFields'
import { timeAgo } from '../../lib/time'
import { useAdminData } from './AdminLayout'

type Changes = Record<string, { from: unknown; to: unknown }>

function EventDetails({ event }: { event: AuditEvent }) {
  const details = event.details ?? {}
  const changes = details.changes as Changes | undefined
  return (
    <div className="mt-1 space-y-0.5 text-sm">
      {event.action === 'user.role' && (
        <p>
          {String(details.username)}: {String(details.from)} → <strong className="font-medium">{String(details.to)}</strong>
        </p>
      )}
      {event.action === 'fish.import' && (
        <p className="text-muted">
          {String(details.changed)} of {String(details.rows)} rows changed a fish
        </p>
      )}
      {details.via === 'import' && <p className="text-xs text-muted">from a spreadsheet import</p>}
      {typeof details.picture === 'object' && details.picture !== null && (
        <p className="text-muted">{String((details.picture as { credit?: string }).credit ?? '')}</p>
      )}
      {details.suggested_by !== undefined && <p className="text-xs text-muted">suggested by {String(details.suggested_by ?? 'a removed user')}</p>}
      {changes &&
        orderedChanges(changes).map(([field, change]) => (
          <p key={field}>
            <span className="text-muted">{fieldLabel(field)}:</span> {showValue(change.from)} →{' '}
            <strong className="font-medium">{showValue(change.to)}</strong>
          </p>
        ))}
    </div>
  )
}

// Every change admins made, newest first, or only the changes to one fish
export function ActivityList({ fishId, compact = false }: { fishId?: number; compact?: boolean }) {
  const { fish } = useAdminData()
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [more, setMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(
    (before?: number) => {
      setLoading(true)
      api
        .listAudit({ fishId, before })
        .then((answer) => {
          setEvents((current) => (before === undefined ? answer.events : [...current, ...answer.events]))
          setMore(answer.more)
          setError(null)
        })
        .catch((reason: Error) => setError(reason.message))
        .finally(() => setLoading(false))
    },
    [fishId],
  )
  useEffect(() => load(), [load])

  const fishName = (id: number | null) => {
    const entry = id === null ? undefined : fish.find((candidate) => candidate.id === id)
    return entry ? (entry.common_name ?? entry.scientific_name) : id !== null ? `fish #${id}` : null
  }

  if (error) return <ErrorNotice message={error} onRetry={() => load()} />
  if (loading && events.length === 0) return <LoadingBlock />
  if (events.length === 0) {
    return compact ? <p className="text-sm text-muted">No changes recorded yet.</p> : <EmptyState title="No changes recorded yet" />
  }
  return (
    <div>
      <ol className="divide-y divide-line">
        {events.map((event) => (
          <li key={event.id} className="py-3">
            <p className="text-sm">
              <strong className="font-medium">{event.username ?? 'Command line'}</strong> {ACTION_LABELS[event.action] ?? event.action}
              {!compact && event.fish_id !== null && (
                <>
                  {' '}
                  {event.action === 'fish.delete' ? (
                    <span>{String(event.details?.scientific_name ?? fishName(event.fish_id))}</span>
                  ) : (
                    <Link to={`/admin/fish/${event.fish_id}`} className="text-brand hover:underline">
                      {fishName(event.fish_id)}
                    </Link>
                  )}
                </>
              )}
              <span className="text-muted"> · {timeAgo(event.created_at)}</span>
            </p>
            <EventDetails event={event} />
          </li>
        ))}
      </ol>
      {more && (
        <div className="mt-3">
          <Button variant="secondary" size="sm" busy={loading} onClick={() => load(events[events.length - 1]!.id)}>
            Show older
          </Button>
        </div>
      )}
    </div>
  )
}

export function AdminActivity() {
  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-6">
        <h1 className="font-display text-3xl">Activity</h1>
        <p className="mt-1 text-sm text-muted">Every change admins made to fish and roles, with what changed, newest first.</p>
      </header>
      <section className="rounded-2xl border border-line bg-surface px-5 py-2">
        <ActivityList />
      </section>
    </div>
  )
}
