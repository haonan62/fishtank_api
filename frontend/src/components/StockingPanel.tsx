import type { Fish, Fishtank, StockingLevel, TankWarning } from '../api/types'
import { displayName } from '../lib/fish'
import { Button } from './ui'

const LEVELS: Record<StockingLevel, { label: string; bar: string; text: string }> = {
  empty: { label: 'Empty', bar: 'bg-ok', text: 'text-muted' },
  comfortable: { label: 'Comfortable', bar: 'bg-ok', text: 'text-ok' },
  'nearly full': { label: 'Nearly full', bar: 'bg-warn', text: 'text-warn' },
  overstocked: { label: 'Overstocked', bar: 'bg-danger', text: 'text-danger' },
}

// the bar runs to 125%, so an overstocked tank shows how far over it is
const BAR_MAX_SHARE = 1.25

const ICONS: Record<TankWarning['kind'], string> = { overstocked: '!', group: '⋯', room: '↔' }

function WarningRow({
  warning,
  fish,
  busy,
  onAddFish,
  onResize,
}: {
  warning: TankWarning
  fish: Fish | undefined
  busy: boolean
  onAddFish?: (fish: Fish, count: number) => void
  onResize?: () => void
}) {
  const missing = warning.kind === 'group' ? warning.minimum - warning.count : 0
  return (
    <li className="flex gap-3 py-3">
      <span
        aria-hidden
        className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
          warning.kind === 'overstocked' ? 'bg-danger-soft text-danger' : 'bg-warn-soft text-warn'
        }`}
      >
        {ICONS[warning.kind]}
      </span>
      <div className="min-w-0 flex-1 text-sm">
        {warning.kind === 'group' && fish ? (
          <p>
            <strong className="font-medium">{displayName(fish)}</strong> is a schooling fish. Keep at least {warning.minimum} together,
            this tank has {warning.count}.
          </p>
        ) : warning.kind === 'room' && fish ? (
          <p>
            <strong className="font-medium">{displayName(fish)}</strong> grows to {fish.maximum_size} cm and needs a tank at least{' '}
            {warning.minimum_length} cm long to swim.
          </p>
        ) : warning.kind === 'overstocked' ? (
          <p>Too many fish for this much water. Take some out or choose a bigger tank.</p>
        ) : (
          <p>{warning.message}</p>
        )}
        {warning.kind === 'group' && fish && !fish.retired && onAddFish && (
          <Button variant="secondary" size="sm" className="mt-2" disabled={busy} onClick={() => onAddFish(fish, missing)}>
            Add {missing} more
          </Button>
        )}
        {(warning.kind === 'room' || warning.kind === 'overstocked') && onResize && (
          <Button variant="secondary" size="sm" className="mt-2" onClick={onResize}>
            Change tank size
          </Button>
        )}
      </div>
    </li>
  )
}

// How full the tank is and what its fish would miss, as advice: nothing here stops a fish from being added
// Without onAddFish and onResize it only shows the advice, e.g. on a shared tank
export function StockingPanel({
  tank,
  byId,
  busy = false,
  onAddFish,
  onResize,
}: {
  tank: Pick<Fishtank, 'stocking' | 'warnings'>
  byId: Map<number, Fish>
  busy?: boolean
  onAddFish?: (fish: Fish, count: number) => void
  onResize?: () => void
}) {
  const { stocking, warnings } = tank
  const level = LEVELS[stocking.level]
  const percent = Math.round(stocking.share * 100)
  const width = `${Math.min(stocking.share, BAR_MAX_SHARE) / BAR_MAX_SHARE * 100}%`

  return (
    <section className="rounded-2xl border border-line bg-surface p-5" aria-labelledby="stocking-title">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="stocking-title" className="font-display text-lg">
          Stocking
        </h2>
        <span className={`text-sm font-medium ${level.text}`}>
          {level.label}
          {stocking.level !== 'empty' && ` · ${percent}%`}
        </span>
      </div>

      <div
        className="relative mt-4 h-2.5 rounded-full bg-surface-2"
        role="meter"
        aria-label="How full the tank is"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(percent, 125)}
        aria-valuetext={`${level.label}, ${percent}% of a comfortable stocking`}
      >
        <div className={`absolute inset-y-0 left-0 rounded-full transition-[width] ${level.bar}`} style={{ width }} />
        {/* the 80% and 100% marks */}
        <span className="absolute -inset-y-1 w-px bg-ink/25" style={{ left: `${(0.8 / BAR_MAX_SHARE) * 100}%` }} aria-hidden />
        <span className="absolute -inset-y-1 w-0.5 bg-ink/50" style={{ left: `${(1 / BAR_MAX_SHARE) * 100}%` }} aria-hidden />
      </div>

      <p className="mt-3 text-sm text-muted">
        {stocking.level === 'empty'
          ? `About ${Math.round(stocking.capacity_cm)} cm of adult fish fit comfortably in ${Math.round(stocking.net_litres)} litres of water.`
          : `${stocking.fish_cm} cm of adult fish, about ${Math.round(stocking.capacity_cm)} cm fit comfortably in ${Math.round(stocking.net_litres)} litres of water.`}
      </p>
      {stocking.uncounted_fish > 0 && (
        <p className="mt-1 text-xs text-muted">
          {stocking.uncounted_fish} fish without a known adult size {stocking.uncounted_fish === 1 ? 'is' : 'are'} not counted.
        </p>
      )}

      {warnings.length > 0 && (
        <ul className="mt-2 divide-y divide-line border-t border-line" aria-label="Advice for this tank">
          {warnings.map((warning) => (
            <WarningRow
              key={`${warning.kind}-${'fish_id' in warning ? warning.fish_id : ''}`}
              warning={warning}
              fish={'fish_id' in warning ? byId.get(warning.fish_id) : undefined}
              busy={busy}
              onAddFish={onAddFish}
              onResize={onResize}
            />
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs leading-relaxed text-muted">
        A rule of thumb: about 1 cm of adult fish per 1.5 litres. Advice only, it never stops you adding a fish.
      </p>
    </section>
  )
}
