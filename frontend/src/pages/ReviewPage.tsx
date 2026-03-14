import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import FileUpload from '../components/FileUpload'
import Toast from '../components/Toast'
import type { ToastMessage } from '../components/Toast'
import { useTransactions } from '../context/TransactionsContext'

let toastCounter = 0

export default function ReviewPage() {
  const navigate = useNavigate()
  const { populate } = useTransactions()
  const [loading, setLoading] = useState(false)
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const addToast = useCallback((text: string, type: ToastMessage['type'] = 'info') => {
    setToasts(prev => [...prev, { id: ++toastCounter, text, type }])
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const handleUpload = async (files: File[]) => {
    setLoading(true)
    try {
      const result = await api.uploadCSVs(files)
      populate(result.transactions)
      navigate('/transactions')
    } catch (e) {
      addToast(`Upload failed: ${(e as Error).message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Statements</h1>
        <p className="text-sm text-gray-500 mt-0.5">Upload your bank and credit card CSVs. You'll be taken to Transactions to review and categorize.</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-gray-800 mb-4">Import CSV Files</h2>
        <FileUpload onFiles={handleUpload} loading={loading} />
      </div>
    </div>
  )
}
