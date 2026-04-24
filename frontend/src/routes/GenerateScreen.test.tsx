/**
 * Phase 4 sub-plan 4 Step 7 unit (TDD): each render state of GenerateScreen.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import GenerateScreen from './GenerateScreen'

vi.mock('@/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/api/client')>('@/api/client')
  return {
    ...actual,
    startPromptsGeneration: vi.fn(async () => ({ job_id: 'pjob' })),
    startGenerate: vi.fn(async () => ({ job_id: 'gjob' })),
    getJob: vi.fn(),
    getPrompts: vi.fn(),
    savePrompts: vi.fn(async (_pid: string, m: Record<string, string>) => m),
    listStageOutputs: vi.fn(),
    getProjectOrder: vi.fn(),
    listVideos: vi.fn(),
  }
})

import * as client from '@/api/client'

function renderAt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/abc/generate']}>
        <Routes>
          <Route path="/projects/:projectId/generate" element={<GenerateScreen />} />
          <Route path="/projects/:projectId/review" element={<div>review</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => vi.clearAllMocks())

const jobDone = {
  job_id: 'x',
  project_id: 'abc',
  user_id: 'local',
  kind: 'prompts',
  payload: {},
  error: null as string | null,
  created_at: '',
  updated_at: '',
  status: 'done' as const,
}

describe('GenerateScreen', () => {
  it('shows the prompts-loading state while prompts are being generated', async () => {
    ;(client.getPrompts as any).mockResolvedValue(null) // 404 -> trigger prompts gen
    ;(client.getJob as any).mockResolvedValue({ ...jobDone, status: 'running' })
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    renderAt()
    expect(await screen.findByText(/writing starter prompts/i)).toBeInTheDocument()
  })

  it('renders one PromptRow per pair once prompts resolve', async () => {
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.getPrompts as any).mockResolvedValue({
      '1_to_2': 'prompt-a',
      '2_to_3': 'prompt-b',
    })
    renderAt()
    const textareas = await screen.findAllByRole('textbox', { name: /^prompt for pair /i })
    expect(textareas.length).toBe(2)
    expect(textareas[0]).toHaveValue('prompt-a')
    expect(textareas[1]).toHaveValue('prompt-b')
    expect(screen.getByRole('button', { name: /generate videos/i })).not.toBeDisabled()
  })

  it('triggers one re-gen when server prompts keys do not match expected pair_keys', async () => {
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    // First GET returns stale keys, second returns the expected ones.
    const staleThenFresh = vi
      .fn()
      .mockResolvedValueOnce({ '0_to_1': 'stale' })
      .mockResolvedValue({ '1_to_2': 'fresh-a', '2_to_3': 'fresh-b' })
    ;(client.getPrompts as any).mockImplementation(staleThenFresh)
    ;(client.getJob as any).mockResolvedValue({ ...jobDone, status: 'done' })
    renderAt()
    // Waits for re-gen + re-fetch to converge on fresh keys.
    const textareas = await screen.findAllByRole('textbox', { name: /^prompt for pair /i })
    expect(textareas.length).toBe(2)
    expect(client.startPromptsGeneration).toHaveBeenCalledTimes(1)
  })

  it('shows the rendering spinner while generate job is running', async () => {
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.getPrompts as any).mockResolvedValue({
      '1_to_2': 'p1',
      '2_to_3': 'p2',
    })
    // Click generate, then poll returns 'running'.
    ;(client.getJob as any).mockImplementation((_pid: string, jid: string) =>
      Promise.resolve({ ...jobDone, job_id: jid, status: 'running' })
    )
    renderAt()
    // Wait for prompts to hydrate the local state so the button is enabled.
    await screen.findAllByRole('textbox', { name: /^prompt for pair /i })
    const btn = screen.getByRole('button', { name: /generate videos/i })
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)
    expect(await screen.findByText(/rendering your 1-second clips/i)).toBeInTheDocument()
  })

  it('shows video lightbox triggers and enables Next once generate job is done', async () => {
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.getPrompts as any).mockResolvedValue({
      '1_to_2': 'p1',
      '2_to_3': 'p2',
    })
    ;(client.getJob as any).mockResolvedValue({ ...jobDone, status: 'done' })
    ;(client.listVideos as any).mockResolvedValue([
      { name: 'seg_1_to_2.mp4', pair_key: '1_to_2' },
      { name: 'seg_2_to_3.mp4', pair_key: '2_to_3' },
    ])
    renderAt()
    await screen.findAllByRole('textbox', { name: /^prompt for pair /i })
    const btn = screen.getByRole('button', { name: /generate videos/i })
    await waitFor(() => expect(btn).not.toBeDisabled())
    fireEvent.click(btn)
    // wait for posters + Next enabled
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /^play /i }).length).toBe(2)
    })
    const next = screen.getByRole('button', { name: /next: review/i })
    expect(next).not.toBeDisabled()
  })

  it('passes modes.generatePrompts from useSettings into startPromptsGeneration', async () => {
    // Authentic test (plan-skill #9): flip localStorage to api mode
    // BEFORE mount; useSettings hydrates from it; the screen must
    // pass 'api' not 'mock' into the mutation. Would regress if the
    // mutationFn goes back to a hardcoded 'mock' literal.
    localStorage.clear()
    localStorage.setItem(
      'olga.modes',
      JSON.stringify({
        prepare: 'mock',
        extend: 'mock',
        generatePrompts: 'api',
        generateVideos: 'mock',
        stitch: 'mock',
      })
    )
    ;(client.listStageOutputs as any).mockResolvedValue({
      stage: 'kling_test',
      outputs: ['1.jpg', '2.jpg', '3.jpg'],
    })
    ;(client.getProjectOrder as any).mockResolvedValue(null)
    ;(client.getPrompts as any).mockResolvedValue(null) // triggers re-gen
    ;(client.getJob as any).mockResolvedValue({ ...jobDone, status: 'done' })
    renderAt()
    await waitFor(() =>
      expect(client.startPromptsGeneration).toHaveBeenCalledWith(
        'abc',
        'api',
        'cinematic'
      )
    )
  })
})
