import type { Health, Project, ProjectCreate, Upload, Job, JobRef, StageOutputs } from './types'

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

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, `${res.status} ${res.statusText}: ${text}`)
  }
  return (await res.json()) as T
}

export async function getHealth(): Promise<Health> {
  return parse<Health>(await fetch(`${API_BASE}/health`))
}

export async function createProject(body: ProjectCreate): Promise<Project> {
  return parse<Project>(
    await fetch(`${API_BASE}/projects`, {
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
    await fetch(`${API_BASE}/projects/${projectId}/uploads`, {
      method: 'POST',
      body: form,
    })
  )
}

export async function listUploads(projectId: string): Promise<Upload[]> {
  return parse<Upload[]>(await fetch(`${API_BASE}/projects/${projectId}/uploads`))
}

export async function getJob(projectId: string, jobId: string): Promise<Job> {
  return parse<Job>(
    await fetch(`${API_BASE}/projects/${projectId}/jobs/${jobId}`)
  )
}

export async function startPrepare(
  projectId: string,
  mode: 'mock' | 'api' = 'mock'
): Promise<JobRef> {
  return parse<JobRef>(
    await fetch(`${API_BASE}/projects/${projectId}/prepare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    })
  )
}

export async function listStageOutputs(
  projectId: string,
  stage: string
): Promise<StageOutputs> {
  return parse<StageOutputs>(
    await fetch(`${API_BASE}/projects/${projectId}/outputs/${stage}`)
  )
}

export function artifactUrl(projectId: string, stage: string, name: string): string {
  return `${API_BASE}/projects/${projectId}/artifacts/${stage}/${encodeURIComponent(name)}`
}

export type { Health, Project, ProjectCreate, Upload, Job, JobRef, StageOutputs }
