import type { AgentEvent, Cash, PaymentRequest, PurchaseOrder, RunInfo, Ticket, TicketDetail } from './types'

// FastAPI from Problem 7. uvicorn serves plain http unless you give it a cert,
// so the default is http://localhost:8000. Override in frontend/.env.local.
export const API_BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_BASE + path, { headers: { 'Content-Type': 'application/json' }, ...init })
  } catch {
    throw new ApiError(`Can't reach the backend at ${API_BASE}. Is uvicorn running?`, 0)
  }
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(typeof body.detail === 'string' ? body.detail : res.statusText, res.status)
  return body as T
}

const post = <T>(path: string, data?: unknown) =>
  req<T>(path, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) })

export const api = {
  health: () => req<{ ok: boolean; model: string; gateway: string; active_run: string | null }>('/api/health'),
  tickets: () => req<{ shop_today: string; tickets: Ticket[] }>('/api/tickets'),
  ticket: (id: number) => req<TicketDetail>(`/api/tickets/${id}`),
  run: (id: number) => post<RunInfo>(`/api/tickets/${id}/run`),
  runStatus: (sessionId: string) => req<RunInfo>(`/api/runs/${sessionId}`),
  events: (sessionId: string) =>
    req<{ total: number; events: AgentEvent[] }>(`/api/events?limit=500&session_id=${sessionId}`),
  cash: () => req<Cash>('/api/cash'),
  payments: (status: 'pending' | 'approved' | 'denied') =>
    req<{ balance: number; count: number; requests: PaymentRequest[] }>(`/api/payments?status=${status}`),
  purchaseOrders: () => req<{ count: number; purchase_orders: PurchaseOrder[] }>('/api/purchase-orders'),
  approvePayment: (id: number, by: string) =>
    post<{ ok: boolean; amount: number; new_balance: number }>(`/api/payments/${id}/approve`, { approved_by: by }),
  denyPayment: (id: number, by: string, note = '') =>
    post<{ ok: boolean }>(`/api/payments/${id}/deny`, { denied_by: by, note }),
  approvePurchase: (id: number, by: string) =>
    post<{ ok: boolean; amount: number; new_balance: number; po_eta?: string }>(`/api/purchase-orders/${id}/approve`, {
      approved_by: by,
    }),
  reset: () => post<{ ok: boolean }>('/api/reset'),
}
