import type { CrossSpeciesTemperament, Fish, InSpeciesTemperament } from '../api/types'

// 146 fish have no common name, their scientific name is their name then
export function displayName(fish: Pick<Fish, 'common_name' | 'scientific_name'>) {
  return fish.common_name ?? fish.scientific_name
}

// A fish whose temperament is not known yet can only be kept alone, the simulation refuses any company
export function isSoloOnly(fish: Pick<Fish, 'cross_species_temperament' | 'in_species_temperament'>) {
  return fish.cross_species_temperament === 'unknown' || fish.in_species_temperament === 'unknown'
}

export type TemperamentGroup = 'peaceful' | 'aggressive' | 'solo'

export function temperamentGroup(fish: Fish): TemperamentGroup {
  if (isSoloOnly(fish)) return 'solo'
  return fish.cross_species_temperament === 'peaceful' ? 'peaceful' : 'aggressive'
}

export const CROSS_SPECIES_TEXT: Record<CrossSpeciesTemperament, string> = {
  peaceful: 'Peaceful with other species',
  'aggressive/territorial': 'Territorial, does not share a tank with other species',
  'aggressive to smaller': 'Attacks fish smaller than itself',
  unknown: 'Temperament not known yet, can only be kept alone',
}

export const IN_SPECIES_TEXT: Record<InSpeciesTemperament, string> = {
  peaceful: 'Lives peacefully with its own kind',
  'peaceful to males': 'Only peaceful towards males of its kind, keep one',
  'peaceful to females': 'Only peaceful towards females of its kind, keep one',
  'aggressive/territorial': 'Fights its own kind, keep one',
  unknown: 'Behaviour with its own kind is not known yet',
}

export function crossSpeciesSummary(fish: Fish) {
  if (fish.cross_species_temperament === 'aggressive to smaller' && fish.maximum_size !== null) {
    return `Attacks fish smaller than ${fish.maximum_size} cm`
  }
  return CROSS_SPECIES_TEXT[fish.cross_species_temperament]
}

export type TankLevel = 'top' | 'middle' | 'bottom'

export function tankLevel(fish: Pick<Fish, 'fishtank_position'>): TankLevel {
  const position = fish.fishtank_position?.toLowerCase() ?? ''
  if (position.startsWith('top')) return 'top'
  if (position.startsWith('bottom')) return 'bottom'
  return 'middle'
}

// The api explains a refusal with scientific names, the title says what it means in a few words
// fish is the fish that was refused, when known: a solo only fish refuses its own kind for lack of knowledge, not out of spite
export function alarmTitle(reason: string, fish?: Pick<Fish, 'cross_species_temperament' | 'in_species_temperament'>) {
  const text = reason.toLowerCase()
  if (text.includes('temperature')) return 'They need different water temperatures'
  if (text.includes('ph ranges')) return 'They need water of a different pH'
  if (text.includes('hardness')) return 'They need water of a different hardness'
  if (text.includes('in species')) return fish && isSoloOnly(fish) ? 'This fish can only be kept alone' : 'This fish fights its own kind'
  if (text.includes('not known yet')) return 'This fish can only be kept alone'
  if (text.includes('competition')) return 'These fish would not get along'
  if (text.includes('retired')) return 'This fish is no longer in the catalogue'
  if (text.includes('no such fish')) return 'That fish is not in the tank'
  return 'This fish cannot join the tank'
}

// a soft colour per family, so the drawn fish of one family look alike
export function familyHue(familyName: string) {
  let hash = 0
  for (const character of familyName) hash = (hash * 31 + character.charCodeAt(0)) >>> 0
  return hash % 360
}

export interface Range {
  min: number
  max: number
}

export interface WaterConditions {
  temperature: Range
  ph: Range
  hardness: Range
}

// The water every fish in the tank is happy in: the overlap of their ranges
// Returns null for an empty tank. The simulation only lets fish in whose ranges overlap, so the overlap is never empty
export function waterConditions(fish: Fish[]): WaterConditions | null {
  if (fish.length === 0) return null
  const overlap = (low: (f: Fish) => number, high: (f: Fish) => number): Range => ({
    min: Math.max(...fish.map(low)),
    max: Math.min(...fish.map(high)),
  })
  return {
    temperature: overlap((f) => f.minimum_temperature, (f) => f.maximum_temperature),
    ph: overlap((f) => f.minimum_ph, (f) => f.maximum_ph),
    hardness: overlap((f) => f.minimum_water_hardness, (f) => f.maximum_water_hardness),
  }
}

export function formatRange(range: Range, unit = '', digits = 0) {
  const low = range.min.toFixed(digits)
  const high = range.max.toFixed(digits)
  return low === high ? `${low}${unit}` : `${low}–${high}${unit}`
}

// matches common and scientific names, ignoring case and accents
export function matchesSearch(fish: Fish, search: string) {
  const query = normalise(search.trim())
  if (!query) return true
  return normalise(`${fish.common_name ?? ''} ${fish.scientific_name} ${fish.family_name}`).includes(query)
}

function normalise(text: string) {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}
