const BASE = '/api'

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  // Transactions
  uploadCSVs: (files: File[]) => {
    const form = new FormData()
    files.forEach(f => form.append('files', f))
    return req<import('../types').UploadResponse>('/transactions/upload', { method: 'POST', body: form })
  },
  listTransactions: (month?: string) =>
    req<import('../types').Transaction[]>(`/transactions${month ? `?month=${month}` : ''}`),
  updateTransaction: (id: string, data: { property?: string; category?: string; comments?: string }) =>
    req<import('../types').Transaction>(`/transactions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  deleteTransaction: (id: string) =>
    req<void>(`/transactions/${id}`, { method: 'DELETE' }),
  bulkUpdate: (updates: import('../types').BulkUpdateItem[]) =>
    req<import('../types').Transaction[]>('/transactions/bulk-update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ updates }),
    }),

  // Pipeline
  runPipeline: (month?: string) =>
    req<import('../types').PipelineRunResponse>('/pipeline/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ month: month ?? null }),
    }),
  pipelineStatus: () => req<import('../types').PipelineStatusResponse>('/pipeline/status'),

  // Config
  getVendorMappings: () => req<import('../types').VendorMapping[]>('/config/vendor-mappings'),
  addVendorMapping: (data: import('../types').VendorMapping) =>
    req<import('../types').VendorMapping>('/config/vendor-mappings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  deleteVendorMapping: (key: string) =>
    req<void>(`/config/vendor-mappings/${encodeURIComponent(key)}`, { method: 'DELETE' }),
  getCategories: () => req<import('../types').CategoriesResponse>('/config/categories'),
  getProperties: () => req<{ properties: string[] }>('/config/properties'),
  getOverview: () => req<import('../types').OverviewData>('/overview'),
  getSheetTransactions: (month: string, property?: string) =>
    req<import('../types').SheetTransaction[]>(
      `/sheets/transactions?month=${month}${property && property !== 'all' ? `&property=${encodeURIComponent(property)}` : ''}`
    ),
}
