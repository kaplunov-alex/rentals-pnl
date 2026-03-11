import type { PipelineRunResponse, PipelineStatusResponse } from '../types'

interface Props {
  status: PipelineStatusResponse | null
  lastRun: PipelineRunResponse | null
  onRun: () => void
  loading: boolean
  month: string
  onMonthChange: (m: string) => void
}

export default function PipelineStatus({ status, lastRun, onRun, loading, month, onMonthChange }: Props) {
  const isRunning = status?.running ?? false

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <h2 className="font-semibold text-gray-800 mb-3">Push to Google Sheets</h2>
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Month (optional override)</label>
          <input
            type="month"
            value={month}
            onChange={e => onMonthChange(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
        <button
          onClick={onRun}
          disabled={loading || isRunning}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium text-sm hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {(loading || isRunning) && (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          )}
          {loading || isRunning ? 'Running...' : 'Push to Sheets'}
        </button>
      </div>

      {lastRun && (
        <div className={`mt-4 p-3 rounded-lg text-sm ${lastRun.status === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
          <p className={`font-medium ${lastRun.status === 'success' ? 'text-green-700' : 'text-red-700'}`}>
            {lastRun.status === 'success' ? 'Pipeline completed' : 'Pipeline error'}
          </p>
          <p className="text-gray-600 mt-1">{lastRun.message}</p>
          {lastRun.transactions_written > 0 && (
            <p className="text-gray-500 text-xs mt-1">
              {lastRun.transactions_written} transactions written
              {Object.entries(lastRun.details).length > 0 && (
                <> ({Object.entries(lastRun.details).map(([k, v]) => `${k}: ${v}`).join(', ')})</>
              )}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
