// The shapes the fishtank api answers with, see the README for every endpoint

export type InSpeciesTemperament =
  | 'peaceful'
  | 'peaceful to males'
  | 'peaceful to females'
  | 'aggressive/territorial'
  | 'unknown'

export type CrossSpeciesTemperament = 'peaceful' | 'aggressive/territorial' | 'aggressive to smaller' | 'unknown'

export const IN_SPECIES_TEMPERAMENTS: InSpeciesTemperament[] = [
  'peaceful',
  'peaceful to males',
  'peaceful to females',
  'aggressive/territorial',
  'unknown',
]
export const CROSS_SPECIES_TEMPERAMENTS: CrossSpeciesTemperament[] = [
  'peaceful',
  'aggressive/territorial',
  'aggressive to smaller',
  'unknown',
]

export interface Picture {
  url: string
  author: string | null
  licence: string
  credit: string
  source_url: string
}

export interface Fish {
  id: number
  scientific_name: string
  common_name: string | null
  family_name: string
  minimum_size: number | null
  maximum_size: number | null
  minimum_ph: number
  maximum_ph: number
  minimum_water_hardness: number
  maximum_water_hardness: number
  minimum_temperature: number
  maximum_temperature: number
  reproduce_method: string | null
  origin: string | null
  in_species_temperament: InSpeciesTemperament
  cross_species_temperament: CrossSpeciesTemperament
  fishtank_position: string | null
  fishbase_spec_code: number | null
  data_source: string
  fishbase_url: string | null
  retired: boolean
  pictures: Picture[]
  // only in answers to admins
  fishtank_count?: number
}

export interface TankSize {
  length: number
  width: number
  height: number
}

export interface TankFish {
  id: number
  scientific_name: string
  common_name: string | null
  count: number
}

export interface Fishtank {
  key: string
  name: string | null
  size: TankSize
  saved: boolean
  fish: TankFish[]
  created_at: string
  updated_at: string
  expires_at: string | null
}

export type Role = 'user' | 'admin'

export interface User {
  id: number
  username: string
  role: Role
  created_at: string
}

export interface LoginAnswer {
  user: User
  token: string
  expires_at: string
}

export interface Compatibility {
  compatible: number[]
  incompatible: { id: number; reason: string }[]
}

// the fields an admin sends to create or change a fish
export type FishInput = Partial<
  Omit<Fish, 'id' | 'fishbase_url' | 'retired' | 'pictures' | 'fishtank_count'>
>
