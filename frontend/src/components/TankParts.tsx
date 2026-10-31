import { useDraggable, useDroppable } from '@dnd-kit/core'
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'

import type { Fish, Fishtank, Suggestions, TankSize } from '../api/types'
import { alarmTitle, displayName, formatRange, waterConditions } from '../lib/fish'
import { timeLeft } from '../lib/time'
import { tankTitle } from '../lib/useMyTanks'
import { FishArt } from './FishArt'
import { TemperamentBadge } from './FishBadges'
import { EMPTY_FILTER, FishFilters, filterFish, type FishFilter } from './FishFilters'
import { Badge, Button, Modal, RangeBar, Spinner, TextField, inputClasses } from './ui'

const PICKER_PAGE = 60

export interface Resident {
  fish: Fish
  count: number
}

// --- the fish picker ---

function PickerRow({
  fish,
  reason,
  busy,
  onAdd,
  onOpen,
}: {
  fish: Fish
  reason: string | undefined
  busy: boolean
  onAdd: (fish: Fish) => void
  onOpen: (fish: Fish) => void
}) {
  const blocked = reason !== undefined
  const { setNodeRef, listeners, attributes, isDragging } = useDraggable({
    id: `pick-${fish.id}`,
    data: { fishId: fish.id, from: 'picker' },
    disabled: blocked,
  })
  return (
    <li
      ref={setNodeRef}
      className={`flex items-center gap-3 rounded-xl px-2 py-2 ${blocked ? 'opacity-55' : 'hover:bg-surface-2'} ${isDragging ? 'opacity-30' : ''}`}
    >
      <button
        type="button"
        {...listeners}
        {...attributes}
        aria-label={blocked ? `${displayName(fish)} cannot join` : `Drag ${displayName(fish)} into the tank`}
        className={`flex h-10 w-14 shrink-0 items-center justify-center rounded-lg bg-surface-2 ${blocked ? 'cursor-not-allowed' : 'cursor-grab touch-none active:cursor-grabbing'}`}
      >
        <FishArt fish={fish} className="w-11" />
      </button>
      <button type="button" onClick={() => onOpen(fish)} className="min-w-0 flex-1 text-left">
        <span className="block truncate text-sm font-medium">{displayName(fish)}</span>
        {blocked ? (
          <span className="block truncate text-xs text-danger" title={reason}>
            {alarmTitle(reason, fish)}
          </span>
        ) : (
          <span className="block truncate text-xs text-muted">
            {fish.minimum_temperature}–{fish.maximum_temperature} °C · pH {fish.minimum_ph}–{fish.maximum_ph}
          </span>
        )}
      </button>
      <button
        type="button"
        onClick={() => onAdd(fish)}
        disabled={blocked || busy}
        title={blocked ? reason : `Add one ${displayName(fish)}`}
        aria-label={`Add one ${displayName(fish)}`}
        className="flex size-8 shrink-0 items-center justify-center rounded-full border border-line text-lg leading-none text-brand hover:border-brand hover:bg-brand-soft disabled:cursor-not-allowed disabled:text-muted disabled:hover:border-line disabled:hover:bg-transparent"
      >
        +
      </button>
    </li>
  )
}

