import type { CSSProperties } from 'react'
import { AGENT_ORDER, PERSONAS } from '../agents'
import type { Floor, Station } from '../floor'
import type { AgentName } from '../types'

// Where each station sits on the floor (percent of the stage). The Boss is
// up front; the four specialists sit in a row below.
const SPOTS: Record<AgentName, { x: number; y: number }> = {
  boss: { x: 50, y: 27 },
  inventory: { x: 13, y: 76 },
  accounting: { x: 38, y: 76 },
  facilities: { x: 62, y: 76 },
  customer_service: { x: 87, y: 76 },
}

const STATUS_WORD: Record<Station['status'], string> = {
  idle: 'Idle',
  thinking: 'Thinking',
  working: 'Working',
  waiting: 'Waiting',
  done: 'Done',
  error: 'Error',
}

function edgePath(from: AgentName, to: AgentName) {
  const a = SPOTS[from]
  const b = SPOTS[to]
  // Specialist-to-specialist hand-offs arc above the row so they don't overlap.
  const sameRow = Math.abs(a.y - b.y) < 5
  const cx = (a.x + b.x) / 2
  const cy = sameRow ? a.y - 22 - Math.abs(a.x - b.x) * 0.15 : (a.y + b.y) / 2
  return `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`
}

export default function AgentFloor({ floor, live }: { floor: Floor; live: boolean }) {
  return (
    <section className={`floor ${live ? 'is-live' : ''}`} aria-label="Agents on the floor">
      <div className="floor-label">The floor</div>
      <svg className="floor-wires" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
        {floor.edges.map((e) => (
          <path
            key={`${e.from}>${e.to}`}
            d={edgePath(e.from, e.to)}
            className={`wire ${e.active ? 'is-active' : ''} ${e.blocked ? 'is-blocked' : ''}`}
            style={{ '--wire': PERSONAS[e.to].color } as CSSProperties}
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>

      {AGENT_ORDER.map((name) => {
        const p = PERSONAS[name]
        const st = floor.stations[name]
        const spot = SPOTS[name]
        return (
          <article
            key={name}
            className={`station is-${st.status} voice-${p.voice} ${name === 'boss' ? 'is-boss' : ''}`}
            style={{ left: `${spot.x}%`, top: `${spot.y}%`, '--agent': p.color } as CSSProperties}
          >
            <div className="bubble" aria-live={live ? 'polite' : 'off'}>
              {st.line}
            </div>
            <div className="avatar">
              <span className="avatar-ring" aria-hidden />
              <span className="avatar-glyph" aria-hidden>
                {p.glyph}
              </span>
              {st.status === 'done' && (
                <span className="avatar-check" aria-hidden>
                  ✓
                </span>
              )}
            </div>
            <div className="station-name">{p.title}</div>
            <div className="station-meta">
              <span className={`station-status s-${st.status}`}>{STATUS_WORD[st.status]}</span>
              {st.toolCalls > 0 && <span className="station-calls">{st.toolCalls} tool calls</span>}
            </div>
            {st.tools.length > 0 && (
              <div className="station-tools">
                {st.tools.slice(0, 4).map((t) => (
                  <code key={t}>{t}</code>
                ))}
                {st.tools.length > 4 && <code title={st.tools.slice(4).join(', ')}>+{st.tools.length - 4}</code>}
              </div>
            )}
          </article>
        )
      })}
    </section>
  )
}
