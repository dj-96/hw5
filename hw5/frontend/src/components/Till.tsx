import { useEffect, useRef, useState } from 'react'
import { KIND_LABEL } from '../agents'
import { useTween } from '../hooks'
import type { Cash, PaymentRequest } from '../types'

const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export default function Till({ cash, paid }: { cash: Cash | null; paid: PaymentRequest[] }) {
  const balance = cash?.balance ?? 0
  const shown = useTween(cash ? balance : null)
  const prev = useRef<number | null>(null)
  const [drop, setDrop] = useState<{ id: number; amount: number } | null>(null)

  // When the balance falls, flash the till and float the amount that left.
  useEffect(() => {
    if (cash === null) return
    if (prev.current !== null && balance < prev.current) {
      setDrop({ id: Date.now(), amount: prev.current - balance })
      const id = window.setTimeout(() => setDrop(null), 2600)
      prev.current = balance
      return () => window.clearTimeout(id)
    }
    prev.current = balance
  }, [balance, cash])

  const after = cash?.balance_after_pending ?? 0
  return (
    <section className={`till ${drop ? 'is-dropping' : ''}`} aria-label="Checking account">
      <div className="till-head">
        <span>Checking</span>
        <span className="till-date">as of {cash?.shop_today ?? '—'}</span>
      </div>
      <div className="till-display" aria-live="polite">
        <span className="till-digits">{cash ? usd(shown) : '$—'}</span>
        {drop && (
          <span key={drop.id} className="till-drop">
            −{usd(drop.amount)}
          </span>
        )}
      </div>
      <div className="till-row">
        <div>
          <span className="till-k">Waiting on signatures</span>
          <span className="till-v">{usd(cash?.pending_total ?? 0)}</span>
        </div>
        <div>
          <span className="till-k">Left if all signed</span>
          <span className={`till-v ${after < 0 ? 'is-neg' : after < 300 ? 'is-low' : ''}`}>{usd(after)}</span>
        </div>
      </div>
      <div className="receipt">
        <div className="receipt-head">Paid out</div>
        {paid.length === 0 && <div className="receipt-empty">Nothing yet this shift.</div>}
        {paid.map((p) => (
          <div className="receipt-line" key={p.id}>
            <span>
              {KIND_LABEL[p.kind]} #{p.ref_id}
              <small>signed {p.decided_by}</small>
            </span>
            <span>−{usd(p.amount)}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
