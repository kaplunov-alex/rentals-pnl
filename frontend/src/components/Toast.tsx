import { useEffect } from 'react'

export interface ToastMessage {
  id: number
  text: string
  type: 'success' | 'error' | 'info'
}

interface Props {
  toasts: ToastMessage[]
  onDismiss: (id: number) => void
}

export default function Toast({ toasts, onDismiss }: Props) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onDismiss }: { toast: ToastMessage; onDismiss: (id: number) => void }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 4000)
    return () => clearTimeout(timer)
  }, [toast.id, onDismiss])

  const colors = {
    success: 'bg-green-600 text-white',
    error: 'bg-red-600 text-white',
    info: 'bg-blue-600 text-white',
  }

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg shadow-lg ${colors[toast.type]}`}
      role="alert"
    >
      <span className="flex-1 text-sm">{toast.text}</span>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-white opacity-75 hover:opacity-100 transition-opacity text-lg leading-none"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  )
}
