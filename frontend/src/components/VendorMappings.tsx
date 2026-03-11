import { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { VendorMapping } from '../types'

interface Props {
  categories: string[]
  properties: string[]
  onToast: (msg: string, type?: 'success' | 'error') => void
}

export default function VendorMappings({ categories, properties, onToast }: Props) {
  const [mappings, setMappings] = useState<VendorMapping[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<Set<string>>(new Set())
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState<VendorMapping>({ key: '', property: '', category: '' })

  const load = async () => {
    try {
      setLoading(true)
      const data = await api.getVendorMappings()
      setMappings(data)
    } catch (e) {
      onToast(`Failed to load vendor mappings: ${(e as Error).message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (key: string) => {
    setDeleting(prev => new Set(prev).add(key))
    try {
      await api.deleteVendorMapping(key)
      setMappings(prev => prev.filter(m => m.key !== key))
      onToast('Mapping deleted', 'success')
    } catch (e) {
      onToast(`Delete failed: ${(e as Error).message}`, 'error')
    } finally {
      setDeleting(prev => { const s = new Set(prev); s.delete(key); return s })
    }
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.key.trim() || !form.property || !form.category) {
      onToast('All fields required', 'error')
      return
    }
    setAdding(true)
    try {
      const created = await api.addVendorMapping(form)
      setMappings(prev => [...prev, created])
      setForm({ key: '', property: '', category: '' })
      onToast('Mapping added', 'success')
    } catch (e) {
      onToast(`Add failed: ${(e as Error).message}`, 'error')
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Add form */}
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <h3 className="font-semibold text-gray-800 mb-3">Add Vendor Mapping</h3>
        <form onSubmit={handleAdd} className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Vendor keyword</label>
            <input
              type="text"
              placeholder="e.g. Home Depot"
              value={form.key}
              onChange={e => setForm(f => ({ ...f, key: e.target.value }))}
              className="border border-gray-300 rounded px-2 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Property</label>
            <select
              value={form.property}
              onChange={e => setForm(f => ({ ...f, property: e.target.value }))}
              className="border border-gray-300 rounded px-2 py-1.5 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value="">-- select --</option>
              {properties.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Category</label>
            <select
              value={form.category}
              onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              className="border border-gray-300 rounded px-2 py-1.5 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value="">-- select --</option>
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <button
            type="submit"
            disabled={adding}
            className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {adding ? 'Adding...' : 'Add'}
          </button>
        </form>
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-800">Vendor Mappings ({mappings.length})</h3>
          <button onClick={load} className="text-xs text-blue-600 hover:underline">Refresh</button>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading...</div>
        ) : mappings.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No vendor mappings configured</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-100 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Vendor Keyword</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Property</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Category</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mappings.map(m => (
                  <tr key={m.key} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-mono text-gray-800">{m.key}</td>
                    <td className="px-4 py-2 text-gray-600">{m.property}</td>
                    <td className="px-4 py-2 text-gray-600">{m.category}</td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => handleDelete(m.key)}
                        disabled={deleting.has(m.key)}
                        className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50 transition-colors"
                      >
                        {deleting.has(m.key) ? 'Deleting...' : 'Delete'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
