/**
 * Phase 4 sub-plan 5 Step 6: real network flow via MSW.
 *
 * Full pipeline: mount -> GETs hydrate rows -> verdict click POSTs ->
 * Stitch & Export -> job polls done -> Download link appears.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import ReviewScreen from './ReviewScreen'

const BASE = 'http://127.0.0.1:8000'

const postedReviews: Array<{ segId: string; verdict: string }> = []
let stitchCalls = 0
let serverSegments: Array<{
  seg_id: string
  verdict: string
  notes: string | null
  updated_at: string
}> = []

const server = setupServer(
  http.get(`${BASE}/projects/:pid/outputs/kling_test`, () =>
    HttpResponse.json({ stage: 'kling_test', outputs: ['1.jpg', '2.jpg', '3.jpg'] })
  ),
  http.get(`${BASE}/projects/:pid/order`, () =>
    HttpResponse.text('not set', { status: 404 })
  ),
  http.get(`${BASE}/projects/:pid/videos`, () =>
    HttpResponse.json({
      videos: [
        { name: 'seg_1_to_2.mp4', pair_key: '1_to_2' },
        { name: 'seg_2_to_3.mp4', pair_key: '2_to_3' },
      ],
    })
  ),
  http.get(`${BASE}/projects/:pid/segments`, () =>
    HttpResponse.json({ segments: serverSegments })
  ),
  http.post(
    `${BASE}/projects/:pid/segments/:segId/review`,
    async ({ params, request }) => {
      const body = (await request.json()) as { verdict: string; notes: string | null }
      postedReviews.push({ segId: String(params.segId), verdict: body.verdict })
      const row = {
        seg_id: String(params.segId),
        verdict: body.verdict,
        notes: body.notes,
        updated_at: '2026-04-24T00:00:00Z',
      }
      serverSegments = [
        ...serverSegments.filter((s) => s.seg_id !== row.seg_id),
        row,
      ]
      return HttpResponse.json(row)
    }
  ),
  http.post(`${BASE}/projects/:pid/stitch`, () => {
    stitchCalls++
    return HttpResponse.json({ job_id: 'sjob-int' }, { status: 202 })
  }),
  http.get(`${BASE}/projects/:pid/jobs/:jid`, ({ params }) =>
    HttpResponse.json({
      job_id: params.jid,
      project_id: params.pid,
      user_id: 'local',
      kind: 'stitch',
      status: 'done',
      payload: {},
      error: null,
      created_at: '',
      updated_at: '',
    })
  )
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  postedReviews.length = 0
  stitchCalls = 0
  serverSegments = []
})
afterAll(() => server.close())

function renderAt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/pid-int/review']}>
        <Routes>
          <Route path="/projects/:projectId/review" element={<ReviewScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ReviewScreen integration', () => {
  it('hydrates persisted verdicts from listSegments', async () => {
    serverSegments = [
      { seg_id: 'seg_1_to_2', verdict: 'winner', notes: null, updated_at: '' },
    ]
    renderAt()
    const winner = await screen.findByRole('button', {
      name: /mark 1_to_2 as winner/i,
    })
    await waitFor(() =>
      expect(winner).toHaveAttribute('aria-pressed', 'true')
    )
  })

  it('clicking a verdict fires POST with the right body', async () => {
    renderAt()
    const btn = await screen.findByRole('button', {
      name: /mark 2_to_3 as redo/i,
    })
    fireEvent.click(btn)
    await waitFor(() => expect(postedReviews.length).toBe(1))
    expect(postedReviews[0]).toEqual({ segId: 'seg_2_to_3', verdict: 'redo' })
    await waitFor(() => expect(btn).toHaveAttribute('aria-pressed', 'true'))
  })

  it('Stitch & Export triggers POST, polls done, reveals Download link', async () => {
    renderAt()
    await screen.findByRole('button', { name: /mark 1_to_2 as winner/i })
    const stitchBtn = screen.getByRole('button', { name: /stitch & export/i })
    fireEvent.click(stitchBtn)
    await waitFor(() => expect(stitchCalls).toBe(1))
    const link = await screen.findByRole('link', { name: /download full movie/i })
    expect(link.getAttribute('href')).toMatch(/\/projects\/pid-int\/download$/)
    expect(link.hasAttribute('download')).toBe(true)
  })
})
