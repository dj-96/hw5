export interface Toast {
  id: number
  text: string
  tone: 'info' | 'good' | 'bad'
}

export default function Toasts({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast t-${t.tone}`}>
          {t.text}
        </div>
      ))}
    </div>
  )
}
