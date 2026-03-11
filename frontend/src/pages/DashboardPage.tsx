import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import type { Transaction } from '../types'
import Toast from '../components/Toast'
import type { ToastMessage } from '../components/Toast'

let toastCounter = 0

export default function DashboardPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(false)
  const [month, setMonth] = useState('')
  const [properties, setProperties] = useState<string[]>([])
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const addToast = useCallback((text: string, type: ToastMessage['type'] = 'info') => {
    setToasts(prev => [...prev, { id: ++toastCounter, text, type }])
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  useEffect(() => {
    api.getProperties()
      .then(r => setProperties(r.properties))
      .catch(e => addToast(`Failed to load properties: ${(e as Error).message}`, 'error'))
  }, [addToast])

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.listTransactions(month || undefined)
      setTransactions(data)
    } catch (e) {
      addToast(`Failed to load transactions: ${(e as Error).message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [month])

  // Aggregate by property
  const byProperty: Record<string, { income: number; expenses: number; count: number }> = {}
  transactions.forEach(t => {
    const key = t.property ?? 'Unassigned'
    if (!byProperty[key]) byProperty[key] = { income: 0, expenses: 0, count: 0 }
    byProperty[key].count++
    if (t.amount > 0) byProperty[key].income += t.amount
    else byProperty[key].expenses += Math.abs(t.amount)
  })

  // Aggregate by category
  const byCategory: Record<string, number> = {}
  transactions
    .filter(t => t.amount < 0)
    .forEach(t => {
      const key = t.category ?? 'Uncategorized'
      byCategory[key] = (byCategory[key] ?? 0) + Math.abs(t.amount)
    })

  const sortedCategories = Object.entries(byCategory).sort((a, b) => b[1] - a[1])
  const totalExpenses = Object.values(byCategory).reduce((s, v) => s + v, 0)

  const allProperties = [...new Set([...properties, ...Object.keys(byProperty)])]

  return (
    <div className="space-y-6">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500">Monthly breakdown by property and category</p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="month"
            value={month}
            onChange={e => setMonth(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <button
            onClick={load}
            disabled={loading}
            className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {loading && transactions.length === 0 ? (
        <div className="text-center py-12 text-gray-400">Loading transactions...</div>
      ) : transactions.length === 0 ? (
        <div className="text-center py-12 text-gray-400 bg-white rounded-xl border border-gray-200">
          <p className="font-medium">No transactions found</p>
          <p className="text-sm mt-1">Upload CSVs on the Review page first</p>
        </div>
      ) : (
        <>
          {/* Property breakdown */}
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <h2 className="font-semibold text-gray-800">By Property</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-100 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Property</th>
                    <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600 uppercase">Income</th>
                    <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600 uppercase">Expenses</th>
                    <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600 uppercase">Net</th>
                    <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600 uppercase">Txns</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {allProperties.map(prop => {
                    const d = byProperty[prop] ?? { income: 0, expenses: 0, count: 0 }
                    const net = d.income - d.expenses
                    return (
                      <tr key={prop} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-medium text-gray-800">{prop}</td>
                        <td className="px-4 py-2 text-right text-green-600">${d.income.toFixed(2)}</td>
                        <td className="px-4 py-2 text-right text-red-600">${d.expenses.toFixed(2)}</td>
                        <td className={`px-4 py-2 text-right font-semibold ${net >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {net >= 0 ? '+' : '-'}${Math.abs(net).toFixed(2)}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-500">{d.count}</td>
                      </tr>
                    )
                  })}
                </tbody>
                <tfoot className="bg-gray-50 border-t-2 border-gray-200">
                  <tr>
                    <td className="px-4 py-2 font-bold text-gray-800">Total</td>
                    <td className="px-4 py-2 text-right font-bold text-green-600">
                      ${Object.values(byProperty).reduce((s, d) => s + d.income, 0).toFixed(2)}
                    </td>
                    <td className="px-4 py-2 text-right font-bold text-red-600">
                      ${Object.values(byProperty).reduce((s, d) => s + d.expenses, 0).toFixed(2)}
                    </td>
                    <td className="px-4 py-2 text-right font-bold">
                      {(() => {
                        const net = Object.values(byProperty).reduce((s, d) => s + d.income - d.expenses, 0)
                        return <span className={net >= 0 ? 'text-green-600' : 'text-red-600'}>{net >= 0 ? '+' : '-'}${Math.abs(net).toFixed(2)}</span>
                      })()}
                    </td>
                    <td className="px-4 py-2 text-right font-bold text-gray-600">{transactions.length}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Category breakdown */}
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <h2 className="font-semibold text-gray-800">Expenses by Category</h2>
            </div>
            {sortedCategories.length === 0 ? (
              <p className="px-4 py-6 text-gray-400 text-sm text-center">No expense data</p>
            ) : (
              <div className="p-4 space-y-2">
                {sortedCategories.map(([cat, amt]) => {
                  const pct = totalExpenses > 0 ? (amt / totalExpenses) * 100 : 0
                  return (
                    <div key={cat}>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-gray-700 font-medium">{cat}</span>
                        <span className="text-gray-600">${amt.toFixed(2)} <span className="text-gray-400 text-xs">({pct.toFixed(1)}%)</span></span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
