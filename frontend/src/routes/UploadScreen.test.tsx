/**
 * Step 4 (TDD red): Upload screen renders dropzone, file list, and wizard.
 *
 * No network — all tests stub the useCreateProject / useUploadFile hooks
 * via a module mock. Network-integration tests live in the sibling
 * UploadScreen.integration.test.tsx (Step 5).
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import UploadScreen from './UploadScreen'

// Mock the upload hook so clicking Next doesn't actually fire a network call
// in this unit-level suite.
vi.mock('./useUploadFlow', () => ({
  useUploadFlow: () => ({
    runUpload: vi.fn(),
    isRunning: false,
    error: null as string | null,
  }),
}))

function renderScreen() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/new/upload']}>
        <Routes>
          <Route path="/projects/new/upload" element={<UploadScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('UploadScreen', () => {
  it('renders the dropzone heading + CTA copy', () => {
    renderScreen()
    expect(screen.getByRole('heading', { name: /upload your photos/i })).toBeInTheDocument()
    expect(screen.getByText(/drag photos here or click to browse/i)).toBeInTheDocument()
  })

  it('shows empty state when no files dropped', () => {
    renderScreen()
    expect(screen.getByText(/no photos yet/i)).toBeInTheDocument()
  })

  it('adds files when dropped onto the dropzone', async () => {
    renderScreen()
    const dropzone = screen.getByRole('button', { name: /drag photos here/i })
    const file = new File(['img-bytes'], 'hello.png', { type: 'image/png' })
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [file], items: [{ kind: 'file', type: 'image/png', getAsFile: () => file }], types: ['Files'] },
    })
    expect(await screen.findByText('hello.png')).toBeInTheDocument()
    // the "Next" button is enabled once we have at least one file
    expect(screen.getByRole('button', { name: /next/i })).not.toBeDisabled()
  })

  it('Next button is disabled before any file is uploaded', () => {
    renderScreen()
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
  })

  it('remove icon deletes a file from the list', async () => {
    const user = userEvent.setup()
    renderScreen()
    const dropzone = screen.getByRole('button', { name: /drag photos here/i })
    const file = new File(['x'], 'remove-me.png', { type: 'image/png' })
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [file], items: [{ kind: 'file', type: 'image/png', getAsFile: () => file }], types: ['Files'] },
    })
    expect(await screen.findByText('remove-me.png')).toBeInTheDocument()
    const remove = screen.getByRole('button', { name: /remove remove-me.png/i })
    await user.click(remove)
    expect(screen.queryByText('remove-me.png')).not.toBeInTheDocument()
    expect(screen.getByText(/no photos yet/i)).toBeInTheDocument()
  })
})
