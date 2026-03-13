import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import VendorMappings from '../components/VendorMappings'
import Toast from '../components/Toast'
import type { ToastMessage } from '../components/Toast'

let toastCounter = 0

export default function SettingsPage() {
  const [categories, setCategories] = useState<string[]>([])
  const [properties, setProperties] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
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
      .catch(e => addToast(`Failed to load config: ${(e as Error).message}`, 'error'))
      .finally(() => setLoading(false))
  }, [addToast])

  return (
    <div className="p-6 space-y-6">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <div>
        <h1 className="text-2xl font-bold text-gray-900">Categorization Rules</h1>
        <p className="text-sm text-gray-500 mt-0.5">Manage vendor mappings to auto-categorize future transactions.</p>
      </div>

      {loading ? (
        <div className="text-center py-16 text-gray-400">Loading...</div>
      ) : (
        <>
          <VendorMappings
            categories={categories}
            properties={properties}
            onToast={addToast}
          />

          {/* Config summary */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Properties</p>
              <ul className="space-y-2">
                {properties.map(p => (
                  <li key={p} className="flex items-center gap-2 text-sm text-gray-700">
                    <span className="w-2 h-2 rounded-full bg-blue-400 flex-shrink-0" />
                    {p}
                  </li>
                ))}
                {properties.length === 0 && <li className="text-sm text-gray-400">No properties configured</li>}
              </ul>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Categories</p>
              <ul className="space-y-2">
                {categories.map(c => (
                  <li key={c} className="flex items-center gap-2 text-sm text-gray-700">
                    <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                    {c}
                  </li>
                ))}
                {categories.length === 0 && <li className="text-sm text-gray-400">No categories configured</li>}
              </ul>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
