import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from './api'
import { buildDebrief, buildFloor } from './floor'
import { useInterval, useLocalStorage } from './hooks'
import type { AgentEvent, BossReport, Cash, PaymentRequest, PurchaseOrder, RunInfo, Ticket, TicketDetail } from './types'
import Header from './components/Header'
import TicketRail from './components/TicketRail'
import TicketHero from './components/TicketHero'
import AgentFloor from './components/AgentFloor'
import LiveWire from './components/LiveWire'
import DebriefPanel from './components/DebriefPanel'
import Till from './components/Till'
import SignatureTray from './components/SignatureTray'
import Toasts, { type Toast } from './components/Toasts'

const BASE_POLL_MS = 4000
const LIVE_POLL_MS = 1200

export default function App() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [model, setModel] = useState('')
  const [shopToday, setShopToday] = useState('')
  const [tickets, setTickets] = useState<Ticket[]>([])
  // The URL hash picks the ticket (e.g. http://localhost:5173/#103), so a
  // ticket's view can be bookmarked or screenshotted.
  const [selectedId, setSelectedIdState] = useState<number | null>(() => Number(location.hash.slice(1)) || null)
  const setSelectedId = useCallback((id: number | null) => {
    setSelectedIdState(id)
    if (id !== null) history.replaceState(null, '', `#${id}`)
  }, [])
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [cash, setCash] = useState<Cash | null>(null)
  const [pending, setPending] = useState<PaymentRequest[]>([])
  const [paid, setPaid] = useState<PaymentRequest[]>([])
  const [pos, setPos] = useState<PurchaseOrder[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [liveRun, setLiveRun] = useState<RunInfo | null>(null)
  const [lastReport, setLastReport] = useState<BossReport | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [signer, setSigner] = useLocalStorage('cc-desk-signer', '')
  const toastId = useRef(0)

  const toast = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = ++toastId.current
    setToasts((t) => [...t, { id, text, tone }])
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5200)
  }, [])

  const selected = tickets.find((t) => t.id === selectedId) ?? null
  const running = liveRun?.status === 'running'
  // Which run to show for the selected ticket: the live one, else its last run.
  const sessionId =
    liveRun && liveRun.ticket_id === selectedId ? liveRun.session_id : selected?.last_run?.session_id ?? null

  const refreshDesk = useCallback(async () => {
    try {
      const [t, c, p, a, o] = await Promise.all([
        api.tickets(),
        api.cash(),
        api.payments('pending'),
        api.payments('approved'),
        api.purchaseOrders(),
      ])
      setTickets(t.tickets)
      setShopToday(t.shop_today)
      setCash(c)
      setPending(p.requests)
      setPaid(a.requests)
      setPos(o.purchase_orders)
      setOnline(true)
      setSelectedIdState((id) => id ?? t.tickets.find((x) => x.state === 'open')?.id ?? t.tickets[0]?.id ?? null)
    } catch (err) {
      setOnline(false)
    }
  }, [])

  const refreshEvents = useCallback(async () => {
    if (!sessionId) return setEvents([])
    try {
      setEvents((await api.events(sessionId)).events)
    } catch {
      /* keep the last events on a blip */
    }
  }, [sessionId])

  // First load + health.
  useEffect(() => {
    refreshDesk()
    api.health().then((h) => {
      setModel(`${h.model} · ${h.gateway}`)
      if (h.active_run) api.runStatus(h.active_run).then(setLiveRun).catch(() => {})
    }).catch(() => setOnline(false))
  }, [refreshDesk])

  useEffect(() => {
    setEvents([])
    refreshEvents()
  }, [refreshEvents])

  useEffect(() => {
    if (selectedId === null) return setDetail(null)
    api.ticket(selectedId).then(setDetail).catch(() => setDetail(null))
  }, [selectedId, tickets])

  useInterval(refreshDesk, running ? LIVE_POLL_MS * 2 : BASE_POLL_MS)
  useInterval(refreshEvents, running && liveRun?.ticket_id === selectedId ? LIVE_POLL_MS : null)

  // Watch the live run until it finishes.
  useInterval(
    async () => {
      if (!liveRun) return
      try {
        const info = await api.runStatus(liveRun.session_id)
        if (info.status === 'running') return
        setLiveRun(info)
        if (info.report) setLastReport(info.report)
        await Promise.all([refreshDesk(), refreshEvents()])
        if (info.status === 'done') toast(`Ticket #${info.ticket_id} resolved by the team. Check the signature tray.`, 'good')
        else toast(`Run on #${info.ticket_id} failed: ${info.error ?? 'unknown error'}`, 'bad')
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) setLiveRun(null)
      }
    },
    running ? LIVE_POLL_MS : null,
  )

  const dispatch = async () => {
    if (!selected) return
    try {
      const info = await api.run(selected.id)
      setLiveRun(info)
      setEvents([])
      toast(`The team is on ticket #${selected.id}.`)
      refreshDesk()
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), 'bad')
    }
  }

  const sign = async (action: () => Promise<{ amount?: number; new_balance?: number; po_eta?: string }>, label: string) => {
    if (!signer.trim()) {
      toast('Type your name in "Signing as" first. Every payment is signed by a person.', 'bad')
      return false
    }
    try {
      const r = await action()
      const eta = r.po_eta ? ` Order placed, arriving ${r.po_eta}.` : ''
      toast(`${label} approved by ${signer}. Checking is now $${r.new_balance?.toLocaleString()}.${eta}`, 'good')
      await refreshDesk()
      return true
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), 'bad')
      return false
    }
  }

  const deny = async (req: PaymentRequest) => {
    if (!signer.trim()) return toast('Type your name in "Signing as" first.', 'bad')
    try {
      await api.denyPayment(req.id, signer, 'Denied from the desk')
      toast(`Request #${req.id} denied. No money moved.`)
      refreshDesk()
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), 'bad')
    }
  }

  const reset = async () => {
    if (running) return toast('Wait for the run to finish before starting a new shift.', 'bad')
    if (!window.confirm('Start a new shift? This resets the shop database to the original values (the audit trail is kept).')) return
    try {
      await api.reset()
      setLiveRun(null)
      setLastReport(null)
      setEvents([])
      await refreshDesk()
      toast('New shift: database reset, till back to the opening balance.', 'good')
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), 'bad')
    }
  }

  const floor = useMemo(() => buildFloor(events), [events])
  const debrief = useMemo(() => (selectedId ? buildDebrief(events, selectedId) : []), [events, selectedId])
  const bossReport = useMemo(() => {
    const end = [...events].reverse().find((e) => e.agent === 'boss' && e.step === 'end')
    return (end?.output as BossReport | undefined) ?? lastReport
  }, [events, lastReport])
  const showingLive = running && liveRun?.ticket_id === selectedId
  // Slips still waiting on a person, per ticket (payment requests + draft POs with no request yet).
  const toSign = useMemo(() => {
    const counts: Record<number, number> = {}
    const bump = (id: number | null) => {
      if (id !== null) counts[id] = (counts[id] ?? 0) + 1
    }
    pending.forEach((r) => bump(r.ticket_id))
    pos
      .filter((p) => p.status === 'draft' && !pending.some((r) => r.kind === 'purchase_order' && r.ref_id === p.id))
      .forEach((p) => bump(p.ticket_id))
    return counts
  }, [pending, pos])

  return (
    <div className="desk">
      <div className="desk-glow" aria-hidden />
      <Header
        online={online}
        shopToday={shopToday}
        model={model}
        signer={signer}
        onSigner={setSigner}
        onReset={reset}
        running={running}
      />

      <main className="desk-grid">
        <TicketRail
          tickets={tickets}
          selectedId={selectedId}
          onSelect={setSelectedId}
          liveTicketId={running ? liveRun?.ticket_id ?? null : null}
          toSign={toSign}
        />

        <section className="floor-col">
          <TicketHero
            ticket={selected}
            detail={detail}
            running={running}
            liveHere={showingLive}
            otherLive={running && !showingLive ? liveRun?.ticket_id ?? null : null}
            startedAt={floor.startedAt}
            endedAt={floor.endedAt}
            onDispatch={dispatch}
          />
          <AgentFloor floor={floor} live={showingLive} />
          {floor.endedAt && debrief.length > 0 && <DebriefPanel ticketId={selectedId!} debrief={debrief} />}
          <LiveWire feed={floor.feed} live={showingLive} startedAt={floor.startedAt} />
        </section>

        <aside className="till-col">
          <Till cash={cash} paid={paid} />
          <SignatureTray
            pending={pending}
            pos={pos}
            report={bossReport}
            selectedId={selectedId}
            signer={signer}
            onApprovePayment={(r) => sign(() => api.approvePayment(r.id, signer), `$${r.amount.toLocaleString()} ${r.kind.replace('_', ' ')}`)}
            onApprovePurchase={(po) => sign(() => api.approvePurchase(po.id, signer), `PO #${po.id} ($${po.total.toLocaleString()})`)}
            onDeny={deny}
          />
        </aside>
      </main>

      <Toasts toasts={toasts} />
    </div>
  )
}