export function FishPicker({
  fish,
  incompatible,
  checking,
  busy,
  canDrag,
  onAdd,
  onOpen,
}: {
  fish: Fish[]
  // fish id to the reason it cannot join, from the api
  incompatible: Map<number, string>
  checking: boolean
  busy: boolean
  // on phones fish are added with +, the tank is not in view while picking
  canDrag: boolean
  onAdd: (fish: Fish) => void
  onOpen: (fish: Fish) => void
}) {
  const [filter, setFilter] = useState<FishFilter>(EMPTY_FILTER)
  const [hideBlocked, setHideBlocked] = useState(false)
  const [shown, setShown] = useState(PICKER_PAGE)
  // dropping a fish from the tank here takes one out
  const { setNodeRef, isOver } = useDroppable({ id: 'picker' })

  const results = useMemo(() => {
    const matching = filterFish(fish, filter).filter((entry) => !hideBlocked || !incompatible.has(entry.id))
    // the fish that can join come first
    return matching.sort(
      (a, b) => Number(incompatible.has(a.id)) - Number(incompatible.has(b.id)) || displayName(a).localeCompare(displayName(b)),
    )
  }, [fish, filter, hideBlocked, incompatible])

  useEffect(() => setShown(PICKER_PAGE), [filter, hideBlocked])
  const blockedCount = fish.filter((entry) => incompatible.has(entry.id)).length

  return (
    <div ref={setNodeRef} className={`flex h-full flex-col rounded-2xl transition-colors ${isOver ? 'bg-danger-soft' : ''}`}>
      <div className="space-y-3 pb-3">
        <FishFilters fish={fish} filter={filter} onChange={setFilter} compact />
        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={hideBlocked}
            onChange={(event) => setHideBlocked(event.target.checked)}
            className="size-4 accent-[var(--color-brand)]"
          />
          Hide fish that cannot join{blockedCount > 0 && ` (${blockedCount.toLocaleString()})`}
          {checking && <span className="text-xs">· checking…</span>}
        </label>
      </div>
      <p className="mb-1 text-xs text-muted">{results.length.toLocaleString()} fish · {canDrag ? 'drag one into the tank or press +' : 'press + to add one'}</p>
      <ul className="-mx-2 flex-1 space-y-0.5 overflow-y-auto pr-1">
        {results.slice(0, shown).map((entry) => (
          <PickerRow key={entry.id} fish={entry} reason={incompatible.get(entry.id)} busy={busy} onAdd={onAdd} onOpen={onOpen} />
        ))}
        {shown < results.length && (
          <li className="py-3 text-center">
            <Button variant="ghost" size="sm" onClick={() => setShown(shown + PICKER_PAGE)}>
              Show more
            </Button>
          </li>
        )}
      </ul>
    </div>
  )
}

// --- the fish in the tank ---

function CountStepper({ resident, busy, onChange }: { resident: Resident; busy: boolean; onChange: (count: number) => void }) {
  const [draft, setDraft] = useState(String(resident.count))
  useEffect(() => setDraft(String(resident.count)), [resident.count])

  // typing a number changes the tank in one go, all of the new fish are checked together
  const commit = () => {
    const count = Math.round(Number(draft))
    if (!Number.isFinite(count) || count < 0 || count === resident.count) setDraft(String(resident.count))
    else onChange(Math.min(count, 500))
  }

  return (
    <div className="flex items-center rounded-full border border-line">
      <button
        type="button"
        onClick={() => onChange(resident.count - 1)}
        disabled={busy}
        aria-label={`One ${displayName(resident.fish)} less`}
        className="size-8 rounded-l-full text-lg leading-none hover:bg-surface-2 disabled:opacity-50"
      >
        −
      </button>
      <input
        value={draft}
        inputMode="numeric"
        onChange={(event) => setDraft(event.target.value.replace(/\D/g, ''))}
        onBlur={commit}
        onKeyDown={(event) => event.key === 'Enter' && (event.target as HTMLInputElement).blur()}
        aria-label={`Number of ${displayName(resident.fish)}`}
        className="h-8 w-10 bg-transparent text-center text-sm tabular-nums focus:outline-none"
      />
      <button
        type="button"
        onClick={() => onChange(resident.count + 1)}
        disabled={busy || resident.fish.retired}
        aria-label={`One more ${displayName(resident.fish)}`}
        className="size-8 rounded-r-full text-lg leading-none hover:bg-surface-2 disabled:opacity-50"
      >
        +
      </button>
    </div>
  )
}

