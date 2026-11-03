export type Role = 'owner' | 'member'

export interface HouseholdMember {
  user_id: string
  email: string | null
  role: Role
  joined_at: string
}

export interface Household {
  id: string
  name: string
  invite_code: string
  role: Role
  created_at: string
  members: HouseholdMember[]
}

export type ReceiptStatus = 'processing' | 'ready' | 'failed'
export type TagSource = 'rule' | 'ai' | 'user'

export interface ReceiptSummary {
  id: string
  title: string | null
  merchant: string | null
  amount: string | null
  currency: string
  bill_date: string | null
  bill_type: string | null
  status: ReceiptStatus
  ai_skipped: boolean
  failure_reason: string | null
  created_at: string
  thumbnail_url: string | null
}

export interface ReceiptPage {
  page_no: number
  mime_type: string
  size_bytes: number
  url: string | null
}

export interface ReceiptTag {
  tag_id: string
  slug: string
  label_en: string
  label_hi: string | null
  label_mr: string | null
  kind: 'bill_type' | 'merchant' | 'custom'
  source: TagSource
  confidence: number | null
}

export interface ReceiptDetail extends ReceiptSummary {
  language: string | null
  raw_text: string | null
  extracted: Record<string, unknown> | null
  pages: ReceiptPage[]
  tags: ReceiptTag[]
  processed_at: string | null
}

export interface ReceiptUploadResponse {
  id: string
  status: ReceiptStatus
}

export interface ReceiptUpdateInput {
  title?: string | null
  merchant?: string | null
  amount?: string | null
  bill_date?: string | null
}

export interface ReceiptSearchResponse {
  items: ReceiptSummary[]
  total: number
  page: number
  page_size: number
}

export interface TagView {
  id: string
  slug: string
  label_en: string
  label_hi: string | null
  label_mr: string | null
  kind: 'bill_type' | 'merchant' | 'custom'
  keywords: string[]
  count: number
}
