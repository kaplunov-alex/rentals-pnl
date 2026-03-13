import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import type { Transaction } from '../types'
import TransactionTable from '../components/TransactionTable'
import Toast from '../components/Toast'
import type { ToastMessage } from '../components/Toast'

let toastCounter = 0

const currentMonthValue = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [editedIds, setEditedIds] = useState<Set<string>>(new Set())
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [month, setMonth] = useState(currentMonthValue())
  const [selectedProperty, setSelectedProperty] = useState('all')
  const [search, setSearch] = useState('')
  const [categories, setCategories] = useState<string[]>([])
  const [properties, setProperties] = useState<string[]>([])
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const addToast = useCallback((text: string, type: ToastMessage['type'] = 'info') => {
    setToasts(prev => [...prev, { id: ++toastCounter, text, type }])
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  useEffect(() => {
    Promise.all([api.getCategories(), api.getProperties()])
      .then(([cats, props]) => {
        setCategories([...cats.income_categories, ...cats.categories])
        setProperties(props.properties)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    api.listTransactions(month || undefined)
      .then(setTransactions)
      .catch(e => addToast(`Failed to load transactions: ${(e as Error).message}`, 'error'))
      .finally(() => setLoading(false))
  }, [month, addToast])

  const handleUpdate = async (id: string, field: 'property' | 'category', value: string) => {
    setTransactions(prev =>
      prev.map(t => t.id === id ? { ...t, [field]: value, needs_review: false } : t)
    )
    setEditedIds(prev => new Set(prev).add(id))
    setSavingIds(prev => new Set(prev).add(id))
    try {
      const updated = await api.updateTransaction(id, { [field]: value })
      setTransactions(prev => prev.map(t => t.id === updated.id ? updated : t))
    } catch (e) {
      addToast(`Save failed: ${(e as Error).message}`, 'error')
      setEditedIds(prev => { const s = new Set(prev); s.delete(id); return s })
    } finally {
      setSavingIds(prev => { const s = new Set(prev); s.delete(id); return s })
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteTransaction(id)
      setTransactions(prev => prev.filter(t => t.id !== id))
      setEditedIds(prev => { const s = new Set(prev); s.delete(id); return s })
    } catch (e) {
      addToast(`Delete failed: ${(e as Error).message}`, 'error')
    }
  }

  // Apply property + search filters client-side
  const filtered = transactions
    .filter(t => selectedProperty === 'all' || t.property === selectedProperty)
    .filter(t => !search || t.description.toLowerCase().includes(search.toLowerCase()))

  const needsReviewCount = filtered.filter(t => t.needs_review).length

  return (
    <div className="p-6 space-y-6">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Transactions</h1>
          <p className="text-sm text-gray-500 mt-0.5">Browse and edit all transactions for the selected month.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Search */}
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search descriptions…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 w-48"
            />
          </div>
          {/* Property filter */}
          <select
            value={selectedProperty}
            onChange={e => setSelectedProperty(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value="all">All Properties</option>
            {properties.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          {/* Month filter */}
          <input
            type="month"
            value={month}
            onChange={e => setMonth(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
      </div>

      {/* Table card */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-sm font-medium text-gray-700">
              {loading ? 'Loading…' : `${filtered.length} transaction${filtered.length !== 1 ? 's' : ''}`}
              {search && ` matching "${search}"`}
            </p>
            {needsReviewCount > 0 && (
              <p className="text-xs text-amber-600 mt-0.5">{needsReviewCount} need review — shown at top in yellow</p>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-green-200 inline-block" /> Auto
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-yellow-200 inline-block" /> Needs review
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-200 inline-block" /> Edited
            </span>
          </div>
        </div>

        {loading && transactions.length === 0 ? (
          <div className="text-center py-16 text-gray-400 text-sm">Loading transactions…</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-400 text-sm">
            {transactions.length === 0
              ? 'No transactions for this period. Upload CSVs from Upload Statements first.'
              : 'No transactions match your filters.'}
          </div>
        ) : (
          <TransactionTable
            transactions={filtered}
            categories={categories}
            properties={properties}
            editedIds={editedIds}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
            saving={savingIds}
          />
        )}
      </div>
    </div>
  )
}
