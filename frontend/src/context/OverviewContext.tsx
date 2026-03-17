import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { OverviewData } from '../types'

interface OverviewContextValue {
  overview: OverviewData | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const OverviewContext = createContext<OverviewContextValue>({
  overview: null,
  loading: true,
  error: null,
  refresh: async () => {},
})

export function OverviewProvider({ children }: { children: ReactNode }) {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getOverview()
      setOverview(data)
    } catch (e) {
      setError((e as Error).message || 'Failed to load overview')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return (
    <OverviewContext.Provider value={{ overview, loading, error, refresh }}>
      {children}
    </OverviewContext.Provider>
  )
}

export const useOverview = () => useContext(OverviewContext)
