/**
 * Phase 4 sub-plan 4 Step 8: real network flow via MSW.
 *
 * Full pipeline: prompts missing -> auto-gen -> prompts load ->
 * edit one textarea -> debounced PUT fires -> click Generate -> poll
 * job to done -> /videos list appears -> poster opens lightbox.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import GenerateScreen from './GenerateScreen'

let promptsGenCalls = 0
let generateCalls = 0
const putPromptsCalls: Record<string, string>[] = []
let serverPrompts: Record<string, string> | null = null
let videosAvailable = false

const BASE = 'http://127.0.0.1:8000'

const server = setupServer(
  // Outputs: frames are ready.
  http.get(`${BASE}/projects/:pid/outputs/extended`, () =>
    HttpResponse.json({ stage: 'extended', outputs: ['1.jpg', '2.jpg', '3.jpg'] })
  ),
  // Order: none set (natural order).
  http.get(`${BASE}/projects/:pid/order`, () =>
    HttpResponse.text('not set', { status: 404 })
  ),
  // Prompts GET: 404 until generation completes, then the stored map.
  http.get(`${BASE}/projects/:pid/prompts`, () => {
    if (serverPrompts === null) return HttpResponse.text('not yet', { status: 404 })
    return HttpResponse.json(serverPrompts)
  }),
  // Prompts generate: create the default map on disk.
  http.post(`${BASE}/projects/:pid/prompts/generate`, () => {
    promptsGenCalls++
    serverPrompts = {
      '1_to_2': 'starter prompt a',
      '2_to_3': 'starter prompt b',
    }
    return HttpResponse.json({ job_id: 'pjob-int' }, { status: 202 })
  }),
  // Prompts PUT: echo back and record.
  http.put(`${BASE}/projects/:pid/prompts`, async ({ request }) => {
    const body = (await request.json()) as { prompts: Record<string, string> }
    putPromptsCalls.push(body.prompts)
    serverPrompts = { ...body.prompts }
    return HttpResponse.json(body.prompts)
  }),
  // Generate POST.
  http.post(`${BASE}/projects/:pid/generate`, () => {
    generateCalls++
    return HttpResponse.json({ job_id: 'gjob-int' }, { status: 202 })
  }),
  // Jobs: both prompts and generate jobs report done immediately.
  http.get(`${BASE}/projects/:pid/jobs/:jid`, ({ params }) => {
    if (params.jid === 'gjob-int') videosAvailable = true
    return HttpResponse.json({
      job_id: params.jid,
      project_id: params.pid,
      user_id: 'local',
      kind: 'prompts',
      status: 'done',
      payload: {},
      error: null,
      created_at: '',
      updated_at: '',
    })
  }),
  // Videos list: empty until generate has completed.
  http.get(`${BASE}/projects/:pid/videos`, () => {
    if (!videosAvailable) return HttpResponse.json({ videos: [] })
    return HttpResponse.json({
      videos: [
        { name: 'seg_1_to_2.mp4', pair_key: '1_to_2' },
        { name: 'seg_2_to_3.mp4', pair_key: '2_to_3' },
      ],
    })
  })
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  promptsGenCalls = 0
  generateCalls = 0
  putPromptsCalls.length = 0
  serverPrompts = null
  videosAvailable = false
})
afterAll(() => server.close())

function renderAt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/pid-int/generate']}>
        <Routes>
          <Route path="/projects/:projectId/generate" element={<GenerateScreen />} />
          <Route path="/projects/:projectId/review" element={<div>review</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('GenerateScreen integration', () => {
  it('auto-generates prompts when missing, then renders editable rows with no PUT echo', async () => {
    renderAt()
    // Loading state appears first.
    expect(await screen.findByText(/writing starter prompts/i)).toBeInTheDocument()
    // Wait for rows to render from the generated prompts.
    const rows = await screen.findAllByRole('textbox', { name: /^prompt for pair /i })
    expect(rows.length).toBe(2)
    await waitFor(() => expect(promptsGenCalls).toBe(1))
    // Regression: no PUT /prompts on initial seed of local state.
    await new Promise((r) => setTimeout(r, 400))
    expect(putPromptsCalls.length).toBe(0)
  })

  it('debounces PUT /prompts on textarea edit', async () => {
    renderAt()
    const rows = await screen.findAllByRole('textbox', { name: /^prompt for pair /i })
    fireEvent.change(rows[0], { target: { value: 'edited text' } })
    await waitFor(
      () => expect(putPromptsCalls.length).toBe(1),
      { timeout: 1000 }
    )
    // The PUT contains the full map including the edit.
    expect(putPromptsCalls[0]['1_to_2']).toBe('edited text')
    expect(putPromptsCalls[0]['2_to_3']).toBe('starter prompt b')
  })

  it('clicking Generate videos fires POST /generate, polls done, and renders lightbox posters', async () => {
    renderAt()
    await screen.findAllByRole('textbox', { name: /^prompt for pair /i })
    const btn = screen.getByRole('button', { name: /generate videos/i })
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)
    await waitFor(() => expect(generateCalls).toBe(1))
    // Two posters once /videos returns them.
    const posters = await screen.findAllByRole('button', { name: /^play /i })
    expect(posters.length).toBe(2)
    // Next: Review footer button is enabled now.
    const next = screen.getByRole('button', { name: /next: review/i })
    expect(next).not.toBeDisabled()
    // Opening a poster mounts the <video>.
    fireEvent.click(posters[0])
    await waitFor(() => expect(document.querySelector('video')).not.toBeNull())
  })
})
