import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { api } from '../api/client'
import type { OverviewData } from '../types'

interface OverviewContextValue {
  overview: OverviewData | null
  loading: boolean
  refresh: () => Promise<void>
}

const OverviewContext = createContext<OverviewContextValue>({
  overview: null,
  loading: true,
  refresh: async () => {},
})

export function OverviewProvider({ children }: { children: ReactNode }) {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getOverview()
      setOverview(data)
    } catch {
      // leave stale data in place on error
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return (
    <OverviewContext.Provider value={{ overview, loading, refresh }}>
      {children}
    </OverviewContext.Provider>
  )
}

export const useOverview = () => useContext(OverviewContext)
