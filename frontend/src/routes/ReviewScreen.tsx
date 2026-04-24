import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'

import { AppBar } from '@/components/layout/AppBar'
import { Footer } from '@/components/layout/Footer'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button, buttonVariants } from '@/components/ui/button'
import { JobProgressCard } from '@/components/prepare/JobProgressCard'
import { SegmentReviewRow } from '@/components/review/SegmentReviewRow'
import {
  downloadUrl,
  getJob,
  getProjectOrder,
  listSegments,
  listStageOutputs,
  listVideos,
  reviewSegment,
  startStitch,
  type Verdict,
} from '@/api/client'

export default function ReviewScreen() {
  const { projectId = '' } = useParams()

  const outputsQuery = useQuery({
    queryKey: ['outputs', projectId, 'kling_test'],
    queryFn: () => listStageOutputs(projectId, 'kling_test'),
    enabled: !!projectId,
  })
  const savedOrderQuery = useQuery({
    queryKey: ['order', projectId],
    queryFn: () => getProjectOrder(projectId),
    enabled: !!projectId,
  })
  const videosQuery = useQuery({
    queryKey: ['videos', projectId],
    queryFn: () => listVideos(projectId),
    enabled: !!projectId,
  })
  const segmentsQuery = useQuery({
    queryKey: ['segments', projectId],
    queryFn: () => listSegments(projectId),
    enabled: !!projectId,
  })

  const orderedNames: string[] = useMemo(() => {
    const names = outputsQuery.data?.outputs
    if (!names) return []
    const saved = savedOrderQuery.data
    if (saved && saved.length === names.length && saved.every((n) => names.includes(n))) {
      return saved
    }
    return names
  }, [outputsQuery.data, savedOrderQuery.data])

  // Local verdict state — seeded from the server once, then updated
  // only on successful reviewSegment mutations. Failed POSTs leave
  // the local state untouched so the UI never shows a verdict the
  // server hasn't recorded.
  const [localVerdicts, setLocalVerdicts] = useState<Record<string, Verdict>>({})
  const [verdictsSeeded, setVerdictsSeeded] = useState(false)
  if (!verdictsSeeded && segmentsQuery.data) {
    const seed: Record<string, Verdict> = {}
    for (const s of segmentsQuery.data) seed[s.seg_id] = s.verdict
    setLocalVerdicts(seed)
    setVerdictsSeeded(true)
  }

  const verdictMutation = useMutation({
    mutationFn: ({ segId, verdict }: { segId: string; verdict: Verdict }) =>
      reviewSegment(projectId, segId, verdict),
    onSuccess: (seg) => {
      setLocalVerdicts((prev) => ({ ...prev, [seg.seg_id]: seg.verdict }))
    },
  })

  const [stitchJobId, setStitchJobId] = useState<string | null>(null)
  const stitchMutation = useMutation({
    mutationFn: () => startStitch(projectId, 'mock'),
    onSuccess: (ref) => setStitchJobId(ref.job_id),
  })
  const stitchJobQuery = useQuery({
    queryKey: ['job', projectId, 'stitch', stitchJobId],
    queryFn: () => getJob(projectId, stitchJobId!),
    enabled: !!stitchJobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'done' || s === 'error' ? false : 500
    },
    refetchIntervalInBackground: true,
  })

  const stitchStatus: 'idle' | 'running' | 'done' | 'error' = stitchMutation.isError
    ? 'error'
    : stitchJobId
      ? (stitchJobQuery.data?.status ?? 'running') === 'done'
        ? 'done'
        : (stitchJobQuery.data?.status ?? 'running') === 'error'
          ? 'error'
          : 'running'
      : 'idle'

  const pairs = useMemo(() => {
    const vids = videosQuery.data ?? []
    const vidByPair = new Map(vids.map((v) => [v.pair_key, v]))
    const out: Array<{ pairKey: string; segId: string; a: string; b: string; videoName: string }> = []
    for (let i = 0; i < orderedNames.length - 1; i++) {
      const a = orderedNames[i]
      const b = orderedNames[i + 1]
      const pairKey = `${a.replace(/\.[^.]+$/, '')}_to_${b.replace(/\.[^.]+$/, '')}`
      const vid = vidByPair.get(pairKey)
      if (!vid) continue
      out.push({ pairKey, segId: `seg_${pairKey}`, a, b, videoName: vid.name })
    }
    return out
  }, [orderedNames, videosQuery.data])

  const videosLoading = videosQuery.isPending || !orderedNames.length

  return (
    <>
      <AppBar currentStep="review" />
      <PageContainer
        title="Review your clips and export"
        subtitle="Watch each segment, mark it, and then stitch the full movie."
      >
        {videosLoading ? (
          <JobProgressCard
            status="running"
            headline="Loading your clips…"
            subheadline=""
          />
        ) : (
          <div className="space-y-6">
            {pairs.map(({ pairKey, segId, a, b, videoName }) => (
              <SegmentReviewRow
                key={segId}
                projectId={projectId}
                pairKey={pairKey}
                frameA={a}
                frameB={b}
                videoName={videoName}
                verdict={localVerdicts[segId] ?? null}
                onVerdict={(v) => verdictMutation.mutate({ segId, verdict: v })}
              />
            ))}

            <div className="mx-auto max-w-md pt-4">
              {stitchStatus === 'running' ? (
                <JobProgressCard
                  status="running"
                  headline="Stitching your full movie…"
                  subheadline="Usually a few seconds in mock mode."
                />
              ) : stitchStatus === 'error' ? (
                <JobProgressCard
                  status="error"
                  headline="Stitching failed"
                  subheadline="Check the backend, then try again."
                  errorText={stitchJobQuery.data?.error ?? stitchMutation.error?.message}
                  onRetry={() => {
                    setStitchJobId(null)
                    stitchMutation.reset()
                    stitchMutation.mutate()
                  }}
                />
              ) : stitchStatus === 'done' ? (
                <a
                  href={downloadUrl(projectId)}
                  download
                  className={buttonVariants({ variant: 'default', size: 'lg' })}
                >
                  Download full movie
                </a>
              ) : (
                <Button
                  size="lg"
                  disabled={pairs.length === 0}
                  onClick={() => stitchMutation.mutate()}
                >
                  Stitch & Export
                </Button>
              )}
            </div>
          </div>
        )}
      </PageContainer>

      <Footer right={null} />
    </>
  )
}
