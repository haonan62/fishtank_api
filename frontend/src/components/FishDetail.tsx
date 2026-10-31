import { useEffect, useState, type ReactNode } from 'react'

import type { Fish } from '../api/types'
import { IN_SPECIES_TEXT, crossSpeciesSummary, displayName, isSoloOnly, tankLevel } from '../lib/fish'
import { AddToTank } from './AddToTank'
import { FishImage } from './FishArt'
import { TemperamentBadge } from './FishBadges'
import { Badge, RangeBar } from './ui'

// scales wide enough for every fish in the catalogue, so two fish can be compared by eye
const SCALES = { temperature: [10, 40], ph: [4, 10], hardness: [0, 40] } as const

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line py-2 text-sm last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right">{children ?? <span className="text-muted">Not known</span>}</dd>
    </div>
  )
}

function WaterRow({ label, min, max, unit, scale }: { label: string; min: number; max: number; unit: string; scale: readonly [number, number] }) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className="font-medium tabular-nums">
          {min}–{max}
          {unit}
        </span>
      </div>
      <RangeBar min={min} max={max} scale={[scale[0], scale[1]]} />
    </div>
  )
}

export function FishDetail({ fish, actions = true }: { fish: Fish; actions?: boolean }) {
  const [pictureIndex, setPictureIndex] = useState(0)
  useEffect(() => setPictureIndex(0), [fish.id])
  const picture = fish.pictures[pictureIndex]
  const level = tankLevel(fish)

  return (
    <article className="space-y-6">
      <div>
        {picture ? (
          <figure>
            <div className="overflow-hidden rounded-2xl bg-surface-2">
              <img src={picture.url} alt={`${displayName(fish)}, ${picture.credit}`} className="aspect-[4/3] w-full object-cover" />
            </div>
            <figcaption className="mt-2 text-xs text-muted">
              Photo: {picture.credit} ·{' '}
              <a href={picture.source_url} target="_blank" rel="noreferrer" className="underline hover:text-ink">
                source
              </a>{' '}
              · {picture.licence}
            </figcaption>
            {fish.pictures.length > 1 && (
              <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                {fish.pictures.map((entry, index) => (
                  <button
                    key={entry.url}
                    type="button"
                    onClick={() => setPictureIndex(index)}
                    aria-label={`Photo ${index + 1}`}
                    aria-pressed={index === pictureIndex}
                    className={`h-14 w-20 shrink-0 overflow-hidden rounded-lg border-2 ${index === pictureIndex ? 'border-brand' : 'border-transparent opacity-70 hover:opacity-100'}`}
                  >
                    <img src={entry.url} alt="" loading="lazy" className="size-full object-cover" />
                  </button>
                ))}
              </div>
            )}
          </figure>
        ) : (
          <FishImage fish={fish} className="aspect-[4/3] w-full rounded-2xl" />
        )}
      </div>

      <header className="space-y-2">
        <div className="flex flex-wrap gap-1.5">
          <TemperamentBadge fish={fish} />
          {fish.retired && <Badge tone="neutral">Retired</Badge>}
          <Badge>{fish.family_name}</Badge>
        </div>
        <h2 className="font-display text-3xl leading-tight">{displayName(fish)}</h2>
        {fish.common_name && <p className="text-muted italic">{fish.scientific_name}</p>}
      </header>

      {isSoloOnly(fish) && (
        <p className="rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
          Its temperament is not known yet, so it can only be kept alone: one fish in a tank.
        </p>
      )}

      <section className="space-y-2">
        <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">Behaviour</h3>
        <ul className="space-y-1 text-sm">
          <li>{crossSpeciesSummary(fish)}</li>
          <li>{IN_SPECIES_TEXT[fish.in_species_temperament]}</li>
          <li>Swims in the {level} of the tank</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">Water it needs</h3>
        <WaterRow label="Temperature" min={fish.minimum_temperature} max={fish.maximum_temperature} unit=" °C" scale={SCALES.temperature} />
        <WaterRow label="pH" min={fish.minimum_ph} max={fish.maximum_ph} unit="" scale={SCALES.ph} />
        <WaterRow label="Hardness" min={fish.minimum_water_hardness} max={fish.maximum_water_hardness} unit=" dGH" scale={SCALES.hardness} />
      </section>

      <dl>
        <Row label="Size">{fish.minimum_size !== null ? `${fish.minimum_size}–${fish.maximum_size} cm` : null}</Row>
        <Row label="Origin">{fish.origin}</Row>
        <Row label="Breeding">{fish.reproduce_method}</Row>
        <Row label="Data from">
          {fish.fishbase_url ? (
            <a href={fish.fishbase_url} target="_blank" rel="noreferrer" className="text-brand hover:underline">
              {fish.data_source} ↗
            </a>
          ) : (
            fish.data_source
          )}
        </Row>
      </dl>

      {actions && !fish.retired && <AddToTank fish={fish} full />}
      {fish.retired && <p className="text-sm text-muted">This fish is no longer in the catalogue and cannot be added to tanks.</p>}
    </article>
  )
}

// The detail as a panel sliding in from the right, over the page it was opened from
export function FishPanel({ fish, onClose }: { fish: Fish | null; onClose: () => void }) {
  useEffect(() => {
    if (!fish) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [fish, onClose])

  if (!fish) return null
  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-ink/30" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={displayName(fish)}
        className="animate-rise-in h-full w-full max-w-lg overflow-y-auto bg-surface p-6 shadow-[var(--shadow-pop)]"
      >
        <div className="mb-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            autoFocus
            className="size-9 rounded-lg text-2xl leading-none text-muted hover:bg-surface-2 hover:text-ink"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <FishDetail fish={fish} />
      </aside>
    </div>
  )
}
