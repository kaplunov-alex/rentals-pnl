import { useState } from 'react'
import type { Transaction } from '../types'
import CategorySelect from './CategorySelect'
import PropertySelect from './PropertySelect'

type SortField = 'date' | 'description' | 'property' | 'category' | 'amount' | 'source'
type SortDir = 'asc' | 'desc'

interface Props {
  transactions: Transaction[]
  categories: string[]
  properties: string[]
  editedIds: Set<string>
  onUpdate: (id: string, field: 'property' | 'category', value: string) => void
  onDelete: (id: string) => void
  saving: Set<string>
}

export default function TransactionTable({
  transactions,
  categories,
  properties,
  editedIds,
  onUpdate,
  onDelete,
  saving,
}: Props) {
  const [sortField, setSortField] = useState<SortField>('date')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  const sorted = [...transactions].sort((a, b) => {
    // needs_review rows float to top regardless of sort
    if (a.needs_review && !b.needs_review) return -1
    if (!a.needs_review && b.needs_review) return 1

    let cmp = 0
    switch (sortField) {
      case 'date':
        cmp = a.date.localeCompare(b.date)
        break
      case 'description':
        cmp = a.description.localeCompare(b.description)
        break
      case 'property':
        cmp = (a.property ?? '').localeCompare(b.property ?? '')
        break
      case 'category':
        cmp = (a.category ?? '').localeCompare(b.category ?? '')
        break
      case 'amount':
        cmp = a.amount - b.amount
        break
      case 'source':
        cmp = a.source.localeCompare(b.source)
        break
    }
    return sortDir === 'asc' ? cmp : -cmp
  })

  const rowClass = (txn: Transaction) => {
    if (editedIds.has(txn.id)) return 'bg-blue-50 border-l-4 border-blue-400'
    if (txn.needs_review) return 'bg-yellow-50 border-l-4 border-yellow-400'
    return 'bg-green-50'
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="ml-1 text-gray-300">↕</span>
    return <span className="ml-1 text-blue-600">{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  const thClass = 'px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide cursor-pointer select-none whitespace-nowrap hover:bg-gray-100'

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className={thClass} onClick={() => handleSort('date')}>
              Date<SortIcon field="date" />
            </th>
            <th className={thClass} onClick={() => handleSort('description')}>
              Description<SortIcon field="description" />
            </th>
            <th className={thClass} onClick={() => handleSort('amount')}>
              Amount<SortIcon field="amount" />
            </th>
            <th className={thClass} onClick={() => handleSort('source')}>
              Source<SortIcon field="source" />
            </th>
            <th className={thClass} onClick={() => handleSort('property')}>
              Property<SortIcon field="property" />
            </th>
            <th className={thClass} onClick={() => handleSort('category')}>
              Category<SortIcon field="category" />
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {sorted.map(txn => (
            <tr key={txn.id} className={`${rowClass(txn)} transition-colors`}>
              <td className="px-3 py-2 whitespace-nowrap text-gray-700">{txn.date}</td>
              <td className="px-3 py-2 max-w-xs">
                <span className="block truncate text-gray-800" title={txn.description}>
                  {txn.description}
                </span>
              </td>
              <td className={`px-3 py-2 whitespace-nowrap font-mono font-medium ${txn.amount < 0 ? 'text-red-600' : 'text-green-600'}`}>
                {txn.amount < 0 ? '-' : '+'}${Math.abs(txn.amount).toFixed(2)}
              </td>
              <td className="px-3 py-2 whitespace-nowrap text-gray-600">{txn.source}</td>
              <td className="px-3 py-2 min-w-[150px]">
                <PropertySelect
                  value={txn.property}
                  properties={properties}
                  onChange={val => onUpdate(txn.id, 'property', val)}
                  disabled={saving.has(txn.id)}
                />
              </td>
              <td className="px-3 py-2 min-w-[160px]">
                <CategorySelect
                  value={txn.category}
                  categories={categories}
                  onChange={val => onUpdate(txn.id, 'category', val)}
                  disabled={saving.has(txn.id)}
                />
              </td>
              <td className="px-3 py-2 whitespace-nowrap">
                <div className="flex items-center gap-2">
                  {saving.has(txn.id) ? (
                    <span className="inline-flex items-center gap-1 text-xs text-blue-600">
                      <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                      Saving
                    </span>
                  ) : editedIds.has(txn.id) ? (
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700 font-medium">Edited</span>
                  ) : txn.needs_review ? (
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-yellow-100 text-yellow-700 font-medium">Review</span>
                  ) : (
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700 font-medium">Auto</span>
                  )}
                  <button
                    onClick={() => onDelete(txn.id)}
                    disabled={saving.has(txn.id)}
                    className="text-gray-300 hover:text-red-500 disabled:opacity-30 transition-colors text-xs leading-none"
                    title="Remove from review (personal/irrelevant transaction)"
                  >
                    ✕
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={7} className="px-3 py-8 text-center text-gray-400">
                No transactions loaded
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
