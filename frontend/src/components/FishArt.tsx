import type { Fish } from '../api/types'
import { displayName, familyHue, tankLevel, type TankLevel } from '../lib/fish'

// Only 201 of the 1040 fish have a photo, every fish gets a drawn likeness: the body follows where it swims
// (slender at the top, round in the middle, flat at the bottom), the colour follows its family
const BODIES: Record<TankLevel, string> = {
  top: 'M6 32 C18 22 38 20 56 26 C62 28 66 30 70 32 C66 34 62 36 56 38 C38 44 18 42 6 32 Z',
  middle: 'M8 32 C14 14 40 10 56 22 C62 26 66 29 70 32 C66 35 62 38 56 42 C40 54 14 50 8 32 Z',
  bottom: 'M6 36 C12 24 34 20 54 26 C62 28 67 31 70 34 C67 37 62 40 54 41 C34 44 14 44 6 36 Z',
}

export function FishArt({ fish, className = '' }: { fish: Pick<Fish, 'family_name' | 'fishtank_position'>; className?: string }) {
  const hue = familyHue(fish.family_name)
  const level = tankLevel(fish)
  const body = `hsl(${hue} 55% 58%)`
  const shade = `hsl(${hue} 50% 42%)`
  const light = `hsl(${hue} 70% 82%)`
  return (
    <svg viewBox="0 0 96 64" className={className} aria-hidden>
      {/* tail */}
      <path d="M68 32 L90 18 C88 26 88 38 90 46 Z" fill={shade} />
      {/* fins */}
      <path d={level === 'bottom' ? 'M30 24 L40 14 L46 25 Z' : 'M28 18 L42 6 L48 20 Z'} fill={shade} opacity="0.85" />
      <path d="M34 44 L42 54 L48 42 Z" fill={shade} opacity="0.75" />
      <path d={BODIES[level]} fill={body} />
      {/* belly and stripe */}
      <path d="M14 36 C26 44 46 44 60 38 C48 48 24 48 14 36 Z" fill={light} opacity="0.7" />
      <path d="M40 18 C44 26 44 38 40 46" stroke={shade} strokeWidth="3" fill="none" opacity="0.35" />
      {level === 'bottom' && <path d="M8 38 C4 42 3 46 2 48 M10 40 C8 44 8 47 8 50" stroke={shade} strokeWidth="1.5" fill="none" />}
      <circle cx="18" cy="29" r="3.6" fill="white" />
      <circle cx="17.2" cy="29" r="2" fill="#12313a" />
    </svg>
  )
}

// The fish's first photo with its credit when it has one, its drawn likeness otherwise
export function FishImage({ fish, className = '', showCredit = false }: { fish: Fish; className?: string; showCredit?: boolean }) {
  const picture = fish.pictures[0]
  const hue = familyHue(fish.family_name)
  return (
    <div
      className={`relative overflow-hidden ${className}`}
      style={{ background: `linear-gradient(160deg, hsl(${hue} 60% 94%), hsl(${(hue + 40) % 360} 45% 86%))` }}
    >
      {picture ? (
        <img
          src={picture.url}
          alt={`${displayName(fish)}, ${picture.credit}`}
          loading="lazy"
          className="size-full object-cover"
        />
      ) : (
        <div className="flex size-full items-center justify-center p-[12%]">
          <FishArt fish={fish} className="w-full max-w-40 drop-shadow-sm" />
        </div>
      )}
      {picture && showCredit && (
        <span className="absolute right-1.5 bottom-1.5 max-w-[90%] truncate rounded bg-black/55 px-1.5 py-0.5 text-[10px] text-white">
          {picture.credit}
        </span>
      )}
    </div>
  )
}
