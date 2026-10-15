import { elapsed } from '../floor'
import { useNow } from '../hooks'
import type { Ticket, TicketDetail } from '../types'

interface Props {
  ticket: Ticket | null
  detail: TicketDetail | null
  running: boolean
  liveHere: boolean
  otherLive: number | null
  startedAt: string | null
  endedAt: string | null
  onDispatch: () => void
}

export default function TicketHero({ ticket, detail, running, liveHere, otherLive, startedAt, endedAt, onDispatch }: Props) {
  const now = useNow(liveHere)
  if (!ticket) return <div className="hero hero-empty">Pick a ticket from the spike.</div>

  const t = detail?.ticket
  const ask = t?.sku ? `${t.qty ?? 1}× ${t.sku}${t.size ? ` · size ${t.size}` : ''}` : null
  const resolved = ticket.state === 'resolved'
  const label = liveHere ? 'Team on it' : resolved ? 'Run the team again' : 'Send in the team'

  return (
    <div className={`hero ${liveHere ? 'is-live' : ''}`}>
      <div className="hero-text">
        <div className="hero-kicker">
          Ticket #{ticket.id} · {ticket.requester}
        </div>
        <h2 className="hero-title">{ticket.subject}</h2>
        <p className="hero-notes">
          {ask && <span className="hero-ask">{ask}</span>}
          {(t?.notes ?? '').split('\n')[0]}
        </p>
      </div>

      <div className="hero-action">
        <button className="btn-dispatch" onClick={onDispatch} disabled={running}>
          <span className="btn-dispatch-label">{label}</span>
          <span className="btn-dispatch-arrow" aria-hidden>
            {liveHere ? '' : '▸'}
          </span>
        </button>
        <div className="hero-clock" aria-live="polite">
          {liveHere && <>Running {elapsed(startedAt, now)}</>}
          {!liveHere && endedAt && <>Last run took {elapsed(startedAt, endedAt)}</>}
          {otherLive && <>Team is busy on #{otherLive}</>}
        </div>
      </div>
    </div>
  )
}
