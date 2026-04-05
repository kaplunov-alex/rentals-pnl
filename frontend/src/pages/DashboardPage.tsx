import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import type { SheetTransaction } from '../types'
import Toast from '../components/Toast'
import type { ToastMessage } from '../components/Toast'
import { useOverview } from '../context/OverviewContext'

let toastCounter = 0

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

const currentMonthValue = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function SummaryCard({
  title, value, subtitle, icon, valueColor = 'text-gray-900', loading = false,
}: {
  title: string
  value: string
  subtitle?: string
  icon: React.ReactNode
  valueColor?: string
  loading?: boolean
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-start justify-between">
      <div className="flex-1">
        <p className="text-sm text-gray-500 mb-1">{title}</p>
        {loading ? (
          <div className="h-7 bg-gray-100 rounded w-2/3 animate-pulse mt-1" />
        ) : (
          <p className={`text-2xl font-bold ${valueColor}`}>{value}</p>
        )}
        {subtitle && !loading && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
      </div>
      <div className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 bg-gray-50 ml-3">
        {icon}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { overview, loading: overviewLoading, error: overviewError } = useOverview()
  const [sheetTxns, setSheetTxns] = useState<SheetTransaction[]>([])
  const [txnsLoading, setTxnsLoading] = useState(false)
  const [month, setMonth] = useState(currentMonthValue())
  const [selectedProperty, setSelectedProperty] = useState('all')
  const [properties, setProperties] = useState<string[]>([])
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const addToast = useCallback((text: string, type: ToastMessage['type'] = 'info') => {
    setToasts(prev => [...prev, { id: ++toastCounter, text, type }])
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  useEffect(() => {
    api.getProperties().then(r => setProperties(r.properties)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!month) return
    setTxnsLoading(true)
    api.getSheetTransactions(month, selectedProperty)
      .then(setSheetTxns)
      .catch(e => addToast(`Failed to load transactions: ${(e as Error).message}`, 'error'))
      .finally(() => setTxnsLoading(false))
  }, [month, selectedProperty, addToast])

  const monthLabel = month
    ? new Date(month + '-02').toLocaleString('en-US', { month: 'long', year: 'numeric' })
    : ''

  return (
    <div className="p-6 space-y-6">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Financial summary and transaction history for your properties.</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedProperty}
            onChange={e => setSelectedProperty(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value="all">All Properties</option>
            {properties.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <input
            type="month"
            value={month}
            onChange={e => setMonth(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
      </div>

      {/* Overview error banner */}
      {overviewError && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          <span className="font-medium">Could not load overview from Google Sheets:</span> {overviewError}
        </div>
      )}

      {/* Summary cards — from Google Sheets */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <SummaryCard
          title="Total Income"
          value={overview ? fmt(overview.total_income) : '—'}
          loading={overviewLoading}
          valueColor="text-green-600"
          icon={
            <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 17l9.2-9.2M17 17V7H7" />
            </svg>
          }
        />
        <SummaryCard
          title="Total Expenses"
          value={overview ? fmt(overview.total_expenses) : '—'}
          loading={overviewLoading}
          icon={
            <svg className="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 7l-9.2 9.2M7 7v10h10" />
            </svg>
          }
        />
        <SummaryCard
          title="Net Cash Flow"
          value={overview ? fmt(overview.net_cash_flow) : '—'}
          subtitle="From Google Sheets"
          loading={overviewLoading}
          valueColor={!overview ? 'text-gray-900' : overview.net_cash_flow >= 0 ? 'text-gray-900' : 'text-red-600'}
          icon={
            <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          }
        />
      </div>

      {/* Transactions from property sheets */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-800">Transactions</h2>
            <p className="text-xs text-gray-400 mt-0.5">{monthLabel}{sheetTxns.length > 0 ? ` · ${sheetTxns.length} rows` : ''}</p>
          </div>
        </div>

        {txnsLoading ? (
          <div className="px-5 py-10 text-sm text-gray-400 text-center">Loading…</div>
        ) : sheetTxns.length === 0 ? (
          <p className="px-5 py-10 text-sm text-gray-400 text-center">
            No transactions found in the property sheets for this period.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm divide-y divide-gray-100">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Vendor</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Category</th>
                  {selectedProperty === 'all' && (
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Property</th>
                  )}
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Source</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Comments</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {sheetTxns.map((t, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                      {new Date(t.date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })}
                    </td>
                    <td className="px-4 py-3 font-medium text-gray-900 max-w-[200px] truncate">{t.vendor}</td>
                    <td className="px-4 py-3">
                      {t.category && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 font-medium">{t.category}</span>
                      )}
                    </td>
                    {selectedProperty === 'all' && (
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">{t.property}</td>
                    )}
                    <td className="px-4 py-3 text-gray-400 text-xs">{t.source}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs max-w-[160px] truncate">{t.comments}</td>
                    <td className={`px-4 py-3 text-right font-semibold whitespace-nowrap ${t.amount >= 0 ? 'text-green-600' : 'text-gray-900'}`}>
                      {t.amount >= 0 ? '+' : ''}{fmt(t.amount)}
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
