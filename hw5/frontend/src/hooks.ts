import { useEffect, useRef, useState } from 'react'

/** Run `fn` every `ms` while `ms` is a number; pass null to pause. */
export function useInterval(fn: () => void, ms: number | null) {
  const saved = useRef(fn)
  saved.current = fn
  useEffect(() => {
    if (ms === null) return
    const id = window.setInterval(() => saved.current(), ms)
    return () => window.clearInterval(id)
  }, [ms])
}

/** Smoothly count a number toward its new value (the till's rolling digits).
 *  `null` means "not loaded yet": the first real value is shown at once, so
 *  the till never displays an in-between number on page load. */
export function useTween(target: number | null, ms = 1100) {
  const [value, setValue] = useState(target ?? 0)
  const from = useRef<number | null>(target)
  useEffect(() => {
    if (target === null) return
    if (from.current === null) {
      from.current = target
      setValue(target)
      return
    }
    const start = performance.now()
    const begin = from.current
    if (begin === target) return
    const land = () => {
      setValue(target)
      from.current = target
    }
    // Browsers pause animation frames in background tabs, so jump straight
    // there when hidden, and always land on the real number afterwards.
    if (document.visibilityState !== 'visible') {
      land()
      return
    }
    let frame = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      const eased = 1 - Math.pow(1 - t, 3)
      const v = begin + (target - begin) * eased
      setValue(v)
      from.current = v
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    const fallback = window.setTimeout(land, ms + 150)
    return () => {
      cancelAnimationFrame(frame)
      window.clearTimeout(fallback)
    }
  }, [target, ms])
  return value
}

/** Re-render every second (for live timers). */
export function useNow(active: boolean) {
  const [now, setNow] = useState(Date.now())
  useInterval(() => setNow(Date.now()), active ? 1000 : null)
  return now
}

export function useLocalStorage(key: string, initial: string) {
  const [value, setValue] = useState(() => localStorage.getItem(key) ?? initial)
  useEffect(() => localStorage.setItem(key, value), [key, value])
  return [value, setValue] as const
}
