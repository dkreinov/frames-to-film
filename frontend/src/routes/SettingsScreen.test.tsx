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
    // Two Save buttons on the page (Gemini + fal). Click the one adjacent
    // to the Gemini input (first one in DOM order).
    fireEvent.click(screen.getAllByRole('button', { name: /^save$/i })[0])
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
    fireEvent.click(screen.getAllByRole('button', { name: /^save$/i })[0])
    fireEvent.click(screen.getAllByRole('button', { name: /^clear$/i })[0])
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

    // Prepare / extend / stitch api radios still disabled (Phase 5 only
    // lit up generate-videos + generate-prompts).
    for (const stage of ['prepare', 'storyboard extend', 'stitch']) {
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

describe('SettingsScreen — fal.ai key + enabled Generate videos api (Phase 5 Sub-Plan 2)', () => {
  it('renders both Gemini and fal.ai key inputs', () => {
    renderAt()
    expect(screen.getByLabelText(/gemini api key/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/fal\.ai api key/i)).toBeInTheDocument()
  })

  it('saving the fal.ai key persists to localStorage as olga.keys.fal', () => {
    renderAt()
    const input = screen.getByLabelText(/fal\.ai api key/i) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'fal-test-999' } })
    // Two Save buttons on the page now (one per field). Click the one
    // next to the fal input — it's the second Save button in DOM order.
    const saves = screen.getAllByRole('button', { name: /^save$/i })
    expect(saves).toHaveLength(2)
    fireEvent.click(saves[1])
    const raw = localStorage.getItem('olga.keys')
    expect(raw).toContain('"fal":"fal-test-999"')
  })

  it('Generate videos — api radio is enabled (not disabled like the mock-only rows)', () => {
    // Authenticity: the whole point of Step 9 is to flip apiEnabled:true
    // on the generateVideos row. If this regresses, the user can't even
    // select api mode.
    renderAt()
    const apiRadio = screen.getByRole('radio', {
      name: /^Generate videos — api$/,
    }) as HTMLInputElement
    expect(apiRadio.disabled).toBe(false)
  })

  it('Generate videos row no longer shows the "api mode arrives in Phase 5" note', () => {
    renderAt()
    const row = screen.getByText(/^Generate videos$/i).closest('tr')
    expect(row).toBeTruthy()
    expect(row!.textContent).not.toMatch(/api mode arrives in Phase 5/i)
  })
})
