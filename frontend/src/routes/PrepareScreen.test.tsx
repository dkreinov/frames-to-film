/**
 * Step 5 unit tests (TDD): renders each state.
 *
 * Mocks the api/client module so we can force jobQuery/outputsQuery
 * states without running a real network loop.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import PrepareScreen from './PrepareScreen'

vi.mock('@/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/api/client')>('@/api/client')
  return {
    ...actual,
    startPrepare: vi.fn(async () => ({ job_id: 'jid-1' })),
    getJob: vi.fn(),
    listStageOutputs: vi.fn(),
  }
})

import * as client from '@/api/client'

function renderAt(pid: string = 'abc') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/projects/${pid}/prepare`]}>
        <Routes>
          <Route path="/projects/:projectId/prepare" element={<PrepareScreen />} />
          <Route path="/projects/:projectId/storyboard" element={<div>storyboard</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('PrepareScreen', () => {
  it('renders the running state when job is pending/running', async () => {
    ;(client.getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      job_id: 'jid-1',
      status: 'running',
      project_id: 'abc',
      user_id: 'local',
      kind: 'prepare',
      payload: {},
      error: null,
      created_at: '',
      updated_at: '',
    })
    renderAt()
    expect(await screen.findByText(/preparing photos/i)).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders OutputsGrid when job is done', async () => {
    ;(client.getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      job_id: 'jid-1',
      status: 'done',
      project_id: 'abc',
      user_id: 'local',
      kind: 'prepare',
      payload: {},
      error: null,
      created_at: '',
      updated_at: '',
    })
    ;(client.listStageOutputs as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      stage: 'extended/_4_3',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    renderAt()
    expect(await screen.findByText(/prepared 3 photos/i)).toBeInTheDocument()
    expect(screen.getAllByRole('img').length).toBe(3)
    // Next button becomes enabled
    expect(screen.getByRole('button', { name: /next/i })).not.toBeDisabled()
  })

  it('renders error state with retry button', async () => {
    ;(client.getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      job_id: 'jid-1',
      status: 'error',
      project_id: 'abc',
      user_id: 'local',
      kind: 'prepare',
      payload: {},
      error: 'extended/_4_3 dir missing',
      created_at: '',
      updated_at: '',
    })
    renderAt()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/extended\/_4_3 dir missing/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('Next button is disabled before job done', async () => {
    ;(client.getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      job_id: 'jid-1',
      status: 'running',
      project_id: 'abc',
      user_id: 'local',
      kind: 'prepare',
      payload: {},
      error: null,
      created_at: '',
      updated_at: '',
    })
    renderAt()
    await screen.findByRole('status')
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
  })

  it('passes modes.prepare from useSettings into startPrepare (api override)', async () => {
    // Authentic test (plan-skill #9): seeding localStorage to api
    // mode must reach the mutation fn. Would regress if mutationFn
    // goes back to a hardcoded 'mock' literal.
    localStorage.clear()
    localStorage.setItem(
      'olga.modes',
      JSON.stringify({
        prepare: 'api',
        extend: 'mock',
        generatePrompts: 'mock',
        generateVideos: 'mock',
        stitch: 'mock',
      })
    )
    ;(client.getJob as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      job_id: 'jid-1',
      status: 'running',
      project_id: 'abc',
      user_id: 'local',
      kind: 'prepare',
      payload: {},
      error: null,
      created_at: '',
      updated_at: '',
    })
    renderAt()
    await screen.findByText(/preparing photos/i)
    expect(client.startPrepare).toHaveBeenCalledWith('abc', 'api')
  })
})
