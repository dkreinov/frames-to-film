/**
 * Step 5 integration test: mount triggers POST /prepare, polls /jobs,
 * loads /outputs, renders grid.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import PrepareScreen from './PrepareScreen'

let pollCount = 0

const server = setupServer(
  http.post('http://127.0.0.1:8000/projects/:pid/prepare', () =>
    HttpResponse.json({ job_id: 'jid-int' }, { status: 202 })
  ),
  http.get('http://127.0.0.1:8000/projects/:pid/jobs/:jid', () => {
    pollCount++
    // First poll: running. Second+: done.
    const status = pollCount >= 2 ? 'done' : 'running'
    return HttpResponse.json({
      job_id: 'jid-int',
      project_id: 'pid-int',
      user_id: 'local',
      kind: 'prepare',
      status,
      payload: {},
      error: null,
      created_at: '',
      updated_at: '',
    })
  }),
  http.get('http://127.0.0.1:8000/projects/:pid/outputs/outpainted', () =>
    HttpResponse.json({ stage: 'outpainted', outputs: ['1.jpg', '2.jpg'] })
  )
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  pollCount = 0
})
afterAll(() => server.close())

function renderAt(pid: string = 'pid-int') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/projects/${pid}/prepare`]}>
        <Routes>
          <Route path="/projects/:projectId/prepare" element={<PrepareScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('PrepareScreen integration', () => {
  it('auto-starts prepare, polls until done, renders grid', async () => {
    renderAt()
    // Initially shows the running card (first poll returns running).
    expect(await screen.findByText(/preparing photos/i)).toBeInTheDocument()
    // Eventually the grid appears.
    expect(await screen.findByText(/prepared 2 photos/i, {}, { timeout: 5_000 })).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /next/i })).not.toBeDisabled()
    })
  })

  it('shows error card if prepare fails', async () => {
    server.use(
      http.get('http://127.0.0.1:8000/projects/:pid/jobs/:jid', () =>
        HttpResponse.json({
          job_id: 'jid-int',
          project_id: 'pid-int',
          user_id: 'local',
          kind: 'prepare',
          status: 'error',
          payload: {},
          error: 'outpainted dir missing',
          created_at: '',
          updated_at: '',
        })
      )
    )
    renderAt()
    expect(await screen.findByRole('alert', {}, { timeout: 5_000 })).toBeInTheDocument()
    expect(screen.getByText(/outpainted dir missing/i)).toBeInTheDocument()
  })
})