function ResidentRow({
  resident,
  busy,
  onCount,
  onOpen,
}: {
  resident: Resident
  busy: boolean
  onCount: (fish: Fish, count: number) => void
  onOpen: (fish: Fish) => void
}) {
  const { setNodeRef, listeners, attributes, isDragging } = useDraggable({
    id: `resident-${resident.fish.id}`,
    data: { fishId: resident.fish.id, from: 'tank' },
  })
  return (
    <li ref={setNodeRef} className={`flex items-center gap-3 py-2.5 ${isDragging ? 'opacity-30' : ''}`}>
      <button
        type="button"
        {...listeners}
        {...attributes}
        aria-label={`Drag ${displayName(resident.fish)} out of the tank`}
        className="flex h-10 w-14 shrink-0 cursor-grab touch-none items-center justify-center rounded-lg bg-surface-2 active:cursor-grabbing"
      >
        <FishArt fish={resident.fish} className="w-11" />
      </button>
      <button type="button" onClick={() => onOpen(resident.fish)} className="min-w-0 flex-1 text-left">
        <span className="block truncate text-sm font-medium">{displayName(resident.fish)}</span>
        <span className="flex gap-1.5 pt-0.5">
          <TemperamentBadge fish={resident.fish} />
          {resident.fish.retired && <Badge>Retired</Badge>}
        </span>
      </button>
      <CountStepper resident={resident} busy={busy} onChange={(count) => onCount(resident.fish, count)} />
      <button
        type="button"
        onClick={() => onCount(resident.fish, 0)}
        disabled={busy}
        aria-label={`Take every ${displayName(resident.fish)} out`}
        title="Take them all out"
        className="size-8 shrink-0 rounded-full text-lg leading-none text-muted hover:bg-danger-soft hover:text-danger disabled:opacity-50"
      >
        ×
      </button>
    </li>
  )
}

export function ResidentList({
  residents,
  busy,
  onCount,
  onOpen,
}: {
  residents: Resident[]
  busy: boolean
  onCount: (fish: Fish, count: number) => void
  onOpen: (fish: Fish) => void
}) {
  const total = residents.reduce((sum, resident) => sum + resident.count, 0)
  return (
    <section className="rounded-2xl border border-line bg-surface p-5">
      <div className="mb-1 flex items-baseline justify-between">
        <h2 className="font-display text-lg">In this tank</h2>
        <span className="text-sm text-muted">
          {residents.length} species · {total} fish
        </span>
      </div>
      {residents.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">Empty for now. Pick a fish and drag it into the water.</p>
      ) : (
        <ul className="divide-y divide-line">
          {residents.map((resident) => (
            <ResidentRow key={resident.fish.id} resident={resident} busy={busy} onCount={onCount} onOpen={onOpen} />
          ))}
        </ul>
      )}
    </section>
  )
}

// --- the water every fish is happy in ---

function Condition({ label, value, low, high, scale, icon }: { label: string; value: string; low: number; high: number; scale: [number, number]; icon: ReactNode }) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-2 text-sm text-muted">
          <span aria-hidden>{icon}</span>
          {label}
        </span>
        <span className="font-display text-xl tabular-nums">{value}</span>
      </div>
      <RangeBar min={low} max={high} scale={scale} highlight={[low, high]} />
    </div>
  )
}

export function WaterPanel({ residents }: { residents: Resident[] }) {
  const water = waterConditions(residents.map((resident) => resident.fish))
  return (
    <section className="rounded-2xl border border-line bg-surface p-5">
      <h2 className="font-display text-lg">Water to keep</h2>
      {water === null ? (
        <p className="mt-3 text-sm text-muted">Add fish to see the water they all need.</p>
      ) : (
        <>
          <p className="mt-1 mb-5 text-sm text-muted">What every fish in this tank is happy with.</p>
          <div className="space-y-5">
            <Condition label="Temperature" icon="🌡" value={formatRange(water.temperature, ' °C')} low={water.temperature.min} high={water.temperature.max} scale={[10, 40]} />
            <Condition label="pH" icon="⚗" value={formatRange(water.ph, '', 1)} low={water.ph.min} high={water.ph.max} scale={[4, 10]} />
            <Condition label="Hardness" icon="◈" value={formatRange(water.hardness, ' dGH')} low={water.hardness.min} high={water.hardness.max} scale={[0, 40]} />
          </div>
        </>
      )}
    </section>
  )
}

