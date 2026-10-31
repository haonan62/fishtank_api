import { readStorage, writeStorage } from '../api/client'

// A visitor's fishtanks are found again by their keys, which only this browser knows
const VISITOR_TANKS_KEY = 'fishtank.visitorTanks'
const LAST_TANK_KEY = 'fishtank.lastTank'

export function visitorTankKeys(): string[] {
  try {
    const keys = JSON.parse(readStorage(VISITOR_TANKS_KEY) ?? '[]')
    return Array.isArray(keys) ? keys.filter((key) => typeof key === 'string') : []
  } catch {
    return []
  }
}

function storeVisitorTankKeys(keys: string[]) {
  writeStorage(VISITOR_TANKS_KEY, keys.length ? JSON.stringify(keys) : null)
}

export function rememberVisitorTank(key: string) {
  const keys = visitorTankKeys()
  if (!keys.includes(key)) storeVisitorTankKeys([key, ...keys])
}

export function forgetVisitorTank(key: string) {
  storeVisitorTankKeys(visitorTankKeys().filter((stored) => stored !== key))
  if (lastTankKey() === key) setLastTankKey(null)
}

// the tank "Add to tank" goes to without asking
export function lastTankKey() {
  return readStorage(LAST_TANK_KEY)
}

export function setLastTankKey(key: string | null) {
  writeStorage(LAST_TANK_KEY, key)
}
