// Shapes returned by the FastAPI backend (backend/main.py).

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type RunState = 'running' | 'done' | 'failed' | 'interrupted'

export interface LastRun {
  session_id: string
  state: RunState
  started_at: string
  ended_at?: string
}

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  status: string
  created_at: string
  state: 'open' | 'resolved'
  last_run: LastRun | null
}

export interface TicketDetail {
  found: boolean
  shop_today: string
  ticket: Ticket & { sku: string | null; size: string | null; qty: number | null; notes: string | null }
}

export interface ToolCall {
  tool: string
  call_id?: string
  args: Record<string, unknown> | string
}

export interface ToolResult {
  tool: string
  call_id?: string
  content: unknown
}

export interface AgentEvent {
  ts: string
  session_id: string | null
  agent: string
  step: string
  step_no: number | null
  chain: string
  said?: string | null
  tools?: string[]
  tool_calls?: ToolCall[]
  tool_results?: ToolResult[]
  retries?: { tool: string; error: string }[] | null
  to?: string
  allowed?: boolean
  blocked_reason?: string | null
  output?: unknown
  error?: string
  detail?: Record<string, unknown>
}

export interface Cash {
  account: string
  balance: number
  shop_today: string
  pending_total: number
  balance_after_pending: number
}

export interface PaymentRequest {
  id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number
  amount: number
  ticket_id: number | null
  reason: string
  requested_by: string
  status: 'pending' | 'approved' | 'denied'
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  created_at: string
}

export interface PurchaseOrder {
  id: number
  vendor_id: number
  vendor_name: string
  sku: string
  size: string
  qty: number
  unit_cost: number
  total: number
  ticket_id: number | null
  status: 'draft' | 'ordered'
  eta: string | null
  created_by: string
  payment_request_id: number | null
}

export interface TicketDecision {
  ticket_id: number
  decision: string
  status: string
  handled_by: AgentName[]
  rationale: string
  human_actions: string[]
}

export interface ApprovalItem {
  request_id: number
  kind: PaymentRequest['kind']
  amount: number
  why: string
  priority: number
}

export interface BossReport {
  tickets: TicketDecision[]
  approval_queue: ApprovalItem[]
  cash_note: string
  open_risks: string[]
}

export interface SpecialistReport {
  agent: AgentName
  ticket_ids: number[]
  summary: string
  facts: { tool: string; detail: string }[]
  actions_taken: string[]
  payment_request_ids: number[]
  purchase_order_ids: number[]
  draft_ids: number[]
  needs_human: string[]
  recommended_status: string | null
}

export interface RunInfo {
  session_id: string
  ticket_id: number
  status: 'running' | 'done' | 'failed'
  model: string
  gateway: string
  started_at: string
  finished_at?: string
  report: BossReport | null
  error: string | null
}
