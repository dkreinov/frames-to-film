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
  startExtend,
  listStageOutputs,
  artifactUrl,
  saveProjectOrder,
  getProjectOrder,
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
      http.get(
        'http://127.0.0.1:8000/projects/:pid/outputs/extended/_4_3',
        () => HttpResponse.json({ stage: 'extended/_4_3', outputs: ['1.jpg', '2.jpg'] })
      )
    )
    const r = await listStageOutputs('abc123', 'extended/_4_3')
    expect(r.outputs).toEqual(['1.jpg', '2.jpg'])
  })

  it('artifactUrl URL-encodes the filename', () => {
    expect(artifactUrl('p', 'extended/_4_3', 'a b.jpg')).toBe(
      'http://127.0.0.1:8000/projects/p/artifacts/extended/_4_3/a%20b.jpg'
    )
  })

  it('startExtend posts {mode} and returns a job_id', async () => {
    server.use(
      http.post('http://127.0.0.1:8000/projects/:pid/extend', async ({ request }) => {
        const body = (await request.json()) as { mode: string }
        return HttpResponse.json({ job_id: `xid-${body.mode}` }, { status: 202 })
      })
    )
    const r = await startExtend('abc', 'mock')
    expect(r.job_id).toBe('xid-mock')
  })

  it('saveProjectOrder PUTs the order and returns the saved list', async () => {
    server.use(
      http.put('http://127.0.0.1:8000/projects/:pid/order', async ({ request }) => {
        const body = (await request.json()) as { order: string[] }
        return HttpResponse.json({ order: body.order })
      })
    )
    const r = await saveProjectOrder('abc', ['1.jpg', '3.jpg', '2.jpg'])
    expect(r.order).toEqual(['1.jpg', '3.jpg', '2.jpg'])
  })

  it('getProjectOrder returns the saved list or null on 404', async () => {
    server.use(
      http.get('http://127.0.0.1:8000/projects/abc/order', () =>
        HttpResponse.json({ order: ['1.jpg', '2.jpg'] })
      ),
      http.get('http://127.0.0.1:8000/projects/none/order', () =>
        HttpResponse.text('nope', { status: 404 })
      )
    )
    expect(await getProjectOrder('abc')).toEqual(['1.jpg', '2.jpg'])
    expect(await getProjectOrder('none')).toBeNull()
  })
})

// --- Phase 4 sub-plan 6 Step 3: X-Gemini-Key header attachment ---

describe('api client: X-Gemini-Key header', () => {
  let lastGeminiHeader: string | null = null

  async function run(keyValue: string | null) {
    // afterEach() calls server.resetHandlers() between tests — so each
    // test re-registers its own handler rather than relying on beforeAll.
    server.use(
      http.post(
        'http://127.0.0.1:8000/projects/:pid/prompts/generate',
        ({ request }) => {
          lastGeminiHeader = request.headers.get('x-gemini-key')
          return HttpResponse.json({ job_id: 'jhk' }, { status: 202 })
        }
      )
    )
    localStorage.clear()
    lastGeminiHeader = null
    if (keyValue !== null) {
      localStorage.setItem('olga.keys', JSON.stringify({ gemini: keyValue }))
    }
    const { startPromptsGeneration } = await import('./client')
    await startPromptsGeneration('pid-x', 'mock', 'cinematic')
  }

  it('attaches X-Gemini-Key when olga.keys.gemini is set', async () => {
    await run('sk-abc-123')
    expect(lastGeminiHeader).toBe('sk-abc-123')
  })

  it('omits the header when no Gemini key is stored', async () => {
    await run(null)
    expect(lastGeminiHeader).toBeNull()
  })

  it('omits the header when the stored key is whitespace only', async () => {
    await run('   ')
    expect(lastGeminiHeader).toBeNull()
  })
})

// --- Phase 5 sub-plan 2 Step 10: X-Fal-Key header attachment ---

describe('api client: X-Fal-Key header', () => {
  let lastFalHeader: string | null = null
  let lastGeminiHeader: string | null = null

  async function run(keys: { gemini?: string; fal?: string }) {
    server.use(
      http.post(
        'http://127.0.0.1:8000/projects/:pid/generate',
        ({ request }) => {
          lastFalHeader = request.headers.get('x-fal-key')
          lastGeminiHeader = request.headers.get('x-gemini-key')
          return HttpResponse.json({ job_id: 'jid-gen' }, { status: 202 })
        }
      )
    )
    localStorage.clear()
    lastFalHeader = null
    lastGeminiHeader = null
    localStorage.setItem('olga.keys', JSON.stringify(keys))
    const { startGenerate } = await import('./client')
    await startGenerate('pid-gen', 'api')
  }

  it('attaches X-Fal-Key when olga.keys.fal is set', async () => {
    await run({ fal: 'fal-xyz-777' })
    expect(lastFalHeader).toBe('fal-xyz-777')
  })

  it('attaches both X-Fal-Key and X-Gemini-Key when both are set', async () => {
    await run({ gemini: 'gem-1', fal: 'fal-2' })
    expect(lastGeminiHeader).toBe('gem-1')
    expect(lastFalHeader).toBe('fal-2')
  })

  it('omits X-Fal-Key when only gemini is set', async () => {
    await run({ gemini: 'gem-only' })
    expect(lastGeminiHeader).toBe('gem-only')
    expect(lastFalHeader).toBeNull()
  })

  it('omits X-Fal-Key when the stored value is empty', async () => {
    await run({ fal: '' })
    expect(lastFalHeader).toBeNull()
  })

  it('omits X-Fal-Key when the stored value is whitespace only', async () => {
    await run({ fal: '   ' })
    expect(lastFalHeader).toBeNull()
  })
})
