/**
 * Phase 4 sub-plan 6 Step 4: SettingsScreen unit tests (TDD).
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import SettingsScreen from './SettingsScreen'

function renderAt() {
  return render(
    <MemoryRouter initialEntries={['/settings']}>
      <SettingsScreen />
    </MemoryRouter>
  )
}

beforeEach(() => {
  localStorage.clear()
})

describe('SettingsScreen', () => {
  it('renders the Gemini key input empty and modes defaulting to mock', () => {
    renderAt()
    const input = screen.getByLabelText(/gemini api key/i) as HTMLInputElement
    expect(input.value).toBe('')
    // Generate prompts radio: mock is selected by default.
    const mockRadio = screen.getByRole('radio', {
      name: /generate prompts — mock/i,
    }) as HTMLInputElement
    expect(mockRadio.checked).toBe(true)
  })

  it('saves the Gemini key to localStorage and persists after re-mount', () => {
    renderAt()
    const input = screen.getByLabelText(/gemini api key/i) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'sk-test-123' } })
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
    const raw = localStorage.getItem('olga.keys')
    expect(raw).toContain('sk-test-123')

    // Re-mount and verify the input hydrates (masked still — user clicks Show).
    renderAt()
    const input2 = screen.getAllByLabelText(/gemini api key/i)[0] as HTMLInputElement
    expect(input2.value).toBe('sk-test-123')
  })

  it('Clear wipes the stored key and resets the input', () => {
    renderAt()
    const input = screen.getByLabelText(/gemini api key/i) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'sk-test-123' } })
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^clear$/i }))
    expect(input.value).toBe('')
  })

  it('toggling Generate prompts to api persists + mock-only stages are disabled', () => {
    renderAt()
    const apiRadio = screen.getByRole('radio', {
      name: /generate prompts — api/i,
    }) as HTMLInputElement
    fireEvent.click(apiRadio)
    expect(apiRadio.checked).toBe(true)
    const rawModes = localStorage.getItem('olga.modes')
    expect(rawModes).toContain('"generatePrompts":"api"')

    // Prepare / extend / generateVideos / stitch api radios disabled.
    for (const stage of ['prepare', 'storyboard extend', 'generate videos', 'stitch']) {
      const disabled = screen.getByRole('radio', {
        name: new RegExp(`${stage} — api`, 'i'),
      }) as HTMLInputElement
      expect(disabled.disabled).toBe(true)
    }
  })
})

describe('SettingsScreen — columns', () => {
  it('renders three column headers: Stage, mock, api', () => {
    renderAt()
    const table = screen.getByRole('table')
    const headers = table.querySelectorAll('thead th')
    expect(Array.from(headers).map((h) => h.textContent?.trim())).toEqual([
      'Stage',
      'mock',
      'api',
    ])
  })

  it('Generate prompts — api radio stays enabled (Phase 4 contract)', () => {
    renderAt()
    const apiRadio = screen.getByRole('radio', {
      name: /^Generate prompts — api$/,
    }) as HTMLInputElement
    expect(apiRadio.disabled).toBe(false)
  })

  it('mock radios stay enabled on every stage row', () => {
    renderAt()
    for (const label of [
      'Prepare',
      'Storyboard extend',
      'Generate prompts',
      'Generate videos',
      'Stitch',
    ]) {
      const mockRadio = screen.getByRole('radio', {
        name: new RegExp(`^${label} — mock$`),
      }) as HTMLInputElement
      expect(mockRadio.disabled).toBe(false)
    }
  })
})
