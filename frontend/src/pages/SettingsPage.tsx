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
        setCategories(cats.categories)
        setProperties(props.properties)
      })
      .catch(e => addToast(`Failed to load config: ${(e as Error).message}`, 'error'))
      .finally(() => setLoading(false))
  }, [addToast])

  return (
    <div className="space-y-6">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <div>
        <h1 className="text-xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500">Manage vendor mappings and view configuration.</p>
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-400">Loading...</div>
      ) : (
        <>
          <VendorMappings
            categories={categories}
            properties={properties}
            onToast={addToast}
          />

          {/* Config summary */}
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <h3 className="font-semibold text-gray-800 mb-3">Configuration</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Properties</p>
                <ul className="space-y-1">
                  {properties.map(p => (
                    <li key={p} className="text-sm text-gray-700 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-blue-400 inline-block" />
                      {p}
                    </li>
                  ))}
                  {properties.length === 0 && <li className="text-sm text-gray-400">No properties configured</li>}
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Categories</p>
                <ul className="space-y-1">
                  {categories.map(c => (
                    <li key={c} className="text-sm text-gray-700 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
                      {c}
                    </li>
                  ))}
                  {categories.length === 0 && <li className="text-sm text-gray-400">No categories configured</li>}
                </ul>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
