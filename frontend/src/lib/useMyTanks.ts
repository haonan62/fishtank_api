import { useCallback, useEffect, useState } from 'react'

import { ApiError, api } from '../api/client'
import type { Fishtank } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { forgetVisitorTank, visitorTankKeys } from './visitorTanks'

// Every tank this person can use: their saved tanks when logged in, and the visitor tanks this browser remembers
// Visitor tanks that expired or were saved by someone are forgotten on the way
export function useMyTanks() {
  const { user, ready } = useAuth()
  const [saved, setSaved] = useState<Fishtank[]>([])
  const [visitor, setVisitor] = useState<Fishtank[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    if (!ready) return
    let cancelled = false
    setLoading(true)
    const loadVisitor = Promise.all(
      visitorTankKeys().map((key) =>
        api.getTank(key).catch((reason) => {
          if (reason instanceof ApiError && reason.status === 404) forgetVisitorTank(key)
          return null
        }),
      ),
    ).then((tanks) => tanks.filter((tank): tank is Fishtank => tank !== null && !tank.saved))
    const loadSaved = user ? api.listTanks() : Promise.resolve([])
    Promise.all([loadSaved, loadVisitor])
      .then(([savedTanks, visitorTanks]) => {
        if (cancelled) return
        setSaved(savedTanks)
        setVisitor(visitorTanks)
        setError(null)
      })
      .catch((reason: Error) => !cancelled && setError(reason.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [user, ready, version])

  const reload = useCallback(() => setVersion((current) => current + 1), [])

  // the login dialog saves visitor tanks from anywhere, pages showing tanks then load them again
  useEffect(() => {
    window.addEventListener('fishtank:tanks-changed', reload)
    return () => window.removeEventListener('fishtank:tanks-changed', reload)
  }, [reload])

  return { saved, visitor, loading, error, reload }
}

export function tankTitle(tank: Pick<Fishtank, 'name'>) {
  return tank.name ?? 'Untitled tank'
}
