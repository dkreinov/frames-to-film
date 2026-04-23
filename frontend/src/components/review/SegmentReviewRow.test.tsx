/**
 * Phase 4 sub-plan 5 Step 4 unit (TDD): SegmentReviewRow.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import { SegmentReviewRow } from './SegmentReviewRow'

describe('SegmentReviewRow', () => {
  it('renders two thumbnails, the pair key, and a video poster trigger', () => {
    render(
      <SegmentReviewRow
        projectId="pid-x"
        pairKey="1_to_2"
        frameA="1.jpg"
        frameB="2.jpg"
        videoName="seg_1_to_2.mp4"
        verdict={null}
        onVerdict={() => {}}
      />
    )
    const imgs = screen.getAllByRole('img')
    expect(imgs.length).toBe(2)
    expect(screen.getByText('1_to_2')).toBeInTheDocument()
    // VideoLightbox trigger
    expect(screen.getByRole('button', { name: /play 1_to_2/i })).toBeInTheDocument()
  })

  it('renders three verdict buttons with aria-pressed reflecting current verdict', () => {
    render(
      <SegmentReviewRow
        projectId="pid-x"
        pairKey="1_to_2"
        frameA="1.jpg"
        frameB="2.jpg"
        videoName="seg_1_to_2.mp4"
        verdict="winner"
        onVerdict={() => {}}
      />
    )
    const winner = screen.getByRole('button', { name: /mark 1_to_2 as winner/i })
    const redo = screen.getByRole('button', { name: /mark 1_to_2 as redo/i })
    const bad = screen.getByRole('button', { name: /mark 1_to_2 as bad/i })
    expect(winner).toHaveAttribute('aria-pressed', 'true')
    expect(redo).toHaveAttribute('aria-pressed', 'false')
    expect(bad).toHaveAttribute('aria-pressed', 'false')
  })

  it('calls onVerdict with the clicked verdict', () => {
    const onVerdict = vi.fn()
    render(
      <SegmentReviewRow
        projectId="pid-x"
        pairKey="2_to_3"
        frameA="2.jpg"
        frameB="3.jpg"
        videoName="seg_2_to_3.mp4"
        verdict={null}
        onVerdict={onVerdict}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /mark 2_to_3 as redo/i }))
    expect(onVerdict).toHaveBeenCalledWith('redo')
  })

  it('shows no pressed buttons when verdict is null', () => {
    render(
      <SegmentReviewRow
        projectId="pid-x"
        pairKey="1_to_2"
        frameA="1.jpg"
        frameB="2.jpg"
        videoName="seg_1_to_2.mp4"
        verdict={null}
        onVerdict={() => {}}
      />
    )
    for (const v of ['winner', 'redo', 'bad'] as const) {
      const btn = screen.getByRole('button', { name: new RegExp(`mark 1_to_2 as ${v}`, 'i') })
      expect(btn).toHaveAttribute('aria-pressed', 'false')
    }
  })
})
