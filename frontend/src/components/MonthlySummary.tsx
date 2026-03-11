import type { Transaction } from '../types'

interface Props {
  transactions: Transaction[]
  editedIds: Set<string>
}

export default function MonthlySummary({ transactions, editedIds }: Props) {
  const total = transactions.length
  const needsReview = transactions.filter(t => t.needs_review && !editedIds.has(t.id)).length
  const edited = editedIds.size
  const autoCategorized = total - needsReview - edited

  const totalExpenses = transactions
    .filter(t => t.amount < 0)
    .reduce((sum, t) => sum + Math.abs(t.amount), 0)

  const totalIncome = transactions
    .filter(t => t.amount > 0)
    .reduce((sum, t) => sum + t.amount, 0)

  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
      <StatCard label="Total Transactions" value={total.toString()} color="blue" />
      <StatCard label="Auto-categorized" value={autoCategorized.toString()} color="green" />
      <StatCard label="Needs Review" value={needsReview.toString()} color="yellow" />
      <StatCard label="Manually Edited" value={edited.toString()} color="indigo" />
      <div className="sm:col-span-1 col-span-2">
        <div className="bg-white rounded-lg border border-gray-200 p-3">
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Net</p>
          <p className={`text-xl font-bold mt-1 ${(totalIncome - totalExpenses) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {(totalIncome - totalExpenses) >= 0 ? '+' : '-'}${Math.abs(totalIncome - totalExpenses).toFixed(2)}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">
            In: ${totalIncome.toFixed(2)} | Out: ${totalExpenses.toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  const colors: Record<string, string> = {
    blue: 'text-blue-600 bg-blue-50',
    green: 'text-green-600 bg-green-50',
    yellow: 'text-yellow-600 bg-yellow-50',
    indigo: 'text-indigo-600 bg-indigo-50',
  }
  return (
    <div className={`rounded-lg border border-gray-200 p-3 ${colors[color] ?? ''}`}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  )
}
