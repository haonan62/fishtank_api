import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'

import type { Fish } from '../api/types'
import { displayName, tankLevel, type TankLevel } from '../lib/fish'
import { FishArt } from './FishArt'

export interface AquariumEntry {
  fish: Fish
  count: number
}

// where each level swims, as a share of the water's height
const LEVEL_BANDS: Record<TankLevel, [number, number]> = {
  top: [0.08, 0.3],
  middle: [0.34, 0.58],
  bottom: [0.62, 0.8],
}
// a tank of hundreds of fish would be a blur, a few of each species give the picture
const MAX_DRAWN_PER_SPECIES = 4

// a stable pseudo random number per fish, so the fish keep their place when the tank changes
function seeded(seed: number) {
  const value = Math.sin(seed * 9301 + 49297) * 233280
  return value - Math.floor(value)
}

export function Aquarium({
  entries,
  className = '',
  decorative = false,
  overlay,
}: {
  entries: AquariumEntry[]
  className?: string
  decorative?: boolean
  overlay?: ReactNode
}) {
  const water = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(600)

  useEffect(() => {
    if (!water.current) return
    const observer = new ResizeObserver(([entry]) => entry && setWidth(entry.contentRect.width))
    observer.observe(water.current)
    return () => observer.disconnect()
  }, [])

  const drawn = entries.flatMap(({ fish, count }) =>
    Array.from({ length: Math.min(count, MAX_DRAWN_PER_SPECIES) }, (_, index) => ({ fish, index })),
  )
  const fishWidth = Math.max(44, Math.min(72, width / 9))

  return (
    <div
      ref={water}
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative || undefined}
      aria-label={
        decorative
          ? undefined
          : entries.length
            ? `A tank with ${entries.map((entry) => `${entry.count} ${displayName(entry.fish)}`).join(', ')}`
            : 'An empty tank'
      }
      className={`relative overflow-hidden rounded-3xl border border-white/40 shadow-[var(--shadow-card)] ${className}`}
      style={{ background: 'linear-gradient(180deg, var(--color-water-top) 0%, var(--color-water-bottom) 100%)' }}
    >
      {/* light from above */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_30%_-10%,rgba(255,255,255,0.45),transparent_55%)]" />
      {/* plants */}
      <svg className="pointer-events-none absolute bottom-[10%] left-[6%] h-[45%] text-[hsl(150_40%_35%)] opacity-80" viewBox="0 0 40 120" aria-hidden>
        <path d="M20 120 C10 90 30 70 18 40 C12 25 22 10 20 0" stroke="currentColor" strokeWidth="5" fill="none" strokeLinecap="round" />
        <path d="M22 120 C30 95 14 80 28 55" stroke="currentColor" strokeWidth="4" fill="none" strokeLinecap="round" />
      </svg>
      <svg className="pointer-events-none absolute right-[8%] bottom-[10%] h-[35%] text-[hsl(140_35%_40%)] opacity-75" viewBox="0 0 40 120" aria-hidden>
        <path d="M14 120 C4 90 24 64 12 30 M24 120 C34 92 20 70 32 44" stroke="currentColor" strokeWidth="5" fill="none" strokeLinecap="round" />
      </svg>
      {/* sand */}
      <div className="absolute inset-x-0 bottom-0 h-[12%] rounded-b-3xl bg-sand" style={{ boxShadow: 'inset 0 6px 12px rgb(0 0 0 / 0.08)' }} />
      {/* bubbles */}
      {[0.15, 0.55, 0.82].map((left, index) => (
        <span
          key={left}
          className="animate-bubble absolute bottom-[12%] size-2 rounded-full border border-white/70 bg-white/20"
          style={{ left: `${left * 100}%`, '--bubble-delay': `${index * 2.3}s`, '--bubble-duration': `${6 + index}s` } as CSSProperties}
        />
      ))}

      {drawn.map(({ fish, index }) => {
        const seed = fish.id * 7 + index
        const [top, bottom] = LEVEL_BANDS[tankLevel(fish)]
        const distance = Math.max(80, width * (0.25 + seeded(seed + 1) * 0.35))
        const left = seeded(seed + 2) * Math.max(0, width - distance - fishWidth)
        const style = {
          top: `${(top + seeded(seed) * (bottom - top)) * 100}%`,
          left,
          width: fishWidth,
          '--swim-distance': `${distance}px`,
          '--swim-duration': `${10 + seeded(seed + 3) * 10}s`,
          '--swim-delay': `${-seeded(seed + 4) * 12}s`,
        } as CSSProperties
        return (
          <div key={`${fish.id}-${index}`} className="animate-swim absolute" style={style} title={decorative ? undefined : displayName(fish)}>
            {/* the drawing looks left, swimming starts to the right */}
            <div className="animate-bob -scale-x-100">
              <FishArt fish={fish} className="w-full drop-shadow-[0_2px_2px_rgba(0,0,0,0.15)]" />
            </div>
          </div>
        )
      })}
      {overlay}
    </div>
  )
}