// --- the companions that can all join together ---

function CompanionRow({ fish, busy, onAdd, onOpen }: { fish: Fish; busy: boolean; onAdd: (fish: Fish) => void; onOpen: (fish: Fish) => void }) {
  return (
    <li className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-surface-2">
      <button type="button" onClick={() => onOpen(fish)} className="flex min-w-0 flex-1 items-center gap-3 text-left">
        <span className="flex h-10 w-14 shrink-0 items-center justify-center rounded-lg bg-surface-2">
          <FishArt fish={fish} className="w-11" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{displayName(fish)}</span>
          <span className="block truncate text-xs text-muted">
            {fish.minimum_temperature}–{fish.maximum_temperature} °C · pH {fish.minimum_ph}–{fish.maximum_ph}
          </span>
        </span>
      </button>
      <button
        type="button"
        onClick={() => onAdd(fish)}
        disabled={busy}
        title={`Add one ${displayName(fish)}`}
        aria-label={`Add one ${displayName(fish)}`}
        className="flex size-8 shrink-0 items-center justify-center rounded-full border border-line text-lg leading-none text-brand hover:border-brand hover:bg-brand-soft disabled:cursor-not-allowed disabled:text-muted disabled:hover:border-line disabled:hover:bg-transparent"
      >
        +
      </button>
    </li>
  )
}

export function CompanionPanel({
  suggestions,
  byId,
  checking,
  busy,
  expanded,
  onExpand,
  onAdd,
  onAddAll,
  onOpen,
}: {
  suggestions: Suggestions | null
  byId: Map<number, Fish>
  checking: boolean
  busy: boolean
  // a few suggestions, or as many as the api answers
  expanded: boolean
  onExpand: (expanded: boolean) => void
  onAdd: (fish: Fish) => void
  onAddAll: (fish: Fish[]) => void
  onOpen: (fish: Fish) => void
}) {
  const shown = (suggestions?.suggestions ?? []).flatMap((id) => {
    const fish = byId.get(id)
    return fish ? [fish] : []
  })
  const groupSize = suggestions?.group_size ?? 0
  // an answer for a tank that has changed since may no longer hold, it is not added from
  const disabled = busy || checking

  return (
    <section className="rounded-2xl border border-line bg-surface p-5">
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <h2 className="font-display text-lg">Suggested companions</h2>
        {checking && (
          <span className="flex items-center gap-1.5 text-xs text-muted" role="status">
            <Spinner small /> finding…
          </span>
        )}
      </div>
      {suggestions === null ? (
        <p className="py-4 text-sm text-muted">{checking ? 'Looking for the largest group that gets along…' : 'No suggestions right now.'}</p>
      ) : groupSize === 0 ? (
        <p className="py-4 text-sm text-muted">No new species can live with everyone in this tank.</p>
      ) : (
        <>
          <p className="mb-3 text-sm text-muted">
            {groupSize.toLocaleString()} new {groupSize === 1 ? 'species gets' : 'species get'} along with the tank and each other. Add any of
            them, in any order.
          </p>
          <ul className={`-mx-2 space-y-0.5 transition-opacity ${checking ? 'opacity-60' : ''}`}>
            {shown.map((fish) => (
              <CompanionRow key={fish.id} fish={fish} busy={disabled} onAdd={onAdd} onOpen={onOpen} />
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {shown.length > 1 && (
              <Button size="sm" onClick={() => onAddAll(shown)} disabled={disabled}>
                Add all {shown.length}
              </Button>
            )}
            {groupSize > shown.length && !expanded && (
              <Button variant="ghost" size="sm" onClick={() => onExpand(true)}>
                See more
              </Button>
            )}
            {expanded && (
              <Button variant="ghost" size="sm" onClick={() => onExpand(false)}>
                See fewer
              </Button>
            )}
            {groupSize > shown.length && (
              <span className="ml-auto text-xs text-muted">
                {shown.length} of {groupSize.toLocaleString()}
              </span>
            )}
          </div>
          {!suggestions.complete && (
            <p className="mt-3 text-xs text-muted">The search stopped early, a larger group may exist.</p>
          )}
        </>
      )}
    </section>
  )
}

// --- name, size and what happens to the tank ---

export function TankName({ tank, onRename }: { tank: Fishtank; onRename: (name: string | null) => Promise<void> }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(tank.name ?? '')
  useEffect(() => setDraft(tank.name ?? ''), [tank.name])

  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    setEditing(false)
    const name = draft.trim() || null
    if (name !== tank.name) await onRename(name)
  }

  if (editing) {
    return (
      <form onSubmit={submit} className="min-w-0 flex-1">
        <input
          autoFocus
          value={draft}
          maxLength={100}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => submit()}
          onKeyDown={(event) => event.key === 'Escape' && (setDraft(tank.name ?? ''), setEditing(false))}
          aria-label="Tank name"
          placeholder="Name your tank"
          className={`${inputClasses} h-12 font-display text-2xl`}
        />
      </form>
    )
  }
  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      title="Rename"
      className="group flex min-w-0 items-center gap-2 rounded-lg text-left"
    >
      <h1 className={`truncate font-display text-3xl ${tank.name ? '' : 'text-muted'}`}>{tankTitle(tank)}</h1>
      <span aria-hidden className="text-muted opacity-0 transition group-hover:opacity-100">
        ✎
      </span>
    </button>
  )
}

