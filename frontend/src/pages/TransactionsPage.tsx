import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import Toast from '../components/Toast'
import type { ToastMessage } from '../components/Toast'
import { useTransactions } from '../context/TransactionsContext'

let toastCounter = 0

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

// Per-row local edits before saving
type RowEdits = Record<string, { category: string; property: string; comments: string }>

type TabFilter = 'review' | 'categorized' | 'all'

export default function TransactionsPage() {
  const { transactions, loading, updateTransaction } = useTransactions()
  const [rowEdits, setRowEdits] = useState<RowEdits>({})
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [tab, setTab] = useState<TabFilter>('all')
  const [showFilters, setShowFilters] = useState(false)
  const [selectedProperty, setSelectedProperty] = useState('all')
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

  // Initialize row edits for new transactions; preserve any edits already in progress
  useEffect(() => {
    setRowEdits(prev => {
      const next: RowEdits = {}
      transactions.forEach(t => {
        // Keep existing unsaved edits; initialize from transaction data only for new rows
        next[t.id] = prev[t.id] ?? { category: t.category ?? '', property: t.property ?? '', comments: t.comments ?? '' }
      })
      return next
    })
  }, [transactions])

  const handleSave = async (txnId: string, createRule: boolean) => {
    const txn = transactions.find(t => t.id === txnId)
    if (!txn) return
    const edits = rowEdits[txnId] ?? { category: txn.category ?? '', property: txn.property ?? '', comments: txn.comments ?? '' }
    if (!edits.category || !edits.property) {
      addToast('Please select both a category and a property before saving.', 'error')
      return
    }
    setSavingIds(prev => new Set(prev).add(txnId))
    try {
      const updated = await api.updateTransaction(txnId, { category: edits.category, property: edits.property, comments: edits.comments })
      updateTransaction(updated)

      if (createRule) {
        await api.addVendorMapping({ key: txn.description, property: edits.property, category: edits.category })
        addToast(`Saved and created rule for "${txn.description}"`, 'success')
      } else {
        addToast('Transaction saved', 'success')
      }
    } catch (e) {
      addToast(`Save failed: ${(e as Error).message}`, 'error')
    } finally {
      setSavingIds(prev => { const s = new Set(prev); s.delete(txnId); return s })
    }
  }

  const setRowField = (id: string, field: 'category' | 'property' | 'comments', value: string) => {
    setRowEdits(prev => ({ ...prev, [id]: { ...prev[id], [field]: value } }))
  }

  const needsReviewCount = transactions.filter(t => t.needs_review).length
  const categorizedCount = transactions.filter(t => !t.needs_review).length

  const filtered = transactions
    .filter(t => {
      if (tab === 'review') return t.needs_review
      if (tab === 'categorized') return !t.needs_review
      return true
    })
    .filter(t => selectedProperty === 'all' || t.property === selectedProperty)
    .filter(t => !search || t.description.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="p-6 space-y-5">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <div>
        <h1 className="text-2xl font-bold text-gray-900">Transactions</h1>
        <p className="text-sm text-gray-500 mt-0.5">Review and categorize transactions before syncing to Google Sheets.</p>
      </div>

      {/* Tab filter */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setTab('review')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            tab === 'review'
              ? 'bg-amber-100 text-amber-800 border border-amber-200'
              : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
          }`}
        >
          Needs Review
          {needsReviewCount > 0 && (
            <span className={`text-xs px-1.5 py-0.5 rounded-full font-semibold ${tab === 'review' ? 'bg-amber-200 text-amber-900' : 'bg-gray-100 text-gray-600'}`}>
              {needsReviewCount}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab('categorized')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            tab === 'categorized'
              ? 'bg-gray-900 text-white'
              : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
          }`}
        >
          Categorized
          {categorizedCount > 0 && tab !== 'categorized' && (
            <span className="text-xs px-1.5 py-0.5 rounded-full font-semibold bg-gray-100 text-gray-600">
              {categorizedCount}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab('all')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            tab === 'all'
              ? 'bg-gray-900 text-white'
              : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
          }`}
        >
          All
        </button>
      </div>

      {/* Search + Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search descriptions..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
        <button
          onClick={() => setShowFilters(f => !f)}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl border transition-colors ${
            showFilters ? 'bg-gray-900 text-white border-gray-900' : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
          }`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z" />
          </svg>
          Filters
        </button>
      </div>

      {showFilters && (
        <div className="flex items-center gap-3 flex-wrap p-4 bg-white rounded-xl border border-gray-200">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Property</label>
            <select
              value={selectedProperty}
              onChange={e => setSelectedProperty(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value="all">All Properties</option>
              {properties.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>
      )}

      {/* Transaction list */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="grid grid-cols-[110px_1fr_180px_280px_110px_160px] gap-3 px-5 py-3 border-b border-gray-100 bg-gray-50">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</span>
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Description</span>
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Comments</span>
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Category & Property</span>
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Amount</span>
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Action</span>
        </div>

        {loading && transactions.length === 0 ? (
          <div className="text-center py-16 text-gray-400 text-sm">Loading transactions…</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-400 text-sm">
            {transactions.length === 0
              ? 'No transactions for this period. Upload CSVs from Upload Statements first.'
              : tab === 'review'
              ? 'No transactions need review — all categorized!'
              : 'No transactions match your filters.'}
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filtered.map(txn => {
              const edits = rowEdits[txn.id] ?? { category: txn.category ?? '', property: txn.property ?? '', comments: txn.comments ?? '' }
              const isSaving = savingIds.has(txn.id)
              const isReady = edits.category && edits.property
              const fmtDate = new Date(txn.date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })

              return (
                <div key={txn.id} className="grid grid-cols-[110px_1fr_180px_280px_110px_160px] gap-3 px-5 py-4 items-center hover:bg-gray-50 transition-colors">
                  <span className="text-sm text-gray-600">{fmtDate}</span>

                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">{txn.description}</p>
                    {txn.property && !txn.needs_review && (
                      <p className="text-xs text-blue-500 mt-0.5 truncate">{txn.property} · {txn.category}</p>
                    )}
                    {txn.needs_review && (
                      <p className="text-xs text-amber-500 mt-0.5">Needs categorization</p>
                    )}
                  </div>

                  <input
                    type="text"
                    placeholder="Add note…"
                    value={edits.comments}
                    onChange={e => setRowField(txn.id, 'comments', e.target.value)}
                    disabled={isSaving}
                    className="border border-gray-200 rounded-lg px-2.5 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50 w-full"
                  />

                  <div className="flex flex-col gap-1.5">
                    <select
                      value={edits.category}
                      onChange={e => setRowField(txn.id, 'category', e.target.value)}
                      disabled={isSaving}
                      className="border border-gray-200 rounded-lg px-2.5 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
                    >
                      <option value="">Select Category...</option>
                      {categories.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <select
                      value={edits.property}
                      onChange={e => setRowField(txn.id, 'property', e.target.value)}
                      disabled={isSaving}
                      className="border border-gray-200 rounded-lg px-2.5 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
                    >
                      <option value="">Select Property...</option>
                      {properties.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>

                  <span className={`text-sm font-semibold text-right ${txn.amount < 0 ? 'text-gray-900' : 'text-green-600'}`}>
                    {txn.amount < 0 ? '-' : '+'}{fmt(Math.abs(txn.amount))}
                  </span>

                  <div className="flex justify-end gap-1.5">
                    {txn.needs_review ? (
                      <>
                        <button
                          onClick={() => handleSave(txn.id, false)}
                          disabled={isSaving || !isReady}
                          className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 disabled:opacity-40 text-gray-700 text-xs font-semibold rounded-lg transition-colors whitespace-nowrap"
                        >
                          {isSaving ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          onClick={() => handleSave(txn.id, true)}
                          disabled={isSaving || !isReady}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-xs font-semibold rounded-lg transition-colors whitespace-nowrap"
                        >
                          {isSaving ? 'Saving…' : '+ Rule'}
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleSave(txn.id, false)}
                        disabled={isSaving || !isReady}
                        className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 disabled:opacity-40 text-gray-700 text-xs font-semibold rounded-lg transition-colors whitespace-nowrap"
                      >
                        {isSaving ? 'Saving…' : 'Save'}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {!loading && filtered.length > 0 && (
        <p className="text-xs text-gray-400 text-center">
          Showing {filtered.length} of {transactions.length} transactions
        </p>
      )}
    </div>
  )
}
