import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import type { Transaction, UploadResponse, PipelineRunResponse, PipelineStatusResponse } from '../types'
import FileUpload from '../components/FileUpload'
import TransactionTable from '../components/TransactionTable'
import Toast from '../components/Toast'
import type { ToastMessage } from '../components/Toast'

let toastCounter = 0

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

export default function ReviewPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [editedIds, setEditedIds] = useState<Set<string>>(new Set())
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())
  const [uploadLoading, setUploadLoading] = useState(false)
  const [pipelineLoading, setPipelineLoading] = useState(false)
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null)
  const [lastRun, setLastRun] = useState<PipelineRunResponse | null>(null)
  const [month, setMonth] = useState('')
  const [categories, setCategories] = useState<string[]>([])
  const [properties, setProperties] = useState<string[]>([])
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const [uploadStats, setUploadStats] = useState<Pick<UploadResponse, 'total' | 'auto_categorized' | 'needs_review'> | null>(null)

  const addToast = useCallback((text: string, type: ToastMessage['type'] = 'info') => {
    setToasts(prev => [...prev, { id: ++toastCounter, text, type }])
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  useEffect(() => {
    Promise.all([api.getCategories(), api.getProperties(), api.pipelineStatus()])
      .then(([cats, props, status]) => {
        setCategories([...cats.income_categories, ...cats.categories])
        setProperties(props.properties)
        setPipelineStatus(status)
      })
      .catch(e => addToast(`Config load error: ${(e as Error).message}`, 'error'))
  }, [addToast])

  const handleUpload = async (files: File[]) => {
    setUploadLoading(true)
    try {
      const result = await api.uploadCSVs(files)
      setTransactions(result.transactions)
      setEditedIds(new Set())
      setUploadStats({ total: result.total, auto_categorized: result.auto_categorized, needs_review: result.needs_review })
      addToast(`Loaded ${result.total} transactions (${result.auto_categorized} auto-categorized, ${result.needs_review} need review)`, 'success')
    } catch (e) {
      addToast(`Upload failed: ${(e as Error).message}`, 'error')
    } finally {
      setUploadLoading(false)
    }
  }

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

  const handleRunPipeline = async () => {
    setPipelineLoading(true)
    try {
      const result = await api.runPipeline(month || undefined)
      setLastRun(result)
      addToast(result.message, result.status === 'success' ? 'success' : 'error')
      const status = await api.pipelineStatus()
      setPipelineStatus(status)
    } catch (e) {
      addToast(`Pipeline error: ${(e as Error).message}`, 'error')
    } finally {
      setPipelineLoading(false)
    }
  }

  // Derived stats from current transactions
  const totalIncome = transactions.filter(t => t.amount > 0).reduce((s, t) => s + t.amount, 0)
  const totalExpenses = transactions.filter(t => t.amount < 0).reduce((s, t) => s + Math.abs(t.amount), 0)
  const needsReviewCount = transactions.filter(t => t.needs_review).length
  const isPipelineRunning = pipelineStatus?.running ?? false

  return (
    <div className="p-6 space-y-6">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Statements</h1>
        <p className="text-sm text-gray-500 mt-0.5">Upload your bank and credit card CSVs, review categorization, then push to Google Sheets.</p>
      </div>

      {/* Upload area */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-gray-800 mb-4">Import CSV Files</h2>
        <FileUpload onFiles={handleUpload} loading={uploadLoading} />
      </div>

      {/* Upload stats — shown after upload */}
      {uploadStats && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <p className="text-2xl font-bold text-gray-900">{uploadStats.total}</p>
            <p className="text-sm text-gray-500 mt-0.5">Total Transactions</p>
          </div>
          <div className="bg-white rounded-xl border border-green-100 bg-green-50 p-4 text-center">
            <p className="text-2xl font-bold text-green-600">{uploadStats.auto_categorized}</p>
            <p className="text-sm text-gray-500 mt-0.5">Auto-Categorized</p>
          </div>
          <div className="bg-white rounded-xl border border-amber-100 bg-amber-50 p-4 text-center">
            <p className="text-2xl font-bold text-amber-600">{uploadStats.needs_review}</p>
            <p className="text-sm text-gray-500 mt-0.5">Need Review</p>
          </div>
        </div>
      )}

      {/* Transaction table */}
      {transactions.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="font-semibold text-gray-800">Review Transactions</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                {needsReviewCount > 0
                  ? `${needsReviewCount} transaction${needsReviewCount !== 1 ? 's' : ''} need review — shown at top in yellow`
                  : 'All transactions categorized'}
              </p>
            </div>
            <div className="flex items-center gap-3 text-sm text-gray-500">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-green-200 inline-block" /> Auto
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-yellow-200 inline-block" /> Needs review
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-blue-200 inline-block" /> Edited
              </span>
            </div>
          </div>
          <TransactionTable
            transactions={transactions}
            categories={categories}
            properties={properties}
            editedIds={editedIds}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
            saving={savingIds}
          />
        </div>
      )}

      {/* Push to Sheets panel — always shown */}
      {transactions.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <h2 className="font-semibold text-gray-800">Push to Google Sheets</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                {needsReviewCount > 0
                  ? `${needsReviewCount} transaction${needsReviewCount !== 1 ? 's' : ''} still need review before pushing.`
                  : `Ready to push: ${fmt(totalIncome)} income, ${fmt(totalExpenses)} expenses.`}
              </p>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <input
                type="month"
                value={month}
                onChange={e => setMonth(e.target.value)}
                placeholder="All months"
                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
              <button
                onClick={handleRunPipeline}
                disabled={pipelineLoading || isPipelineRunning || needsReviewCount > 0}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium py-2 px-4 rounded-lg transition-colors"
              >
                <svg className={`w-4 h-4 ${pipelineLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {pipelineLoading ? 'Pushing…' : 'Push to Sheets'}
              </button>
            </div>
          </div>

          {/* Last run result */}
          {lastRun && (
            <div className={`mt-4 rounded-lg px-4 py-3 text-sm ${lastRun.status === 'success' ? 'bg-green-50 text-green-800 border border-green-100' : 'bg-red-50 text-red-800 border border-red-100'}`}>
              {lastRun.status === 'success'
                ? `✓ Wrote ${lastRun.transactions_written} transactions to Google Sheets.`
                : `✗ ${lastRun.message}`}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
