import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import type { Transaction, UploadResponse, PipelineRunResponse, PipelineStatusResponse } from '../types'
import FileUpload from '../components/FileUpload'
import TransactionTable from '../components/TransactionTable'
import MonthlySummary from '../components/MonthlySummary'
import PipelineStatus from '../components/PipelineStatus'
import Toast from '../components/Toast'
import type { ToastMessage } from '../components/Toast'

let toastCounter = 0

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

  // Load config on mount
  useEffect(() => {
    Promise.all([api.getCategories(), api.getProperties(), api.pipelineStatus()])
      .then(([cats, props, status]) => {
        setCategories(cats.categories)
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
    // Optimistically update UI
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
      // Revert
      setEditedIds(prev => { const s = new Set(prev); s.delete(id); return s })
    } finally {
      setSavingIds(prev => { const s = new Set(prev); s.delete(id); return s })
    }
  }

  const handleRunPipeline = async () => {
    setPipelineLoading(true)
    try {
      const result = await api.runPipeline(month || undefined)
      setLastRun(result)
      addToast(result.message, result.status === 'success' ? 'success' : 'error')
      // Refresh status
      const status = await api.pipelineStatus()
      setPipelineStatus(status)
    } catch (e) {
      addToast(`Pipeline error: ${(e as Error).message}`, 'error')
    } finally {
      setPipelineLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <div>
        <h1 className="text-xl font-bold text-gray-900 mb-1">Review Transactions</h1>
        <p className="text-sm text-gray-500">Upload CSV exports, review categorization, then push to Google Sheets.</p>
      </div>

      <FileUpload onFiles={handleUpload} loading={uploadLoading} />

      {uploadStats && (
        <div className="flex items-center gap-4 text-sm text-gray-500 px-1">
          <span>Uploaded: <strong className="text-gray-700">{uploadStats.total}</strong></span>
          <span>Auto: <strong className="text-green-600">{uploadStats.auto_categorized}</strong></span>
          <span>Review: <strong className="text-yellow-600">{uploadStats.needs_review}</strong></span>
        </div>
      )}

      {transactions.length > 0 && (
        <>
          <MonthlySummary transactions={transactions} editedIds={editedIds} />
          <TransactionTable
            transactions={transactions}
            categories={categories}
            properties={properties}
            editedIds={editedIds}
            onUpdate={handleUpdate}
            saving={savingIds}
          />
        </>
      )}

      <PipelineStatus
        status={pipelineStatus}
        lastRun={lastRun}
        onRun={handleRunPipeline}
        loading={pipelineLoading}
        month={month}
        onMonthChange={setMonth}
      />
    </div>
  )
}
