import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api } from '../api/client'
import type { Fish } from '../api/types'

// The whole catalogue is about 50 KB gzipped, so it is loaded once and searched in the browser
interface CatalogueState {
  fish: Fish[]
  byId: Map<number, Fish>
  loading: boolean
  error: string | null
  reload: () => void
  // fish in a tank may have been retired since, those are fetched one by one
  lookup: (id: number) => Promise<Fish | null>
}

const CatalogueContext = createContext<CatalogueState | null>(null)

export function CatalogueProvider({ children }: { children: ReactNode }) {
  const [fish, setFish] = useState<Fish[]>([])
  const [extra, setExtra] = useState<Map<number, Fish>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .listFish()
      .then((loaded) => {
        if (cancelled) return
        setFish(loaded)
        setError(null)
      })
      .catch((reason: Error) => !cancelled && setError(reason.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [version])

  const byId = useMemo(() => {
    const map = new Map(extra)
    for (const entry of fish) map.set(entry.id, entry)
    return map
  }, [fish, extra])

  const lookup = useCallback(
    async (id: number) => {
      const known = byId.get(id)
      if (known) return known
      try {
        const loaded = await api.getFish(id)
        setExtra((current) => new Map(current).set(id, loaded))
        return loaded
      } catch {
        return null
      }
    },
    [byId],
  )

  const value = useMemo(
    () => ({ fish, byId, loading, error, reload: () => setVersion((current) => current + 1), lookup }),
    [fish, byId, loading, error, lookup],
  )
  return <CatalogueContext.Provider value={value}>{children}</CatalogueContext.Provider>
}

export function useCatalogue() {
  const state = useContext(CatalogueContext)
  if (!state) throw new Error('useCatalogue needs a CatalogueProvider')
  return state
}
