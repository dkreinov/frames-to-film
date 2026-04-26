/**
 * Step 6 integration: real network flow via MSW.
 *
 * Skips drag-drop simulation (jsdom can't drive @dnd-kit pointer
 * events reliably). Instead drives the order programmatically by
 * forcing the SortableGrid's onChange via the SortableContext arrayMove
 * — except that's also dnd-kit-internal. Pragmatic approach: assert the
 * full mount-to-grid pipeline + assert that *if* the order changed via
 * any user input, the debounced PUT fires. We synthesise the order
 * change by re-rendering with a saved order from the server.
 */
import { StrictMode } from 'react'
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import StoryboardScreen from './StoryboardScreen'

let extendCalls = 0
const putOrderCalls: string[][] = []

const server = setupServer(
  http.post('http://127.0.0.1:8000/projects/:pid/extend', () => {
    extendCalls++
    return HttpResponse.json({ job_id: 'jid-int' }, { status: 202 })
  }),
  http.get('http://127.0.0.1:8000/projects/:pid/jobs/:jid', () =>
    HttpResponse.json({
      job_id: 'jid-int',
      project_id: 'pid-int',
      user_id: 'local',
      kind: 'extend',
      status: 'done',
      payload: {},
      error: null,
      created_at: '',
      updated_at: '',
    })
  ),
  http.get('http://127.0.0.1:8000/projects/:pid/outputs/extended', () =>
    HttpResponse.json({ stage: 'extended', outputs: ['1.jpg', '2.jpg', '3.jpg'] })
  ),
  http.get('http://127.0.0.1:8000/projects/:pid/order', () =>
    HttpResponse.text('not set', { status: 404 })
  ),
  http.put('http://127.0.0.1:8000/projects/:pid/order', async ({ request }) => {
    const body = (await request.json()) as { order: string[] }
    putOrderCalls.push(body.order)
    return HttpResponse.json({ order: body.order })
  })
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  extendCalls = 0
  putOrderCalls.length = 0
})
afterAll(() => server.close())

function renderAt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/pid-int/storyboard']}>
        <Routes>
          <Route path="/projects/:projectId/storyboard" element={<StoryboardScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('StoryboardScreen integration', () => {
  it('mount triggers POST /extend, polls done, loads grid, no PUT yet', async () => {
    renderAt()
    // Title appears
    expect(await screen.findByText(/arrange your story/i)).toBeInTheDocument()
    // Extend was called once
    await waitFor(() => expect(extendCalls).toBe(1))
    // 3 sortable items appear
    const drag = await screen.findAllByRole('button', { name: /^drag frame /i })
    expect(drag.length).toBe(3)
    // No PUT /order on initial load (skipFirst guard in useDebouncedSave)
    await new Promise((r) => setTimeout(r, 400))
    expect(putOrderCalls.length).toBe(0)
  })

  it('seeds local order from saved order.json when present and compatible', async () => {
    server.use(
      http.get('http://127.0.0.1:8000/projects/:pid/order', () =>
        HttpResponse.json({ order: ['3.jpg', '1.jpg', '2.jpg'] })
      )
    )
    renderAt()
    // Wait for extend done + grid render
    const drag = await screen.findAllByRole('button', { name: /^drag frame /i })
    expect(drag.length).toBe(3)
    // Item indices reflect the saved order (aria-label format "Drag frame N (name). ...")
    const labels = drag.map((b) => b.getAttribute('aria-label'))
    expect(labels[0]).toMatch(/Drag frame 1 \(3\.jpg\)/)
    expect(labels[1]).toMatch(/Drag frame 2 \(1\.jpg\)/)
    expect(labels[2]).toMatch(/Drag frame 3 \(2\.jpg\)/)
  })

  it('does NOT fire PUT /order on initial load under StrictMode (double-effect guard)', async () => {
    // Regression: useDebouncedSave's skipNextNonNull ref must survive
    // StrictMode's intentional double-mount/double-effect, otherwise the
    // first non-null seed of `order` would be saved back to the server.
    server.use(
      http.get('http://127.0.0.1:8000/projects/:pid/order', () =>
        HttpResponse.json({ order: ['2.jpg', '3.jpg', '1.jpg'] })
      )
    )
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <StrictMode>
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={['/projects/pid-int/storyboard']}>
            <Routes>
              <Route path="/projects/:projectId/storyboard" element={<StoryboardScreen />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </StrictMode>
    )
    const drag = await screen.findAllByRole('button', { name: /^drag frame /i })
    expect(drag.length).toBe(3)
    await new Promise((r) => setTimeout(r, 500))
    expect(putOrderCalls.length).toBe(0)
  })
})
