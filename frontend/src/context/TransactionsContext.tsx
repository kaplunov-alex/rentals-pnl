import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { Transaction } from '../types'

const currentMonthValue = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

interface TransactionsContextValue {
  transactions: Transaction[]
  month: string
  loading: boolean
  setMonth: (month: string) => void
  /** Populate directly from an upload response — avoids a redundant fetch */
  populate: (txns: Transaction[]) => void
  /** Update a single transaction in the cache after a save */
  updateTransaction: (updated: Transaction) => void
}

const TransactionsContext = createContext<TransactionsContextValue>({
  transactions: [],
  month: currentMonthValue(),
  loading: false,
  setMonth: () => {},
  populate: () => {},
  updateTransaction: () => {},
})

export function TransactionsProvider({ children }: { children: ReactNode }) {
  const [month, setMonthState] = useState(currentMonthValue())
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loadedMonth, setLoadedMonth] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const setMonth = useCallback((m: string) => {
    setMonthState(m)
  }, [])

  useEffect(() => {
    if (month === loadedMonth) return
    setLoading(true)
    api.listTransactions(month || undefined)
      .then(data => {
        setTransactions(data)
        setLoadedMonth(month)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [month, loadedMonth])

  const populate = useCallback((txns: Transaction[]) => {
    setTransactions(txns)
    setLoadedMonth(month)
  }, [month])

  const updateTransaction = useCallback((updated: Transaction) => {
    setTransactions(prev => prev.map(t => t.id === updated.id ? updated : t))
  }, [])

  return (
    <TransactionsContext.Provider value={{ transactions, month, loading, setMonth, populate, updateTransaction }}>
      {children}
    </TransactionsContext.Provider>
  )
}

export const useTransactions = () => useContext(TransactionsContext)
