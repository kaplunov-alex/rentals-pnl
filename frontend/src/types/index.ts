export interface Transaction {
  id: string
  date: string
  description: string
  amount: number
  source: string
  property: string | null
  category: string | null
  txn_type: string
  needs_review: boolean
  raw_file: string
}

export interface UploadResponse {
  transactions: Transaction[]
  total: number
  auto_categorized: number
  needs_review: number
}

export interface PipelineRunResponse {
  status: string
  transactions_written: number
  details: Record<string, number>
  message: string
}

export interface PipelineStatusResponse {
  running: boolean
  last_run: Record<string, unknown> | null
}

export interface VendorMapping {
  key: string
  property: string
  category: string
}

export interface CategoriesResponse {
  categories: string[]
  income_categories: string[]
}

export interface BulkUpdateItem {
  id: string
  property?: string
  category?: string
}

export interface OverviewData {
  total_income: number
  total_expenses: number
  net_cash_flow: number
}
