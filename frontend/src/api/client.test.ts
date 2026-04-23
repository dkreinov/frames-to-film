/**
 * Step 2 (TDD red): API client contract.
 *
 * Covers:
 *  - getHealth() -> Health
 *  - 5xx throws an Error
 *  - createProject() -> Project
 *  - uploadFile() -> Upload (multipart POST)
 */
import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import {
  getHealth,
  createProject,
  uploadFile,
  ApiError,
  startPrepare,
  listStageOutputs,
  artifactUrl,
} from './client'

const server = setupServer(
  http.get('http://127.0.0.1:8000/health', () =>
    HttpResponse.json({ status: 'ok' })
  ),
  http.post('http://127.0.0.1:8000/projects', async ({ request }) => {
    const body = (await request.json()) as { name: string }
    return HttpResponse.json(
      {
        project_id: 'abc123',
        user_id: 'local',
        name: body.name,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      { status: 201 }
    )
  }),
  http.post(
    'http://127.0.0.1:8000/projects/:pid/uploads',
    () =>
      HttpResponse.json(
        {
          upload_id: 'u1',
          filename: 'f.png',
          size_bytes: 10,
          created_at: '2026-01-01T00:00:00Z',
        },
        { status: 201 }
      )
  )
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('api client', () => {
  it('getHealth returns status ok', async () => {
    const h = await getHealth()
    expect(h).toEqual({ status: 'ok' })
  })

  it('getHealth throws ApiError on 5xx', async () => {
    server.use(
      http.get('http://127.0.0.1:8000/health', () =>
        HttpResponse.text('nope', { status: 503 })
      )
    )
    await expect(getHealth()).rejects.toBeInstanceOf(ApiError)
  })

  it('createProject returns a Project with name', async () => {
    const p = await createProject({ name: 'Test' })
    expect(p.name).toBe('Test')
    expect(p.project_id).toBe('abc123')
    expect(p.user_id).toBe('local')
  })

  it('uploadFile posts multipart and returns Upload', async () => {
    const file = new File([new Uint8Array([1, 2, 3])], 'f.png', { type: 'image/png' })
    const u = await uploadFile('abc123', file)
    expect(u.upload_id).toBe('u1')
    expect(u.filename).toBe('f.png')
  })

  it('startPrepare posts {mode} and returns a job_id', async () => {
    server.use(
      http.post('http://127.0.0.1:8000/projects/:pid/prepare', async ({ request }) => {
        const body = (await request.json()) as { mode: string }
        return HttpResponse.json({ job_id: `jid-${body.mode}` }, { status: 202 })
      })
    )
    const r = await startPrepare('abc123', 'mock')
    expect(r.job_id).toBe('jid-mock')
  })

  it('listStageOutputs returns the array of names', async () => {
    server.use(
      http.get('http://127.0.0.1:8000/projects/:pid/outputs/:stage', () =>
        HttpResponse.json({ stage: 'outpainted', outputs: ['1.jpg', '2.jpg'] })
      )
    )
    const r = await listStageOutputs('abc123', 'outpainted')
    expect(r.outputs).toEqual(['1.jpg', '2.jpg'])
  })

  it('artifactUrl URL-encodes the filename', () => {
    expect(artifactUrl('p', 'outpainted', 'a b.jpg')).toBe(
      'http://127.0.0.1:8000/projects/p/artifacts/outpainted/a%20b.jpg'
    )
  })
})
