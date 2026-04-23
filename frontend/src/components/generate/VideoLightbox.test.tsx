/**
 * Phase 4 sub-plan 4 Step 6 unit (TDD): VideoLightbox.
 */
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import { VideoLightbox } from './VideoLightbox'

describe('VideoLightbox', () => {
  it('renders a poster button with an accessible label when closed', () => {
    render(<VideoLightbox src="https://example.test/a.mp4" pairKey="1_to_2" />)
    expect(
      screen.getByRole('button', { name: /play 1_to_2/i })
    ).toBeInTheDocument()
    // <video> is NOT in the DOM until the dialog opens.
    expect(document.querySelector('video')).toBeNull()
  })

  it('opens a dialog with a <video> element pointing at src on click', () => {
    render(<VideoLightbox src="https://example.test/a.mp4" pairKey="1_to_2" />)
    fireEvent.click(screen.getByRole('button', { name: /play 1_to_2/i }))
    const video = document.querySelector('video')
    expect(video).not.toBeNull()
    expect(video?.getAttribute('src')).toBe('https://example.test/a.mp4')
    expect(video?.hasAttribute('controls')).toBe(true)
  })
})
