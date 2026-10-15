// Turns the raw audit-trail events of one run into what the board shows:
// each agent's live status, the hand-off lines between them, a readable
// feed, and a per-agent debrief once the run is over.
import { AGENT_ORDER, HIDDEN_TOOLS, describeTool, isAgent, titleOf } from './agents'
import type { AgentEvent, AgentName, BossReport, SpecialistReport } from './types'

export type StationStatus = 'idle' | 'thinking' | 'working' | 'waiting' | 'done' | 'error'

export interface Station {
  agent: AgentName
  status: StationStatus
  line: string
  tools: string[]
  toolCalls: number
  turns: number
}

export interface Edge {
  from: AgentName
  to: AgentName
  active: boolean
  blocked: boolean
}

export type FeedKind = 'brief' | 'said' | 'tool' | 'handoff' | 'blocked' | 'done' | 'error' | 'retry'

export interface FeedItem {
  key: string
  ts: string
  agent: AgentName | 'system'
  kind: FeedKind
  text: string
  chips?: string[]
  to?: AgentName
}

export interface Floor {
  stations: Record<AgentName, Station>
  edges: Edge[]
  feed: FeedItem[]
  startedAt: string | null
  endedAt: string | null
}

const emptyStation = (agent: AgentName): Station => ({
  agent,
  status: 'idle',
  line: agent === 'boss' ? 'Waiting for a ticket' : 'Off the clock',
  tools: [],
  toolCalls: 0,
  turns: 0,
})

const firstSentence = (s: string, max = 140) => {
  const cut = s.split(/(?<=[.!?])\s/)[0] ?? s
  return cut.length > max ? cut.slice(0, max - 1) + '…' : cut
}

export function buildFloor(events: AgentEvent[]): Floor {
  const stations = Object.fromEntries(AGENT_ORDER.map((a) => [a, emptyStation(a)])) as Record<AgentName, Station>
  const edges = new Map<string, Edge>()
  const feed: FeedItem[] = []
  let startedAt: string | null = null
  let endedAt: string | null = null

  events.forEach((e, i) => {
    const key = `${e.ts}-${i}`
    if (e.step === 'session_start') startedAt = e.ts
    if (e.step === 'session_end') endedAt = e.ts
    if (!isAgent(e.agent)) return
    const st = stations[e.agent]

    switch (e.step) {
      case 'user_prompt': {
        st.status = 'thinking'
        st.turns += 1
        st.line = e.agent === 'boss' ? 'Reading the ticket' : 'Got the brief, reading it'
        break
      }
      case 'model_request': {
        if (st.status !== 'waiting') st.status = 'thinking'
        if (e.retries?.length) {
          feed.push({ key, ts: e.ts, agent: e.agent, kind: 'retry', text: `Retrying: ${e.retries[0].error.slice(0, 120)}` })
        }
        break
      }
      case 'model_response': {
        const calls = (e.tool_calls ?? []).filter((c) => !HIDDEN_TOOLS.has(c.tool))
        const delegating = (e.tool_calls ?? []).some((c) => c.tool === 'delegate')
        const filing = (e.tool_calls ?? []).some((c) => c.tool === 'final_result')
        if (e.said) {
          st.line = firstSentence(e.said)
          feed.push({ key: key + 's', ts: e.ts, agent: e.agent, kind: 'said', text: e.said })
        }
        if (calls.length) {
          st.status = 'working'
          st.toolCalls += calls.length
          for (const c of calls) if (!st.tools.includes(c.tool)) st.tools.push(c.tool)
          const lines = calls.map((c) => describeTool(c.tool, c.args))
          st.line = lines.join(' · ')
          feed.push({ key, ts: e.ts, agent: e.agent, kind: 'tool', text: lines.join('\n'), chips: calls.map((c) => c.tool) })
        } else if (filing) {
          st.status = 'working'
          st.line = 'Writing up the report'
        }
        if (delegating) st.status = 'waiting'
        break
      }
      case 'delegate': {
        const to = e.to && isAgent(e.to) ? e.to : null
        if (!to) break
        const id = `${e.agent}>${to}`
        const blocked = e.allowed === false
        edges.set(id, { from: e.agent, to, active: !blocked, blocked: blocked && !edges.get(id)?.active })
        if (blocked) {
          feed.push({ key, ts: e.ts, agent: e.agent, kind: 'blocked', to, text: e.blocked_reason ?? 'Hand-off blocked' })
        } else {
          st.status = 'waiting'
          st.line = `Waiting on ${titleOf(to)}`
          feed.push({ key, ts: e.ts, agent: e.agent, kind: 'handoff', to, text: e.said ?? '' })
        }
        break
      }
      case 'end': {
        st.status = 'done'
        const out = e.output as Partial<SpecialistReport & BossReport> | undefined
        st.line = out?.summary ? firstSentence(out.summary) : e.agent === 'boss' ? 'Plan filed' : 'Report filed'
        feed.push({ key, ts: e.ts, agent: e.agent, kind: 'done', text: out?.summary ?? 'Plan is on the desk.' })
        // Close every live hand-off into this agent; the caller is back on it.
        for (const edge of edges.values()) {
          if (edge.to === e.agent && edge.active) {
            edge.active = false
            const parent = stations[edge.from]
            if (parent.status === 'waiting') {
              parent.status = 'thinking'
              parent.line = `Reading ${titleOf(e.agent)}'s report`
            }
          }
        }
        break
      }
      case 'error': {
        st.status = 'error'
        st.line = 'Hit an error'
        feed.push({ key, ts: e.ts, agent: e.agent, kind: 'error', text: e.error ?? 'Unknown error' })
        break
      }
    }
  })

  if (endedAt) for (const edge of edges.values()) edge.active = false
  return { stations, edges: [...edges.values()], feed, startedAt, endedAt }
}

export interface Debrief {
  agent: AgentName
  headline: string
  points: string[]
  needs: string[]
  status?: string
}

/** One card per agent that worked the run, built from their final typed reports. */
export function buildDebrief(events: AgentEvent[], ticketId: number): Debrief[] {
  const byAgent = new Map<AgentName, Debrief>()
  for (const e of events) {
    if (e.step !== 'end' || !isAgent(e.agent) || typeof e.output !== 'object' || !e.output) continue
    if (e.agent === 'boss') {
      const report = e.output as BossReport
      const decision = report.tickets?.find((t) => t.ticket_id === ticketId) ?? report.tickets?.[0]
      if (!decision) continue
      byAgent.set('boss', {
        agent: 'boss',
        headline: decision.decision,
        points: [decision.rationale, report.cash_note].filter(Boolean),
        needs: decision.human_actions ?? [],
        status: decision.status,
      })
    } else {
      const r = e.output as SpecialistReport
      const prev = byAgent.get(e.agent)
      byAgent.set(e.agent, {
        agent: e.agent,
        headline: prev ? `${prev.headline} ${r.summary}` : r.summary,
        points: [...(prev?.points ?? []), ...(r.actions_taken ?? [])],
        needs: [...(prev?.needs ?? []), ...(r.needs_human ?? [])],
        status: r.recommended_status ?? prev?.status,
      })
    }
  }
  return AGENT_ORDER.filter((a) => byAgent.has(a)).map((a) => byAgent.get(a)!)
}

export const elapsed = (from: string | null, to: string | null | number = Date.now()) => {
  if (!from) return '0:00'
  const end = typeof to === 'number' ? to : to ? Date.parse(to) : Date.now()
  const s = Math.max(0, Math.round((end - Date.parse(from)) / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
