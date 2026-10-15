import type { AgentName } from './types'

// Each agent gets its own color, glyph, and "voice" so you can tell who's
// talking at a glance, even in the scrolling feed.
export interface Persona {
  name: AgentName
  title: string
  glyph: string
  color: string
  role: string
  voice: 'command' | 'ledger' | 'plain' | 'warm'
}

export const PERSONAS: Record<AgentName, Persona> = {
  boss: { name: 'boss', title: 'Boss', glyph: '♛', color: '#ff2d8a', role: 'Calls the shots', voice: 'command' },
  inventory: { name: 'inventory', title: 'Inventory', glyph: '▦', color: '#b69cff', role: 'Counts the shelves', voice: 'plain' },
  accounting: { name: 'accounting', title: 'Accounting', glyph: '$', color: '#ffd27a', role: 'Guards the till', voice: 'ledger' },
  facilities: { name: 'facilities', title: 'Facilities', glyph: '⌂', color: '#6fe3ff', role: 'Keeps the lights on', voice: 'plain' },
  customer_service: {
    name: 'customer_service',
    title: 'Customer Service',
    glyph: '✉',
    color: '#ff8a7a',
    role: 'Writes to the people',
    voice: 'warm',
  },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']
export const SPECIALISTS: AgentName[] = AGENT_ORDER.slice(1)

export const isAgent = (name: string): name is AgentName => name in PERSONAS
export const persona = (name: string): Persona | undefined => (isAgent(name) ? PERSONAS[name] : undefined)
export const titleOf = (name: string) => persona(name)?.title ?? name

type Args = Record<string, unknown>
const money = (n: unknown) => (typeof n === 'number' ? `$${n.toLocaleString()}` : '')

// Plain-English verbs for each MCP tool, so the board says what an agent is
// doing instead of showing raw function names.
const TOOL_VERBS: Record<string, (a: Args) => string> = {
  list_tickets: () => 'Scanning the ticket board',
  get_ticket: (a) => `Reading ticket #${a.ticket_id}`,
  check_stock: (a) => `Counting ${a.sku} · ${a.size}${a.qty_needed ? ` (needs ${a.qty_needed})` : ''}`,
  check_vendor_status: (a) => (a.vendor_id ? `Checking in with vendor #${a.vendor_id}` : 'Checking every vendor'),
  get_lease: (a) => `Pulling lease #${a.lease_id}`,
  get_cash_position: () => 'Peeking at the till',
  list_payment_requests: () => 'Reviewing what needs signatures',
  quote_discount: (a) => `Pricing ${a.qty}× ${a.sku} at ${a.discount_pct ?? 0}% off`,
  request_payment: (a) => `Asking a human to sign for ${String(a.kind).replace('_', ' ')} #${a.ref_id}`,
  create_purchase_order: (a) => `Drafting a PO: ${a.qty}× ${a.sku} ${a.size}`,
  draft_customer_message: (a) => `Writing to ${a.recipient}`,
  update_ticket: (a) => `Marking #${a.ticket_id} ${String(a.status).replaceAll('_', ' ')}`,
  delegate: (a) => `Handing off to ${titleOf(String(a.to))}`,
  final_result: () => 'Filing the report',
  list_purchase_orders: () => 'Looking over purchase orders',
}

export function describeTool(tool: string, args: Args | string): string {
  const verb = TOOL_VERBS[tool]
  if (!verb) return tool.replaceAll('_', ' ')
  return verb(typeof args === 'string' ? {} : args)
}

export const HIDDEN_TOOLS = new Set(['final_result', 'delegate'])

export const KIND_LABEL: Record<string, string> = {
  invoice: 'Vendor invoice',
  rent: 'Rent',
  purchase_order: 'Purchase order',
}

export { money }
