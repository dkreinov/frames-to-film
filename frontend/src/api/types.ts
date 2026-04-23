// Mirrors the FastAPI response schemas. Keep in sync with
// backend/routers/*.py + backend/services/*.py.

export interface Health {
  status: string
}

export interface Project {
  project_id: string
  user_id: string
  name: string
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
}

export interface Upload {
  upload_id: string
  filename: string
  size_bytes: number
  created_at: string
}

export interface JobRef {
  job_id: string
}

export interface Job {
  job_id: string
  project_id: string
  user_id: string
  kind: string
  status: 'pending' | 'running' | 'done' | 'error'
  payload: Record<string, unknown>
  error: string | null
  created_at: string
  updated_at: string
}

export interface StageOutputs {
  stage: string
  outputs: string[]
}

export type StylePreset = 'cinematic' | 'nostalgic' | 'vintage' | 'playful'

export type PromptsMap = Record<string, string>

export interface VideoItem {
  name: string
  pair_key: string
}
