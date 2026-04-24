/**
 * Phase 4 sub-plan 6 Step 2: useSettings hook (TDD).
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

import { useSettings, DEFAULT_MODES } from './useSettings'

beforeEach(() => {
  localStorage.clear()
})

describe('useSettings', () => {
  it('returns defaults when localStorage is empty', () => {
    const { result } = renderHook(() => useSettings())
    expect(result.current.keys.gemini).toBe('')
    expect(result.current.modes).toEqual(DEFAULT_MODES)
  })

  it('persists a saved key and reads it back on a second hook instance', () => {
    const { result } = renderHook(() => useSettings())
    act(() => result.current.setKey('gemini', 'sk-abc'))
    expect(result.current.keys.gemini).toBe('sk-abc')
    expect(localStorage.getItem('olga.keys')).toContain('sk-abc')

    // A fresh hook instance sees the persisted value.
    const { result: r2 } = renderHook(() => useSettings())
    expect(r2.current.keys.gemini).toBe('sk-abc')
  })

  it('clearKey wipes storage and state', () => {
    const { result } = renderHook(() => useSettings())
    act(() => result.current.setKey('gemini', 'sk-abc'))
    act(() => result.current.clearKey('gemini'))
    expect(result.current.keys.gemini).toBe('')
    // localStorage entry either absent or an object without the key.
    const raw = localStorage.getItem('olga.keys')
    if (raw) {
      const parsed = JSON.parse(raw) as { gemini?: string }
      expect(parsed.gemini || '').toBe('')
    }
  })

  it('setMode updates the given stage and persists', () => {
    const { result } = renderHook(() => useSettings())
    act(() => result.current.setMode('generatePrompts', 'api'))
    expect(result.current.modes.generatePrompts).toBe('api')
    expect(result.current.modes.prepare).toBe('mock') // others untouched
    const raw = localStorage.getItem('olga.modes')
    expect(raw).toContain('"generatePrompts":"api"')
  })

  it('syncs across hook instances via the storage event', () => {
    const { result: r1 } = renderHook(() => useSettings())
    const { result: r2 } = renderHook(() => useSettings())

    // Simulate another tab writing to localStorage + dispatching the
    // 'storage' event (jsdom only fires 'storage' for cross-document
    // changes, so we fire it manually).
    act(() => {
      localStorage.setItem('olga.keys', JSON.stringify({ gemini: 'from-other-tab' }))
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: 'olga.keys',
          newValue: JSON.stringify({ gemini: 'from-other-tab' }),
        })
      )
    })

    expect(r1.current.keys.gemini).toBe('from-other-tab')
    expect(r2.current.keys.gemini).toBe('from-other-tab')
  })
})

describe('useSettings — generateVideos default', () => {
  it('DEFAULT_MODES.generateVideos stays mock (no accidental upgrade)', () => {
    // Pins the default so a future edit that flips generateVideos to
    // api accidentally fails loudly. Authentic regression guard.
    expect(DEFAULT_MODES.generateVideos).toBe('mock')
  })

  it('storage missing generateVideos key backfills to mock default', () => {
    // Pre-Phase-5 upgrade shape: someone had partial modes written. The
    // read() merge with DEFAULT_MODES fills in the missing keys.
    localStorage.setItem(
      'olga.modes',
      JSON.stringify({ prepare: 'mock', extend: 'mock' })
    )
    const { result } = renderHook(() => useSettings())
    expect(result.current.modes.generateVideos).toBe('mock')
  })
})

describe('useSettings — fal.ai key (Phase 5 Sub-Plan 2)', () => {
  it('DEFAULT_KEYS.fal is empty string', () => {
    const { result } = renderHook(() => useSettings())
    expect(result.current.keys.fal).toBe('')
  })

  it('setKey("fal", ...) persists and reads back on a fresh hook', () => {
    const { result } = renderHook(() => useSettings())
    act(() => result.current.setKey('fal', 'fal-xyz'))
    expect(result.current.keys.fal).toBe('fal-xyz')
    expect(localStorage.getItem('olga.keys')).toContain('fal-xyz')

    const { result: r2 } = renderHook(() => useSettings())
    expect(r2.current.keys.fal).toBe('fal-xyz')
  })

  it('clearKey("fal") wipes without affecting other keys', () => {
    const { result } = renderHook(() => useSettings())
    act(() => result.current.setKey('gemini', 'gem-1'))
    act(() => result.current.setKey('fal', 'fal-1'))
    act(() => result.current.clearKey('fal'))
    expect(result.current.keys.fal).toBe('')
    expect(result.current.keys.gemini).toBe('gem-1')
  })

  it('pre-Sub-Plan-2 storage (no "fal" key) still parses; fal backfills to empty string', () => {
    // Authenticity: someone upgrades from Phase-4 Settings where Keys
    // only had `gemini`. read()'s spread merge must backfill `fal: ""`
    // — otherwise keys.fal is `undefined` and headers break silently.
    localStorage.setItem('olga.keys', JSON.stringify({ gemini: 'legacy' }))
    const { result } = renderHook(() => useSettings())
    expect(result.current.keys.gemini).toBe('legacy')
    expect(result.current.keys.fal).toBe('')
  })
})
