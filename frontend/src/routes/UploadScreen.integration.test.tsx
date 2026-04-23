/**
 * Step 5 (TDD red): clicking Next fires createProject + uploadFile per file,
 * then navigates to /projects/:id/prepare.
 *
 * Uses MSW to mock the real FastAPI endpoints — no mock on useUploadFlow
 * here (that's the unit-test file). Response shapes mirror
 * backend/routers/projects.py + uploads.py exactly.
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import UploadScreen from './UploadScreen'

let uploadCount = 0
let createCount = 0

const server = setupServer(
  http.post('http://127.0.0.1:8000/projects', async () => {
    createCount++
    return HttpResponse.json(
      {
        project_id: 'pid-int',
        user_id: 'local',
        name: 'test',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      { status: 201 }
    )
  }),
  http.post('http://127.0.0.1:8000/projects/:pid/uploads', async () => {
    uploadCount++
    return HttpResponse.json(
      {
        upload_id: `u-${uploadCount}`,
        filename: `f${uploadCount}.png`,
        size_bytes: 10,
        created_at: '2026-01-01T00:00:00Z',
      },
      { status: 201 }
    )
  })
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  uploadCount = 0
  createCount = 0
})
afterAll(() => server.close())

function LocationTracker({ onPath }: { onPath: (p: string) => void }) {
  const loc = useLocation()
  onPath(loc.pathname)
  return null
}

function renderWithRouter() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  let currentPath = '/projects/new/upload'
  const rec = render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/new/upload']}>
        <LocationTracker onPath={(p) => (currentPath = p)} />
        <Routes>
          <Route path="/projects/new/upload" element={<UploadScreen />} />
          <Route path="/projects/:projectId/prepare" element={<div>prepare placeholder</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
  return { ...rec, getPath: () => currentPath }
}

function dropFiles(n: number) {
  const dropzone = screen.getByRole('button', { name: /drag photos here/i })
  const files = Array.from({ length: n }, (_, i) =>
    new File([`x${i}`], `img${i + 1}.png`, { type: 'image/png' })
  )
  fireEvent.drop(dropzone, {
    dataTransfer: {
      files,
      items: files.map((f) => ({ kind: 'file', type: f.type, getAsFile: () => f })),
      types: ['Files'],
    },
  })
  return files
}

describe('UploadScreen integration', () => {
  it('clicking Next posts /projects once then N uploads and navigates to prepare', async () => {
    const { getPath } = renderWithRouter()
    dropFiles(2)
    await screen.findByText('img1.png')
    await screen.findByText('img2.png')

    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    await waitFor(() => expect(createCount).toBe(1))
    await waitFor(() => expect(uploadCount).toBe(2))
    await waitFor(() => expect(getPath()).toBe('/projects/pid-int/prepare'))
  })

  it('does not navigate when Next is never clicked', async () => {
    const { getPath } = renderWithRouter()
    dropFiles(1)
    await screen.findByText('img1.png')
    // no click -> still at /projects/new/upload
    expect(getPath()).toBe('/projects/new/upload')
    expect(createCount).toBe(0)
    expect(uploadCount).toBe(0)
  })

  it('shows an error message when createProject 5xx', async () => {
    server.use(
      http.post('http://127.0.0.1:8000/projects', () =>
        HttpResponse.text('boom', { status: 500 })
      )
    )
    renderWithRouter()
    dropFiles(1)
    await screen.findByText('img1.png')
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/500/)
  })
})
