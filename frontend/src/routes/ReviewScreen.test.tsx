/**
 * Phase 4 sub-plan 5 Step 5 unit (TDD): ReviewScreen.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import ReviewScreen from './ReviewScreen'

vi.mock('@/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/api/client')>('@/api/client')
  return {
    ...actual,
    listStageOutputs: vi.fn(),
    getProjectOrder: vi.fn(),
    listVideos: vi.fn(),
    listSegments: vi.fn(),
    reviewSegment: vi.fn(),
    startStitch: vi.fn(async () => ({ job_id: 'sjob' })),
    getJob: vi.fn(),
  }
})

import * as client from '@/api/client'

function renderAt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/abc/review']}>
        <Routes>
          <Route path="/projects/:projectId/review" element={<ReviewScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => vi.clearAllMocks())

const baseJob = {
  job_id: 'sjob',
  project_id: 'abc',
  user_id: 'local',
  kind: 'stitch',
  payload: {},
  error: null as string | null,
  created_at: '',
  updated_at: '',
}

describe('ReviewScreen', () => {
  it('shows a loading state while videos are being fetched', async () => {
    // Never-resolving videos query keeps the screen in loading.
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.listVideos as any).mockImplementation(() => new Promise(() => {}))
    ;(client.listSegments as any).mockResolvedValue([])
    renderAt()
    expect(await screen.findByText(/loading your clips/i)).toBeInTheDocument()
  })

  it('renders one row per video with persisted verdicts from listSegments', async () => {
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.listVideos as any).mockResolvedValue([
      { name: 'seg_1_to_2.mp4', pair_key: '1_to_2' },
      { name: 'seg_2_to_3.mp4', pair_key: '2_to_3' },
    ])
    ;(client.listSegments as any).mockResolvedValue([
      { seg_id: 'seg_1_to_2', verdict: 'winner', notes: null, updated_at: '' },
    ])
    renderAt()
    const winnerBtn = await screen.findByRole('button', {
      name: /mark 1_to_2 as winner/i,
    })
    expect(winnerBtn).toHaveAttribute('aria-pressed', 'true')
    const secondWinner = screen.getByRole('button', {
      name: /mark 2_to_3 as winner/i,
    })
    expect(secondWinner).toHaveAttribute('aria-pressed', 'false')
  })

  it('clicking a verdict fires reviewSegment and updates aria-pressed on success', async () => {
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.listVideos as any).mockResolvedValue([
      { name: 'seg_1_to_2.mp4', pair_key: '1_to_2' },
    ])
    ;(client.listSegments as any).mockResolvedValue([])
    ;(client.reviewSegment as any).mockResolvedValue({
      seg_id: 'seg_1_to_2',
      verdict: 'winner',
      notes: null,
      updated_at: '',
    })
    renderAt()
    const btn = await screen.findByRole('button', {
      name: /mark 1_to_2 as winner/i,
    })
    expect(btn).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(btn)
    await waitFor(() =>
      expect(client.reviewSegment).toHaveBeenCalledWith('abc', 'seg_1_to_2', 'winner')
    )
    await waitFor(() => expect(btn).toHaveAttribute('aria-pressed', 'true'))
  })

  it('leaves aria-pressed unchanged if reviewSegment rejects', async () => {
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.listVideos as any).mockResolvedValue([
      { name: 'seg_1_to_2.mp4', pair_key: '1_to_2' },
    ])
    ;(client.listSegments as any).mockResolvedValue([])
    ;(client.reviewSegment as any).mockRejectedValue(new Error('boom'))
    renderAt()
    const btn = await screen.findByRole('button', {
      name: /mark 1_to_2 as redo/i,
    })
    fireEvent.click(btn)
    await waitFor(() => expect(client.reviewSegment).toHaveBeenCalled())
    // Still not pressed after the rejection.
    expect(btn).toHaveAttribute('aria-pressed', 'false')
  })

  it('clicking Stitch & Export triggers startStitch and shows the spinner', async () => {
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.listVideos as any).mockResolvedValue([
      { name: 'seg_1_to_2.mp4', pair_key: '1_to_2' },
    ])
    ;(client.listSegments as any).mockResolvedValue([])
    ;(client.getJob as any).mockResolvedValue({ ...baseJob, status: 'running' })
    renderAt()
    const btn = await screen.findByRole('button', { name: /stitch & export/i })
    fireEvent.click(btn)
    expect(await screen.findByText(/stitching your full movie/i)).toBeInTheDocument()
  })

  it('shows Download full movie link once stitch is done', async () => {
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.listVideos as any).mockResolvedValue([
      { name: 'seg_1_to_2.mp4', pair_key: '1_to_2' },
    ])
    ;(client.listSegments as any).mockResolvedValue([])
    ;(client.getJob as any).mockResolvedValue({ ...baseJob, status: 'done' })
    renderAt()
    const btn = await screen.findByRole('button', { name: /stitch & export/i })
    fireEvent.click(btn)
    const link = await screen.findByRole('link', { name: /download full movie/i })
    expect(link).toHaveAttribute('href', expect.stringMatching(/\/download$/))
    expect(link).toHaveAttribute('download')
  })
})
