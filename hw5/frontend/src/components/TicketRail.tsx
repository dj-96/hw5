import type { Ticket } from '../types'

const TYPE_ICON: Record<string, string> = { customer_order: '👕', rent_notice: '🏠', price_override: '🏷️' }
const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  onSelect: (id: number) => void
  liveTicketId: number | null
  toSign: Record<number, number>
}

export default function TicketRail({ tickets, selectedId, onSelect, liveTicketId, toSign }: Props) {
  const open = tickets.filter((t) => t.state === 'open').length
  return (
    <nav className="rail" aria-label="Tickets">
      <div className="rail-head">
        <h2>On the spike</h2>
        <span className="rail-count">
          {open} open · {tickets.length - open} resolved
        </span>
      </div>

      <ul className="stubs">
        {tickets.map((t) => {
          const live = liveTicketId === t.id
          const resolved = t.state === 'resolved'
          return (
            <li key={t.id}>
              <button
                className={`stub ${selectedId === t.id ? 'is-selected' : ''} ${resolved ? 'is-resolved' : ''} ${live ? 'is-live' : ''}`}
                onClick={() => onSelect(t.id)}
                aria-current={selectedId === t.id}
              >
                <span className="stub-top">
                  <span className="stub-no">#{t.id}</span>
                  <span className="stub-icon" aria-hidden>
                    {TYPE_ICON[t.type] ?? '📄'}
                  </span>
                </span>
                <span className="stub-type">{TYPE_LABEL[t.type] ?? t.type}</span>
                <span className="stub-subject">{t.subject}</span>
                <span className="stub-from">from {t.requester}</span>
                <span className="stub-foot">
                  {live ? (
                    <span className="pill pill-live">
                      <span className="pulse-dot" aria-hidden /> Team working
                    </span>
                  ) : resolved ? (
                    <span className="pill pill-done">
                      Resolved · {toSign[t.id] ? `${toSign[t.id]} to sign` : 'signed off'}
                    </span>
                  ) : t.last_run?.state === 'failed' || t.last_run?.state === 'interrupted' ? (
                    <span className="pill pill-bad">Run {t.last_run.state}</span>
                  ) : (
                    <span className="pill">Open</span>
                  )}
                </span>
                {resolved && !live && (
                  <span className="stamp" aria-hidden>
                    Resolved
                  </span>
                )}
              </button>
            </li>
          )
        })}
        {tickets.length === 0 && <li className="rail-empty">No tickets yet. Is the backend running?</li>}
      </ul>
    </nav>
  )
}
