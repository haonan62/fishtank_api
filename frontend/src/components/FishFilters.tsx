import { useMemo } from 'react'

import type { Fish } from '../api/types'
import { matchesSearch, tankLevel, temperamentGroup, type TankLevel, type TemperamentGroup } from '../lib/fish'
import { inputClasses } from './ui'

export interface FishFilter {
  search: string
  family: string
  temperament: TemperamentGroup | 'all'
  level: TankLevel | 'all'
  // the water the user keeps, a fish matches when the value lies in its range
  temperature: string
  ph: string
  photoOnly: boolean
}

export const EMPTY_FILTER: FishFilter = {
  search: '',
  family: '',
  temperament: 'all',
  level: 'all',
  temperature: '',
  ph: '',
  photoOnly: false,
}

export function isFiltering(filter: FishFilter) {
  return JSON.stringify(filter) !== JSON.stringify(EMPTY_FILTER)
}

export function filterFish(fish: Fish[], filter: FishFilter) {
  const temperature = filter.temperature === '' ? null : Number(filter.temperature)
  const ph = filter.ph === '' ? null : Number(filter.ph)
  return fish.filter(
    (entry) =>
      matchesSearch(entry, filter.search) &&
      (!filter.family || entry.family_name === filter.family) &&
      (filter.temperament === 'all' || temperamentGroup(entry) === filter.temperament) &&
      (filter.level === 'all' || tankLevel(entry) === filter.level) &&
      (temperature === null || Number.isNaN(temperature) ||
        (entry.minimum_temperature <= temperature && temperature <= entry.maximum_temperature)) &&
      (ph === null || Number.isNaN(ph) || (entry.minimum_ph <= ph && ph <= entry.maximum_ph)) &&
      (!filter.photoOnly || entry.pictures.length > 0),
  )
}

const TEMPERAMENTS: { value: FishFilter['temperament']; label: string }[] = [
  { value: 'all', label: 'Any temperament' },
  { value: 'peaceful', label: 'Peaceful' },
  { value: 'aggressive', label: 'Aggressive' },
  { value: 'solo', label: 'Solo only' },
]

const LEVELS: { value: FishFilter['level']; label: string }[] = [
  { value: 'all', label: 'Any level' },
  { value: 'top', label: 'Top' },
  { value: 'middle', label: 'Middle' },
  { value: 'bottom', label: 'Bottom' },
]

function Chips<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={`h-8 rounded-full px-3 text-sm transition-colors ${
            value === option.value
              ? 'bg-brand text-on-brand'
              : 'border border-line bg-surface text-muted hover:text-ink'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function SearchBox({ value, onChange, placeholder = 'Search by name or family' }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <div className="relative">
      <span aria-hidden className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted">
        ⌕
      </span>
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label="Search fish"
        className={`${inputClasses} pl-8`}
      />
    </div>
  )
}

export function FishFilters({
  fish,
  filter,
  onChange,
  compact = false,
}: {
  fish: Fish[]
  filter: FishFilter
  onChange: (filter: FishFilter) => void
  compact?: boolean
}) {
  const families = useMemo(() => [...new Set(fish.map((entry) => entry.family_name))].sort(), [fish])
  const set = <K extends keyof FishFilter>(key: K, value: FishFilter[K]) => onChange({ ...filter, [key]: value })

  return (
    <div className="space-y-3">
      <SearchBox value={filter.search} onChange={(value) => set('search', value)} />
      <Chips label="Temperament" options={TEMPERAMENTS} value={filter.temperament} onChange={(value) => set('temperament', value)} />
      {!compact && <Chips label="Level in the tank" options={LEVELS} value={filter.level} onChange={(value) => set('level', value)} />}
      <div className="grid grid-cols-2 gap-2">
        <select
          aria-label="Family"
          value={filter.family}
          onChange={(event) => set('family', event.target.value)}
          className={`${inputClasses} col-span-2`}
        >
          <option value="">All {families.length} families</option>
          {families.map((family) => (
            <option key={family} value={family}>
              {family}
            </option>
          ))}
        </select>
        <input
          type="number"
          inputMode="decimal"
          min={0}
          max={45}
          value={filter.temperature}
          onChange={(event) => set('temperature', event.target.value)}
          placeholder="Temp. °C"
          aria-label="Fits water of this temperature, in °C"
          title="Only fish that are happy at this temperature"
          className={inputClasses}
        />
        <input
          type="number"
          inputMode="decimal"
          step={0.1}
          min={0}
          max={14}
          value={filter.ph}
          onChange={(event) => set('ph', event.target.value)}
          placeholder="pH"
          aria-label="Fits water of this pH"
          title="Only fish that are happy at this pH"
          className={inputClasses}
        />
      </div>
      <div className="flex items-center justify-between gap-3 text-sm">
        {!compact ? (
          <label className="flex items-center gap-2 text-muted">
            <input
              type="checkbox"
              checked={filter.photoOnly}
              onChange={(event) => set('photoOnly', event.target.checked)}
              className="size-4 accent-[var(--color-brand)]"
            />
            With a photo only
          </label>
        ) : (
          <span />
        )}
        {isFiltering(filter) && (
          <button type="button" onClick={() => onChange(EMPTY_FILTER)} className="text-brand hover:underline">
            Clear filters
          </button>
        )}
      </div>
    </div>
  )
}
