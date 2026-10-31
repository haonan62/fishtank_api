import { describe, expect, it } from 'vitest'

import { cookieValue } from './client'

describe('cookieValue', () => {
  it('finds a cookie among others', () => {
    expect(cookieValue('theme=dark; fishtank_csrf=abc123; other=1', 'fishtank_csrf')).toBe('abc123')
  })

  it('does not match a cookie whose name only ends the same', () => {
    expect(cookieValue('old_fishtank_csrf=x', 'fishtank_csrf')).toBeNull()
  })

  it('keeps equal signs in the value and decodes it', () => {
    expect(cookieValue('token=a%20b=c', 'token')).toBe('a b=c')
  })

  it('is null without cookies', () => {
    expect(cookieValue('', 'fishtank_csrf')).toBeNull()
  })
})
