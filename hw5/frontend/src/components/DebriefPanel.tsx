import type { CSSProperties } from 'react'
import { PERSONAS } from '../agents'
import type { Debrief } from '../floor'

export default function DebriefPanel({ ticketId, debrief }: { ticketId: number; debrief: Debrief[] }) {
  return (
    <section className="debrief" aria-label={`What each agent did on ticket ${ticketId}`}>
      <div className="panel-head">
        <h3>Debrief · #{ticketId}</h3>
        <span className="panel-sub">{debrief.length} agents worked this ticket</span>
      </div>
      <div className="debrief-grid">
        {debrief.map((d) => {
          const p = PERSONAS[d.agent]
          return (
            <article
              key={d.agent}
              className={`debrief-card voice-${p.voice} ${d.agent === 'boss' ? 'is-boss' : ''}`}
              style={{ '--agent': p.color } as CSSProperties}
            >
              <header>
                <span className="debrief-glyph" aria-hidden>
                  {p.glyph}
                </span>
                <span className="debrief-name">{p.title}</span>
                {d.status && <span className="debrief-status">{d.status.replaceAll('_', ' ')}</span>}
              </header>
              <p className="debrief-headline">{d.headline}</p>
              {d.points.length > 0 && (
                <ul className="debrief-points">
                  {d.points.map((pt, i) => (
                    <li key={i}>{pt}</li>
                  ))}
                </ul>
              )}
              {d.needs.length > 0 && (
                <div className="debrief-needs">
                  <span>Needs a human</span>
                  <ul>
                    {d.needs.map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
