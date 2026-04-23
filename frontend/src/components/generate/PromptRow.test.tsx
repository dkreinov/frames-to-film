/**
 * Phase 4 sub-plan 4 Step 6 unit (TDD): PromptRow.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import { PromptRow } from './PromptRow'

describe('PromptRow', () => {
  it('renders two thumbnails, the pair key, and seeds the textarea with value', () => {
    render(
      <PromptRow
        projectId="pid-x"
        pairKey="1_to_2"
        frameA="1.jpg"
        frameB="2.jpg"
        value="slow cinematic dolly"
        onChange={() => {}}
      />
    )
    const imgs = screen.getAllByRole('img')
    expect(imgs.length).toBe(2)
    expect(screen.getByText('1_to_2')).toBeInTheDocument()
    const textarea = screen.getByRole('textbox', { name: /Prompt for pair 1_to_2/i })
    expect(textarea).toHaveValue('slow cinematic dolly')
  })

  it('calls onChange with the new value when the textarea is edited', () => {
    const onChange = vi.fn()
    render(
      <PromptRow
        projectId="pid-x"
        pairKey="2_to_3"
        frameA="2.jpg"
        frameB="3.jpg"
        value=""
        onChange={onChange}
      />
    )
    const textarea = screen.getByRole('textbox', { name: /Prompt for pair 2_to_3/i })
    fireEvent.change(textarea, { target: { value: 'new prompt text' } })
    expect(onChange).toHaveBeenCalledWith('new prompt text')
  })

  it('optionally renders a video poster slot when supplied', () => {
    render(
      <PromptRow
        projectId="pid-x"
        pairKey="1_to_2"
        frameA="1.jpg"
        frameB="2.jpg"
        value=""
        onChange={() => {}}
        poster={<button aria-label="Play 1_to_2">▶</button>}
      />
    )
    expect(screen.getByRole('button', { name: /play 1_to_2/i })).toBeInTheDocument()
  })
})
