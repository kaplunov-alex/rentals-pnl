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
  const [search, setSearch] = useState('')
  const [filterProperty, setFilterProperty] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
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

  const filtered = mappings.filter(m =>
    (!search || m.key.toLowerCase().includes(search.toLowerCase())) &&
    (!filterProperty || m.property === filterProperty) &&
    (!filterCategory || m.category === filterCategory)
  )

  return (
    <div className="space-y-4">
      {/* Add form */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-gray-800 mb-4">Add New Rule</h2>
        <form onSubmit={handleAdd} className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[160px]">
            <label className="block text-xs font-medium text-gray-500 mb-1">Vendor keyword</label>
            <input
              type="text"
              placeholder="e.g. Home Depot"
              value={form.key}
              onChange={e => setForm(f => ({ ...f, key: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>
          <div className="min-w-[160px]">
            <label className="block text-xs font-medium text-gray-500 mb-1">Property</label>
            <select
              value={form.property}
              onChange={e => setForm(f => ({ ...f, property: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value="">-- select --</option>
              {properties.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="min-w-[160px]">
            <label className="block text-xs font-medium text-gray-500 mb-1">Category</label>
            <select
              value={form.category}
              onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value="">-- select --</option>
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <button
            type="submit"
            disabled={adding}
            className="flex items-center gap-2 px-4 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {adding ? 'Adding…' : 'Add Rule'}
          </button>
        </form>
      </div>

      {/* Mappings table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="font-semibold text-gray-800">Existing Rules</h2>
            <p className="text-xs text-gray-400 mt-0.5">{mappings.length} rule{mappings.length !== 1 ? 's' : ''} configured</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative">
              <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Filter rules…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 w-40"
              />
            </div>
            <select
              value={filterProperty}
              onChange={e => setFilterProperty(e.target.value)}
              className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value="">All Properties</option>
              {properties.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <select
              value={filterCategory}
              onChange={e => setFilterCategory(e.target.value)}
              className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value="">All Categories</option>
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <button
              onClick={load}
              className="text-xs text-blue-600 hover:text-blue-800 px-2 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {loading ? (
          <div className="py-16 text-center text-gray-400 text-sm">Loading rules…</div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-gray-400 text-sm">
            {mappings.length === 0 ? 'No rules configured yet. Add one above.' : 'No rules match your filter.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-100 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Vendor Keyword</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Property</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Category</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map(m => (
                  <tr key={m.key} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3 font-mono text-gray-800 text-xs">{m.key}</td>
                    <td className="px-5 py-3">
                      <span className="inline-flex items-center gap-1.5 text-gray-600">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                        {m.property}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span className="inline-flex items-center gap-1.5 text-gray-600">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
                        {m.category}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        onClick={() => handleDelete(m.key)}
                        disabled={deleting.has(m.key)}
                        className="text-xs text-gray-400 hover:text-red-500 disabled:opacity-50 transition-colors px-2 py-1 rounded hover:bg-red-50"
                      >
                        {deleting.has(m.key) ? 'Deleting…' : 'Delete'}
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
