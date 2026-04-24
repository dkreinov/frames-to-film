import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AppBar } from '@/components/layout/AppBar'
import { Footer } from '@/components/layout/Footer'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { JobProgressCard } from '@/components/prepare/JobProgressCard'
import { OutputsGrid } from '@/components/prepare/OutputsGrid'
import { getJob, listStageOutputs, startPrepare } from '@/api/client'

export default function PrepareScreen() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const [jobId, setJobId] = useState<string | null>(null)

  // Kick off the prepare job on mount (or on retry).
  const startMutation = useMutation({
    mutationFn: () => startPrepare(projectId, 'mock'),
    onSuccess: (jobRef) => setJobId(jobRef.job_id),
  })

  useEffect(() => {
    if (projectId && !jobId && !startMutation.isPending) {
      startMutation.mutate()
    }
    // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  // Poll job status every 2s until it settles.
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

  // Once done, list the outputs.
  const outputsQuery = useQuery({
    queryKey: ['outputs', projectId, 'outpainted'],
    queryFn: () => listStageOutputs(projectId, 'outpainted'),
    enabled: jobQuery.data?.status === 'done',
  })

  const status: 'pending' | 'running' | 'done' | 'error' =
    startMutation.isError ? 'error' : (jobQuery.data?.status ?? 'pending')
  const names = outputsQuery.data?.outputs ?? []

  const retry = () => {
    setJobId(null)
    startMutation.reset()
    startMutation.mutate()
  }

  return (
    <>
      <AppBar currentStep="prepare" />
      <PageContainer
        title="Prepare photos"
        subtitle="Normalizing each photo to 4:3 landscape so the story frames fit together."
      >
        {status === 'done' ? (
          <OutputsGrid
            projectId={projectId}
            stage="outpainted"
            names={names}
            altPrefix="prepared photo"
          />
        ) : (
          <JobProgressCard
            status={status}
            headline={status === 'error' ? 'Preparation failed' : 'Preparing photos…'}
            subheadline="Normalizing to 4:3 landscape. This usually takes a minute for 10 photos."
            errorText={jobQuery.data?.error ?? startMutation.error?.message}
            onRetry={status === 'error' ? retry : undefined}
          />
        )}
      </PageContainer>

      <Footer
        right={
          <Button
            size="lg"
            disabled={status !== 'done'}
            onClick={() => navigate(`/projects/${projectId}/storyboard`)}
          >
            Next: Storyboard
          </Button>
        }
      />
    </>
  )
}
