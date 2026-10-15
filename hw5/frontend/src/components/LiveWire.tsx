import { useEffect, useRef, type CSSProperties } from 'react'
import { PERSONAS, persona, titleOf } from '../agents'
import { elapsed, type FeedItem } from '../floor'

const KIND_TAG: Record<FeedItem['kind'], string> = {
  brief: 'brief',
  said: 'says',
  tool: 'does',
  handoff: 'hands off',
  blocked: 'blocked',
  done: 'reports',
  error: 'error',
  retry: 'retry',
}

export default function LiveWire({ feed, live, startedAt }: { feed: FeedItem[]; live: boolean; startedAt: string | null }) {
  const list = useRef<HTMLOListElement>(null)
  // Follow the newest move inside the feed only (never scroll the whole page).
  useEffect(() => {
    const el = list.current
    if (live && el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [feed.length, live])

  return (
    <section className="wire-panel" aria-label="Live agent feed">
      <div className="panel-head">
        <h3>
          Live wire {live && <span className="rec">● REC</span>}
        </h3>
        <span className="panel-sub">{feed.length ? `${feed.length} moves` : 'Quiet for now'}</span>
      </div>
      <ol ref={list} className="feed" aria-live={live ? 'polite' : 'off'}>
        {feed.length === 0 && <li className="feed-empty">Send the team in and every move shows up here.</li>}
        {feed.map((f) => {
          const p = persona(f.agent)
          return (
            <li key={f.key} className={`feed-item k-${f.kind} voice-${p?.voice ?? 'plain'}`} style={{ '--agent': p?.color ?? '#888' } as CSSProperties}>
              <span className="feed-time">{elapsed(startedAt, f.ts)}</span>
              <span className="feed-who">
                <span className="feed-glyph" aria-hidden>
                  {p?.glyph}
                </span>
                {p?.title ?? f.agent}
              </span>
              <span className="feed-tag">{KIND_TAG[f.kind]}</span>
              <div className="feed-body">
                {f.to && (
                  <span className="feed-to" style={{ '--to': PERSONAS[f.to].color } as CSSProperties}>
                    → {titleOf(f.to)}
                  </span>
                )}
                <span className="feed-text">{f.text}</span>
                {f.chips && (
                  <span className="feed-chips">
                    {f.chips.map((c, i) => (
                      <code key={c + i}>{c}</code>
                    ))}
                  </span>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
