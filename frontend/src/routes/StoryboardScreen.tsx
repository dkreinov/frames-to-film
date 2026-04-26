import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AppBar } from '@/components/layout/AppBar'
import { Footer } from '@/components/layout/Footer'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { JobProgressCard } from '@/components/prepare/JobProgressCard'
import { SortableGrid } from '@/components/storyboard/SortableGrid'
import {
  getJob,
  getProjectOrder,
  listStageOutputs,
  saveProjectOrder,
  startExtend,
} from '@/api/client'
import { useDebouncedSave } from './useDebouncedSave'
import { useSettings } from './useSettings'

export default function StoryboardScreen() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const [jobId, setJobId] = useState<string | null>(null)
  const [order, setOrder] = useState<string[] | null>(null)
  const { modes } = useSettings()

  // Auto-start extend on mount.
  const startMutation = useMutation({
    mutationFn: () => startExtend(projectId, modes.extend),
    onSuccess: (jobRef) => setJobId(jobRef.job_id),
  })

  useEffect(() => {
    if (projectId && !jobId && !startMutation.isPending) {
      startMutation.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  const jobQuery = useQuery({
    queryKey: ['job', projectId, jobId],
    queryFn: () => getJob(projectId, jobId!),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'done' || s === 'error' ? false : 2000
    },
    refetchIntervalInBackground: true,
  })

  const status: 'pending' | 'running' | 'done' | 'error' =
    startMutation.isError ? 'error' : (jobQuery.data?.status ?? 'pending')

  const outputsQuery = useQuery({
    queryKey: ['outputs', projectId, 'extended'],
    queryFn: () => listStageOutputs(projectId, 'extended'),
    enabled: status === 'done',
  })

  const savedOrderQuery = useQuery({
    queryKey: ['order', projectId],
    queryFn: () => getProjectOrder(projectId),
    enabled: status === 'done',
  })

  // Initialise local order from server (saved order if compatible, else
  // the natural order from /outputs).
  useEffect(() => {
    if (order !== null) return
    const names = outputsQuery.data?.outputs
    if (!names) return
    const saved = savedOrderQuery.data
    if (saved && saved.length === names.length && saved.every((n) => names.includes(n))) {
      setOrder(saved)
    } else {
      setOrder(names)
    }
  }, [outputsQuery.data, savedOrderQuery.data, order])

  const saveCallback = useCallback(
    (next: string[]) => saveProjectOrder(projectId, next),
    [projectId]
  )

  const { isPending: isSaving } = useDebouncedSave(order, 300, saveCallback)

  const retry = () => {
    setJobId(null)
    setOrder(null)
    startMutation.reset()
    startMutation.mutate()
  }

  return (
    <>
      <AppBar currentStep="storyboard" />
      <PageContainer
        title="Arrange your story"
        subtitle="Drag the frames into the order you want them to play."
      >
        {status === 'done' && order ? (
          <>
            <p
              role="status"
              aria-live="polite"
              className="mb-3 text-sm text-muted-foreground"
            >
              {isSaving ? 'Saving…' : 'Order saved'}
            </p>
            <SortableGrid
              projectId={projectId}
              stage="extended"
              names={order}
              onChange={setOrder}
            />
          </>
        ) : (
          <JobProgressCard
            status={status}
            headline={status === 'error' ? 'Building 16:9 frames failed' : 'Building 16:9 frames…'}
            subheadline="Extending each photo to widescreen so the story frames fit together."
            errorText={jobQuery.data?.error ?? startMutation.error?.message}
            onRetry={status === 'error' ? retry : undefined}
          />
        )}
      </PageContainer>

      <Footer
        right={
          <Button
            size="lg"
            disabled={status !== 'done' || !order}
            onClick={() => navigate(`/projects/${projectId}/generate`)}
          >
            Next: Generate
          </Button>
        }
      />
    </>
  )
}
