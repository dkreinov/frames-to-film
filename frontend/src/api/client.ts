import type {
  Health,
  Project,
  ProjectCreate,
  Upload,
  Job,
  JobRef,
  StageOutputs,
  StylePreset,
  PromptsMap,
  VideoItem,
  Segment,
  Verdict,
} from './types'

export const API_BASE =
  (import.meta as unknown as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ??
  'http://127.0.0.1:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Read stored API keys from localStorage and merge them into request
 * headers. Attached on every request (mode-independent) so the backend's
 * resolve_<vendor>_key helpers can prefer them over .env even for
 * mock-mode flows that happen to inspect the header for logging.
 *
 * Missing/empty key -> no corresponding header attached (backend falls
 * back to env var).
 */
function headersWithKey(base: HeadersInit = {}): HeadersInit {
  try {
    const raw = localStorage.getItem('olga.keys')
    if (!raw) return base
    const parsed = JSON.parse(raw) as { gemini?: string; fal?: string }
    const out: Record<string, string> = { ...(base as Record<string, string>) }
    const gemini = (parsed.gemini || '').trim()
    if (gemini) out['X-Gemini-Key'] = gemini
    const fal = (parsed.fal || '').trim()
    if (fal) out['X-Fal-Key'] = fal
    return out
  } catch {
    return base
  }
}

function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  return fetch(url, { ...init, headers: headersWithKey(init.headers) })
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, `${res.status} ${res.statusText}: ${text}`)
  }
  return (await res.json()) as T
}

export async function getHealth(): Promise<Health> {
  return parse<Health>(await apiFetch(`${API_BASE}/health`))
}

export async function createProject(body: ProjectCreate): Promise<Project> {
  return parse<Project>(
    await apiFetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  )
}

export async function uploadFile(projectId: string, file: File): Promise<Upload> {
  const form = new FormData()
  form.append('file', file)
  return parse<Upload>(
    await apiFetch(`${API_BASE}/projects/${projectId}/uploads`, {
      method: 'POST',
      body: form,
    })
  )
}

export async function listUploads(projectId: string): Promise<Upload[]> {
  return parse<Upload[]>(await apiFetch(`${API_BASE}/projects/${projectId}/uploads`))
}

export async function getJob(projectId: string, jobId: string): Promise<Job> {
  return parse<Job>(
    await apiFetch(`${API_BASE}/projects/${projectId}/jobs/${jobId}`)
  )
}

export async function startPrepare(
  projectId: string,
  mode: 'mock' | 'api' = 'mock'
): Promise<JobRef> {
  return parse<JobRef>(
    await apiFetch(`${API_BASE}/projects/${projectId}/prepare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    })
  )
}

export async function startExtend(
  projectId: string,
  mode: 'mock' | 'api' = 'mock'
): Promise<JobRef> {
  return parse<JobRef>(
    await apiFetch(`${API_BASE}/projects/${projectId}/extend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    })
  )
}

export async function saveProjectOrder(
  projectId: string,
  order: string[]
): Promise<{ order: string[] }> {
  return parse<{ order: string[] }>(
    await apiFetch(`${API_BASE}/projects/${projectId}/order`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order }),
    })
  )
}

export async function getProjectOrder(
  projectId: string
): Promise<string[] | null> {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/order`)
  if (res.status === 404) return null
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, `${res.status}: ${text}`)
  }
  const body = (await res.json()) as { order: string[] }
  return body.order
}

export async function listStageOutputs(
  projectId: string,
  stage: string
): Promise<StageOutputs> {
  return parse<StageOutputs>(
    await apiFetch(`${API_BASE}/projects/${projectId}/outputs/${stage}`)
  )
}

export function artifactUrl(projectId: string, stage: string, name: string): string {
  return `${API_BASE}/projects/${projectId}/artifacts/${stage}/${encodeURIComponent(name)}`
}

export async function startPromptsGeneration(
  projectId: string,
  mode: 'mock' | 'api' = 'mock',
  style: StylePreset = 'cinematic'
): Promise<JobRef> {
  return parse<JobRef>(
    await apiFetch(`${API_BASE}/projects/${projectId}/prompts/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, style }),
    })
  )
}

export async function getPrompts(
  projectId: string
): Promise<PromptsMap | null> {
  const res = await apiFetch(`${API_BASE}/projects/${projectId}/prompts`)
  if (res.status === 404) return null
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, `${res.status}: ${text}`)
  }
  return (await res.json()) as PromptsMap
}

export async function savePrompts(
  projectId: string,
  prompts: PromptsMap
): Promise<PromptsMap> {
  return parse<PromptsMap>(
    await apiFetch(`${API_BASE}/projects/${projectId}/prompts`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompts }),
    })
  )
}

export async function startGenerate(
  projectId: string,
  mode: 'mock' | 'api' = 'mock'
): Promise<JobRef> {
  return parse<JobRef>(
    await apiFetch(`${API_BASE}/projects/${projectId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    })
  )
}

export async function listVideos(projectId: string): Promise<VideoItem[]> {
  const body = await parse<{ videos: VideoItem[] }>(
    await apiFetch(`${API_BASE}/projects/${projectId}/videos`)
  )
  return body.videos
}

export function videoUrl(projectId: string, name: string): string {
  return `${API_BASE}/projects/${projectId}/artifacts/clips/raw/${encodeURIComponent(name)}`
}

export async function listSegments(projectId: string): Promise<Segment[]> {
  const body = await parse<{ segments: Segment[] }>(
    await apiFetch(`${API_BASE}/projects/${projectId}/segments`)
  )
  return body.segments
}

export async function reviewSegment(
  projectId: string,
  segId: string,
  verdict: Verdict,
  notes?: string
): Promise<Segment> {
  return parse<Segment>(
    await apiFetch(`${API_BASE}/projects/${projectId}/segments/${segId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verdict, notes: notes ?? null }),
    })
  )
}

export async function startStitch(
  projectId: string,
  mode: 'mock' | 'api' = 'mock'
): Promise<JobRef> {
  return parse<JobRef>(
    await apiFetch(`${API_BASE}/projects/${projectId}/stitch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    })
  )
}

export function downloadUrl(projectId: string): string {
  return `${API_BASE}/projects/${projectId}/download`
}

export type {
  Health,
  Project,
  ProjectCreate,
  Upload,
  Job,
  JobRef,
  StageOutputs,
  StylePreset,
  PromptsMap,
  VideoItem,
  Segment,
  Verdict,
}
