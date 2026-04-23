import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createProject, uploadFile } from '@/api/client'

/**
 * Kicks off project creation + N uploads + navigation to /:id/prepare.
 * Isolated so Step 4 tests can mock the whole flow.
 */
export function useUploadFlow() {
  const navigate = useNavigate()
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function runUpload(projectName: string, files: File[]) {
    setIsRunning(true)
    setError(null)
    try {
      const project = await createProject({ name: projectName })
      for (const f of files) {
        await uploadFile(project.project_id, f)
      }
      navigate(`/projects/${project.project_id}/prepare`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsRunning(false)
    }
  }

  return { runUpload, isRunning, error }
}
