import { useEffect, useRef, useState } from 'react'

/**
 * Generic debounced-save hook.
 *
 * Re-fires `save(value)` after `delayMs` of stillness on `value` changes.
 * Tracks `isPending` so callers can show a "Saving…" indicator.
 *
 * Pass `null` while loading so the initial server-load doesn't echo back
 * as a save. The first non-null value seen is treated as the loaded
 * baseline; subsequent changes fire saves.
 */
export function useDebouncedSave<T>(
  value: T | null,
  delayMs: number,
  save: (v: T) => Promise<unknown>
) {
  const [isPending, setIsPending] = useState(false)
  const skipNextNonNull = useRef(true)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (value === null) return
    if (skipNextNonNull.current) {
      skipNextNonNull.current = false
      return
    }
    setIsPending(true)
    if (timer.current !== null) {
      window.clearTimeout(timer.current)
    }
    timer.current = window.setTimeout(() => {
      save(value).finally(() => setIsPending(false))
      timer.current = null
    }, delayMs)
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    }
  }, [value, delayMs, save])

  return { isPending }
}
