import { useState, type CSSProperties } from 'react'
import { KIND_LABEL, persona } from '../agents'
import type { BossReport, PaymentRequest, PurchaseOrder } from '../types'

const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

interface Props {
  pending: PaymentRequest[]
  pos: PurchaseOrder[]
  report: BossReport | null
  selectedId: number | null
  signer: string
  onApprovePayment: (r: PaymentRequest) => Promise<boolean>
  onApprovePurchase: (po: PurchaseOrder) => Promise<boolean>
  onDeny: (r: PaymentRequest) => void
}

export default function SignatureTray(props: Props) {
  const { pending, pos, report, selectedId, signer } = props
  const [stamped, setStamped] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  // Show requests in the Boss's recommended order when we have one.
  const priority = new Map(report?.approval_queue?.map((a) => [a.request_id, a.priority]) ?? [])
  const queue = [...pending].sort((a, b) => (priority.get(a.id) ?? 99) - (priority.get(b.id) ?? 99) || a.id - b.id)
  const drafts = pos.filter((p) => p.status === 'draft' && !pending.some((r) => r.kind === 'purchase_order' && r.ref_id === p.id))

  const run = async (key: string, fn: () => Promise<boolean>) => {
    setBusy(key)
    const ok = await fn()
    setBusy(null)
    if (ok) {
      setStamped(key)
      window.setTimeout(() => setStamped(null), 1400)
    }
  }

  const empty = queue.length === 0 && drafts.length === 0
  return (
    <section className="tray" aria-label="Needs your signature">
      <div className="panel-head">
        <h3>Needs your signature</h3>
        <span className="panel-sub">{empty ? 'All clear' : `${queue.length + drafts.length} waiting`}</span>
      </div>
      {!signer.trim() && !empty && <p className="tray-hint">Type your name in “Signing as” at the top to approve.</p>}
      {empty && <p className="tray-empty">Agents prepare payments here. Only a person can sign them.</p>}

      {queue.map((r) => {
        const key = `pay-${r.id}`
        const who = persona(r.requested_by)
        const rank = priority.get(r.id)
        return (
          <article
            key={r.id}
            className={`slip ${r.ticket_id === selectedId ? 'is-here' : ''} ${stamped === key ? 'is-stamped' : ''}`}
            style={{ '--agent': who?.color ?? '#ff2d8a' } as CSSProperties}
          >
            <div className="slip-top">
              <span className="slip-kind">{KIND_LABEL[r.kind]}</span>
              {rank && <span className="slip-rank">Boss says #{rank}</span>}
              {r.ticket_id && <span className="slip-ticket">#{r.ticket_id}</span>}
            </div>
            <div className="slip-amount">{usd(r.amount)}</div>
            <p className="slip-reason">{r.reason}</p>
            <div className="slip-by">
              prepared by <b>{who?.title ?? r.requested_by}</b> · request #{r.id}
            </div>
            <div className="slip-actions">
              <button className="btn-sign" disabled={busy !== null || !signer.trim()} onClick={() => run(key, () => props.onApprovePayment(r))}>
                {busy === key ? 'Signing…' : 'Approve & pay'}
              </button>
              <button className="btn-text" disabled={busy !== null || !signer.trim()} onClick={() => props.onDeny(r)}>
                Deny
              </button>
            </div>
            <span className="slip-stamp" aria-hidden>
              Paid
            </span>
          </article>
        )
      })}

      {drafts.map((po) => {
        const key = `po-${po.id}`
        return (
          <article
            key={key}
            className={`slip is-po ${po.ticket_id === selectedId ? 'is-here' : ''} ${stamped === key ? 'is-stamped' : ''}`}
            style={{ '--agent': persona(po.created_by)?.color ?? '#b69cff' } as CSSProperties}
          >
            <div className="slip-top">
              <span className="slip-kind">Purchase order</span>
              {po.ticket_id && <span className="slip-ticket">#{po.ticket_id}</span>}
            </div>
            <div className="slip-amount">{usd(po.total)}</div>
            <p className="slip-reason">
              {po.qty}× {po.sku} · {po.size} from {po.vendor_name} at {usd(po.unit_cost)} each
            </p>
            <div className="slip-by">
              drafted by <b>{persona(po.created_by)?.title ?? po.created_by}</b> · PO #{po.id}
            </div>
            <div className="slip-actions">
              <button className="btn-sign" disabled={busy !== null || !signer.trim()} onClick={() => run(key, () => props.onApprovePurchase(po))}>
                {busy === key ? 'Signing…' : 'Approve purchase'}
              </button>
            </div>
            <span className="slip-stamp" aria-hidden>
              Ordered
            </span>
          </article>
        )
      })}
    </section>
  )
}
