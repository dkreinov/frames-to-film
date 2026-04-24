import { useCallback, useEffect, useState } from 'react'

export type Mode = 'mock' | 'api'

export type StageKey =
  | 'prepare'
  | 'extend'
  | 'generatePrompts'
  | 'generateVideos'
  | 'stitch'

export interface Modes {
  prepare: Mode
  extend: Mode
  generatePrompts: Mode
  generateVideos: Mode
  stitch: Mode
}

export interface Keys {
  gemini: string
  fal: string
}

export const DEFAULT_MODES: Modes = {
  prepare: 'mock',
  extend: 'mock',
  generatePrompts: 'mock',
  generateVideos: 'mock',
  stitch: 'mock',
}

export const DEFAULT_KEYS: Keys = {
  gemini: '',
  fal: '',
}

const KEYS_STORAGE = 'olga.keys'
const MODES_STORAGE = 'olga.modes'

function read<T>(storageKey: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return fallback
    return { ...fallback, ...(JSON.parse(raw) as Partial<T>) } as T
  } catch {
    return fallback
  }
}

export function useSettings() {
  const [keys, setKeys] = useState<Keys>(() => read(KEYS_STORAGE, DEFAULT_KEYS))
  const [modes, setModes] = useState<Modes>(() => read(MODES_STORAGE, DEFAULT_MODES))

  // Sync across tabs / hook instances via the 'storage' event.
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === KEYS_STORAGE) setKeys(read(KEYS_STORAGE, DEFAULT_KEYS))
      if (e.key === MODES_STORAGE) setModes(read(MODES_STORAGE, DEFAULT_MODES))
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const setKey = useCallback((name: keyof Keys, value: string) => {
    setKeys((prev) => {
      const next = { ...prev, [name]: value }
      localStorage.setItem(KEYS_STORAGE, JSON.stringify(next))
      return next
    })
  }, [])

  const clearKey = useCallback((name: keyof Keys) => {
    setKeys((prev) => {
      const next = { ...prev, [name]: '' }
      localStorage.setItem(KEYS_STORAGE, JSON.stringify(next))
      return next
    })
  }, [])

  const setMode = useCallback((stage: StageKey, mode: Mode) => {
    setModes((prev) => {
      const next = { ...prev, [stage]: mode }
      localStorage.setItem(MODES_STORAGE, JSON.stringify(next))
      return next
    })
  }, [])

  return { keys, modes, setKey, clearKey, setMode }
}
