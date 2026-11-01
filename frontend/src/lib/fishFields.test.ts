import { describe, expect, it } from 'vitest'

import { fieldLabel, orderedChanges, showValue } from './fishFields'

describe('fish fields', () => {
  it('lists changes in the order of the form', () => {
    const changes = { maximum_size: 1, unknown_field: 2, minimum_size: 3, scientific_name: 4 }
    expect(orderedChanges(changes).map(([name]) => name)).toEqual(['scientific_name', 'minimum_size', 'maximum_size', 'unknown_field'])
  })

  it('labels fields and shows empty values', () => {
    expect(fieldLabel('minimum_group_size')).toBe('Smallest group')
    expect(fieldLabel('colour')).toBe('colour')
    expect([showValue(null), showValue(''), showValue(0), showValue('peaceful')]).toEqual(['—', '—', '0', 'peaceful'])
  })
})
