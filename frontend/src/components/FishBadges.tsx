import type { Fish } from '../api/types'
import { crossSpeciesSummary, temperamentGroup } from '../lib/fish'
import { Badge } from './ui'

export function TemperamentBadge({ fish }: { fish: Fish }) {
  const group = temperamentGroup(fish)
  if (group === 'solo') {
    return (
      <Badge tone="warn" title="Its temperament is not known yet, so it can only be kept alone">
        Solo only
      </Badge>
    )
  }
  if (group === 'peaceful') return <Badge tone="ok">Peaceful</Badge>
  return (
    <Badge tone="danger" title={crossSpeciesSummary(fish)}>
      {fish.cross_species_temperament === 'aggressive to smaller' ? 'Hunts smaller fish' : 'Territorial'}
    </Badge>
  )
}

export function WaterBadges({ fish }: { fish: Fish }) {
  return (
    <>
      <Badge title="Water temperature">
        {fish.minimum_temperature}–{fish.maximum_temperature} °C
      </Badge>
      <Badge title="pH">
        pH {fish.minimum_ph}–{fish.maximum_ph}
      </Badge>
    </>
  )
}