export function SizeDialog({ size, onClose, onSave }: { size: TankSize; onClose: () => void; onSave: (size: TankSize) => Promise<void> }) {
  const [draft, setDraft] = useState({ length: String(size.length), width: String(size.width), height: String(size.height) })
  const [busy, setBusy] = useState(false)
  const values = { length: Number(draft.length), width: Number(draft.width), height: Number(draft.height) }
  const valid = Object.values(values).every((value) => Number.isInteger(value) && value > 0 && value <= 10000)
  const litres = valid ? Math.round((values.length * values.width * values.height) / 1000) : null

  return (
    <Modal open onClose={onClose} title="Tank size">
      <form
        onSubmit={async (event) => {
          event.preventDefault()
          if (!valid) return
          setBusy(true)
          await onSave(values)
          setBusy(false)
          onClose()
        }}
      >
        <div className="grid grid-cols-3 gap-3">
          {(['length', 'width', 'height'] as const).map((dimension) => (
            <TextField
              key={dimension}
              label={`${dimension[0]!.toUpperCase()}${dimension.slice(1)} (cm)`}
              inputMode="numeric"
              value={draft[dimension]}
              onChange={(event) => setDraft({ ...draft, [dimension]: event.target.value.replace(/\D/g, '') })}
            />
          ))}
        </div>
        <p className="mt-3 text-sm text-muted">
          {litres !== null ? `About ${litres.toLocaleString()} litres.` : 'Each side is a whole number of centimetres, up to 10,000.'} The size
          is for your reference, the simulation does not limit how many fish fit.
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" busy={busy} disabled={!valid}>
            Save size
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function VisitorBanner({ tank, loggedIn, onSignUp, onSave }: { tank: Fishtank; loggedIn: boolean; onSignUp: () => void; onSave: () => void }) {
  if (tank.saved || !tank.expires_at) return null
  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-brand-soft px-5 py-4 text-sm text-brand-strong sm:flex-row sm:items-center sm:justify-between">
      <p>
        This tank is kept for <strong>{timeLeft(tank.expires_at)}</strong> after your last change.{' '}
        {loggedIn ? 'Save it to keep it for good.' : 'Sign up to keep it for good.'}
      </p>
      <Button size="sm" onClick={loggedIn ? onSave : onSignUp} className="shrink-0">
        {loggedIn ? 'Save to my tanks' : 'Sign up to keep it'}
      </Button>
    </div>
  )
}
