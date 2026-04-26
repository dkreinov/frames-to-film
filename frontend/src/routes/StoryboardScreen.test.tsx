/**
 * Step 6 unit (TDD): each render state.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import StoryboardScreen from './StoryboardScreen'

vi.mock('@/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/api/client')>('@/api/client')
  return {
    ...actual,
    startExtend: vi.fn(async () => ({ job_id: 'jid-x' })),
    getJob: vi.fn(),
    listStageOutputs: vi.fn(),
    getProjectOrder: vi.fn(),
    saveProjectOrder: vi.fn(async () => ({ order: [] })),
  }
})

import * as client from '@/api/client'

function renderAt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/abc/storyboard']}>
        <Routes>
          <Route path="/projects/:projectId/storyboard" element={<StoryboardScreen />} />
          <Route path="/projects/:projectId/generate" element={<div>generate</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => vi.clearAllMocks())

const baseJob = {
  job_id: 'jid-x',
  project_id: 'abc',
  user_id: 'local',
  kind: 'extend',
  payload: {},
  error: null as string | null,
  created_at: '',
  updated_at: '',
}

describe('StoryboardScreen', () => {
  it('renders the running state while extend is in progress', async () => {
    ;(client.getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...baseJob,
      status: 'running',
    })
    renderAt()
    expect(await screen.findByText(/building 16:9 frames/i)).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders SortableGrid when extend is done', async () => {
    ;(client.getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...baseJob,
      status: 'done',
    })
    ;(client.listStageOutputs as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      stage: 'extended',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    ;(client.getProjectOrder as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(null)
    renderAt()
    // 3 thumbnails rendered (each has aria-label "Frame N, name")
    const drag = await screen.findAllByRole('button', { name: /^drag frame /i })
    expect(drag.length).toBe(3)
    expect(screen.getByRole('button', { name: /next/i })).not.toBeDisabled()
  })

  it('shows error card with retry on extend failure', async () => {
    ;(client.getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...baseJob,
      status: 'error',
      error: 'extended/_4_3 dir missing',
    })
    renderAt()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})
