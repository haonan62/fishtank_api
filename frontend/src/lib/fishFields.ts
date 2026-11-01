// How the fields of a fish read in the admin pages, by the names the api uses
export const FIELD_LABELS: Record<string, string> = {
  scientific_name: 'Scientific name',
  common_name: 'Common name',
  family_name: 'Family',
  minimum_size: 'Smallest size',
  maximum_size: 'Largest size',
  minimum_ph: 'Lowest pH',
  maximum_ph: 'Highest pH',
  minimum_water_hardness: 'Lowest hardness',
  maximum_water_hardness: 'Highest hardness',
  minimum_temperature: 'Lowest temperature',
  maximum_temperature: 'Highest temperature',
  reproduce_method: 'Breeding',
  origin: 'Origin',
  in_species_temperament: 'With its own kind',
  cross_species_temperament: 'With other species',
  fishtank_position: 'Level in the tank',
  fishbase_spec_code: 'FishBase species code',
  minimum_group_size: 'Smallest group',
  group_size_source: 'Group size from',
  data_source: 'Data source',
  id: 'Id',
}

export function fieldLabel(name: string) {
  return FIELD_LABELS[name] ?? name
}

// changes listed in the order of the fish form, not alphabetically
export function orderedChanges<T>(changes: Record<string, T>): [string, T][] {
  const order = Object.keys(FIELD_LABELS)
  const position = (name: string) => (order.includes(name) ? order.indexOf(name) : order.length)
  return Object.entries(changes).sort(([a], [b]) => position(a) - position(b))
}

export function showValue(value: unknown) {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

// what an audit event says happened, for people
export const ACTION_LABELS: Record<string, string> = {
  'fish.create': 'added a fish',
  'fish.update': 'changed a fish',
  'fish.retire': 'retired a fish',
  'fish.restore': 'restored a fish',
  'fish.delete': 'removed a fish',
  'fish.import': 'imported a spreadsheet',
  'suggestion.approve': 'approved a suggestion',
  'suggestion.reject': 'rejected a suggestion',
  'user.role': 'changed a role',
  'picture.add': 'added a picture to',
  'picture.remove': 'removed a picture from',
}
