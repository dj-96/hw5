interface Props {
  online: boolean | null
  shopToday: string
  model: string
  signer: string
  onSigner: (v: string) => void
  onReset: () => void
  running: boolean
}

const fmtDate = (iso: string) =>
  iso ? new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }) : '—'

export default function Header({ online, shopToday, model, signer, onSigner, onReset, running }: Props) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden>CC</span>
        <div>
          <h1>
            Campus <em>Customs</em>
          </h1>
          <p className="brand-sub">The Desk · Chapel Street</p>
        </div>
      </div>

      <div className="topbar-meta">
        <div className="meta-chip">
          <span className="meta-label">Shop date</span>
          <span className="meta-value">{fmtDate(shopToday)}</span>
        </div>
        <div className={`meta-chip status-${online === null ? 'wait' : online ? 'on' : 'off'}`}>
          <span className="pulse-dot" aria-hidden />
          <span className="meta-value">
            {online === null ? 'Connecting…' : online ? (running ? 'Team on the floor' : 'Backend live') : 'Backend offline'}
          </span>
        </div>
        {model && <div className="meta-chip model-chip">{model}</div>}
      </div>

      <div className="topbar-actions">
        <label className="signer">
          <span>Signing as</span>
          <input
            value={signer}
            onChange={(e) => onSigner(e.target.value)}
            placeholder="Your name"
            aria-label="Your name, used to sign approvals"
          />
        </label>
        <button className="btn-ghost" onClick={onReset} disabled={running} title="Reset the shop database to its opening values">
          ↺ New shift
        </button>
      </div>
    </header>
  )
}
