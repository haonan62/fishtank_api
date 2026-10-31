import { describe, expect, it } from 'vitest'

import type { Fish } from '../api/types'
import { alarmTitle, displayName, formatRange, isSoloOnly, matchesSearch, tankLevel, waterConditions } from './fish'
import { timeAgo, timeLeft } from './time'

function makeFish(overrides: Partial<Fish> = {}): Fish {
  return {
    id: 1,
    scientific_name: 'Corydoras acrensis',
    common_name: 'Acre cory',
    family_name: 'Callichthyidae',
    minimum_size: 4,
    maximum_size: 5,
    minimum_ph: 6,
    maximum_ph: 7.5,
    minimum_water_hardness: 2,
    maximum_water_hardness: 12,
    minimum_temperature: 22,
    maximum_temperature: 26,
    reproduce_method: 'Spawning',
    origin: 'South America',
    in_species_temperament: 'peaceful',
    cross_species_temperament: 'peaceful',
    fishtank_position: 'Bottom levels',
    fishbase_spec_code: null,
    data_source: 'aqua-fish.net',
    fishbase_url: null,
    retired: false,
    pictures: [],
    ...overrides,
  }
}

describe('waterConditions', () => {
  it('is null for an empty tank', () => {
    expect(waterConditions([])).toBeNull()
  })

  it('is the overlap of every fish', () => {
    const water = waterConditions([
      makeFish(),
      makeFish({ minimum_temperature: 24, maximum_temperature: 28, minimum_ph: 6.5, maximum_ph: 8, maximum_water_hardness: 10 }),
    ])
    expect(water).toEqual({
      temperature: { min: 24, max: 26 },
      ph: { min: 6.5, max: 7.5 },
      hardness: { min: 2, max: 10 },
    })
  })
})

describe('fish wording', () => {
  it('falls back to the scientific name', () => {
    expect(displayName(makeFish({ common_name: null }))).toBe('Corydoras acrensis')
  })

  it('knows solo only fish', () => {
    expect(isSoloOnly(makeFish({ cross_species_temperament: 'unknown' }))).toBe(true)
    expect(isSoloOnly(makeFish())).toBe(false)
  })

  it('reads the tank level', () => {
    expect(tankLevel(makeFish({ fishtank_position: 'Top levels' }))).toBe('top')
    expect(tankLevel(makeFish({ fishtank_position: null }))).toBe('middle')
  })

  it('explains the api refusals', () => {
    expect(alarmTitle('Temperature ranges are not common between A and B')).toMatch(/temperatures/)
    expect(alarmTitle('Ph ranges are not common between A and B')).toMatch(/pH/)
    expect(alarmTitle('Cross species competition exists between A and B')).toMatch(/get along/)
    expect(alarmTitle('In species competition exists between two As')).toMatch(/own kind/)
    expect(alarmTitle('In species competition exists between two As', makeFish({ in_species_temperament: 'unknown' }))).toMatch(/alone/)
    expect(alarmTitle('Temperament is not known yet between A and B')).toMatch(/alone/)
  })

  it('formats ranges', () => {
    expect(formatRange({ min: 24, max: 26 }, ' °C')).toBe('24–26 °C')
    expect(formatRange({ min: 7, max: 7 }, '', 1)).toBe('7.0')
  })

  it('searches names ignoring case and accents', () => {
    const fish = makeFish({ common_name: 'Pléco' })
    expect(matchesSearch(fish, 'pleco')).toBe(true)
    expect(matchesSearch(fish, 'CORYDORAS')).toBe(true)
    expect(matchesSearch(fish, 'tetra')).toBe(false)
  })
})

describe('time', () => {
  const now = Date.parse('2026-10-31T12:00:00Z')
  it('says how long ago', () => {
    expect(timeAgo('2026-10-31T11:59:30Z', now)).toBe('just now')
    expect(timeAgo('2026-10-31T09:00:00Z', now)).toBe('3 h ago')
  })
  it('says how long is left', () => {
    expect(timeLeft('2026-11-01T02:30:00Z', now)).toBe('14 h 30 min')
    expect(timeLeft('2026-10-31T11:00:00Z', now)).toBe('0 min')
  })
})
