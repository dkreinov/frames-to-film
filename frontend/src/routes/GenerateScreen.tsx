import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'

import { AppBar } from '@/components/layout/AppBar'
import { Footer } from '@/components/layout/Footer'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { JobProgressCard } from '@/components/prepare/JobProgressCard'
import { PromptRow } from '@/components/generate/PromptRow'
import { VideoLightbox } from '@/components/generate/VideoLightbox'
import {
  getJob,
  getPrompts,
  getProjectOrder,
  listStageOutputs,
  listVideos,
  savePrompts,
  startGenerate,
  startPromptsGeneration,
  videoUrl,
  type PromptsMap,
  type VideoItem,
} from '@/api/client'
import { useDebouncedSave } from './useDebouncedSave'
import { useSettings } from './useSettings'

function pairKeysFromOrder(ordered: string[]): string[] {
  const stems = ordered.map((n) => n.replace(/\.[^.]+$/, ''))
  const out: string[] = []
  for (let i = 0; i < stems.length - 1; i++) out.push(`${stems[i]}_to_${stems[i + 1]}`)
  return out
}

export default function GenerateScreen() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const { modes } = useSettings()

  // --- Expected pair sequence (from /outputs + /order) ---
  const outputsQuery = useQuery({
    queryKey: ['outputs', projectId, 'extended'],
    queryFn: () => listStageOutputs(projectId, 'extended'),
    enabled: !!projectId,
  })
  const savedOrderQuery = useQuery({
    queryKey: ['order', projectId],
    queryFn: () => getProjectOrder(projectId),
    enabled: !!projectId,
  })

  const orderedNames: string[] | null = useMemo(() => {
    const names = outputsQuery.data?.outputs
    if (!names) return null
    const saved = savedOrderQuery.data
    if (saved && saved.length === names.length && saved.every((n) => names.includes(n))) {
      return saved
    }
    return names
  }, [outputsQuery.data, savedOrderQuery.data])

  const expectedPairKeys: string[] = useMemo(
    () => (orderedNames ? pairKeysFromOrder(orderedNames) : []),
    [orderedNames]
  )

  // --- Prompts: GET, optionally regenerate once if missing/stale ---
  const promptsQuery = useQuery({
    queryKey: ['prompts', projectId],
    queryFn: () => getPrompts(projectId),
    enabled: !!projectId,
  })

  const [promptsJobId, setPromptsJobId] = useState<string | null>(null)
  const promptsJobQuery = useQuery({
    queryKey: ['job', projectId, 'prompts', promptsJobId],
    queryFn: () => getJob(projectId, promptsJobId!),
    enabled: !!promptsJobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'done' || s === 'error' ? false : 500
    },
    refetchIntervalInBackground: true,
  })
  const promptsGenMutation = useMutation({
    mutationFn: () => startPromptsGeneration(projectId, modes.generatePrompts, 'cinematic'),
    onSuccess: (ref) => setPromptsJobId(ref.job_id),
  })

  const regenAttempted = useRef(false)
  useEffect(() => {
    if (!orderedNames || promptsQuery.isPending) return
    const have = new Set(Object.keys(promptsQuery.data ?? {}))
    const want = new Set(expectedPairKeys)
    const mismatch =
      promptsQuery.data === null ||
      have.size !== want.size ||
      [...want].some((k) => !have.has(k))
    if (mismatch && !regenAttempted.current && !promptsGenMutation.isPending && !promptsJobId) {
      regenAttempted.current = true
      promptsGenMutation.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderedNames, promptsQuery.data, promptsQuery.isPending, expectedPairKeys])

  // Re-fetch prompts once the prompts job finishes.
  useEffect(() => {
    if (promptsJobQuery.data?.status === 'done') {
      promptsQuery.refetch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promptsJobQuery.data?.status])

  // --- Local editable prompts + debounced PUT ---
  const [prompts, setPrompts] = useState<PromptsMap | null>(null)
  useEffect(() => {
    if (prompts !== null) return
    const server = promptsQuery.data
    if (!server || expectedPairKeys.length === 0) return
    const have = new Set(Object.keys(server))
    if (!expectedPairKeys.every((k) => have.has(k))) return
    setPrompts(server)
  }, [promptsQuery.data, expectedPairKeys, prompts])

  const saveCallback = useCallback(
    (m: PromptsMap) => savePrompts(projectId, m),
    [projectId]
  )
  const { isPending: isSaving } = useDebouncedSave(prompts, 300, saveCallback)

  // --- Generate job ---
  const [generateJobId, setGenerateJobId] = useState<string | null>(null)
  const generateMutation = useMutation({
    mutationFn: () => startGenerate(projectId, modes.generateVideos),
    onSuccess: (ref) => setGenerateJobId(ref.job_id),
  })
  const generateJobQuery = useQuery({
    queryKey: ['job', projectId, 'generate', generateJobId],
    queryFn: () => getJob(projectId, generateJobId!),
    enabled: !!generateJobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'done' || s === 'error' ? false : 500
    },
    refetchIntervalInBackground: true,
  })

  const generateStatus: 'idle' | 'running' | 'done' | 'error' = generateMutation.isError
    ? 'error'
    : generateJobId
      ? (generateJobQuery.data?.status ?? 'running') === 'done'
        ? 'done'
        : (generateJobQuery.data?.status ?? 'running') === 'error'
          ? 'error'
          : 'running'
      : 'idle'

  const videosQuery = useQuery({
    queryKey: ['videos', projectId],
    queryFn: () => listVideos(projectId),
    enabled: generateStatus === 'done',
  })
  const videos: VideoItem[] = videosQuery.data ?? []
  const videoByPair = useMemo(() => {
    const m = new Map<string, VideoItem>()
    videos.forEach((v) => m.set(v.pair_key, v))
    return m
  }, [videos])

  // --- Prompts-regen failure handling ---
  const regenFailed =
    regenAttempted.current &&
    promptsJobQuery.data?.status === 'done' &&
    promptsQuery.data !== null &&
    expectedPairKeys.length > 0 &&
    !expectedPairKeys.every((k) => Object.keys(promptsQuery.data ?? {}).includes(k))

  const promptsLoading =
    !regenFailed &&
    (promptsQuery.isPending ||
      !orderedNames ||
      prompts === null) &&
    generateStatus !== 'running'

  // --- Render ---
  const pairs = useMemo(() => {
    if (!orderedNames) return []
    const out: Array<{ pairKey: string; a: string; b: string }> = []
    for (let i = 0; i < orderedNames.length - 1; i++) {
      const a = orderedNames[i]
      const b = orderedNames[i + 1]
      out.push({
        pairKey: `${a.replace(/\.[^.]+$/, '')}_to_${b.replace(/\.[^.]+$/, '')}`,
        a,
        b,
      })
    }
    return out
  }, [orderedNames])

  return (
    <>
      <AppBar currentStep="generate" />
      <PageContainer
        title="Write prompts and render"
        subtitle="Each clip is a 1-second transition between two frames. Edit the prompts, then hit Generate videos."
      >
        {prompts ? (
          <p
            role="status"
            aria-live="polite"
            className="mb-3 text-sm text-muted-foreground"
          >
            {isSaving ? 'Saving…' : 'Saved'}
          </p>
        ) : null}

        {generateStatus === 'running' ? (
          <JobProgressCard
            status="running"
            headline="Rendering your 1-second clips…"
            subheadline="Usually under a minute in mock mode."
          />
        ) : generateStatus === 'error' ? (
          <JobProgressCard
            status="error"
            headline="Rendering failed"
            subheadline=""
            errorText={generateJobQuery.data?.error ?? generateMutation.error?.message}
            onRetry={() => {
              setGenerateJobId(null)
              generateMutation.reset()
              generateMutation.mutate()
            }}
          />
        ) : regenFailed ? (
          <JobProgressCard
            status="error"
            headline="Couldn't write prompts"
            subheadline="Check the backend is running, then try again."
            onRetry={() => window.location.reload()}
          />
        ) : promptsLoading ? (
          <JobProgressCard
            status="running"
            headline="Writing starter prompts…"
            subheadline="A one-time setup before your first render."
          />
        ) : prompts ? (
          <div className="space-y-6">
            {pairs.map(({ pairKey, a, b }) => {
              const video = videoByPair.get(pairKey)
              return (
                <PromptRow
                  key={pairKey}
                  projectId={projectId}
                  pairKey={pairKey}
                  frameA={a}
                  frameB={b}
                  value={prompts[pairKey] ?? ''}
                  onChange={(next) =>
                    setPrompts({ ...(prompts ?? {}), [pairKey]: next })
                  }
                  poster={
                    video ? (
                      <VideoLightbox
                        src={videoUrl(projectId, video.name)}
                        pairKey={pairKey}
                      />
                    ) : undefined
                  }
                />
              )
            })}
          </div>
        ) : null}
      </PageContainer>

      <Footer
        right={
          generateStatus === 'done' ? (
            <Button
              size="lg"
              onClick={() => navigate(`/projects/${projectId}/review`)}
            >
              Next: Review
            </Button>
          ) : (
            <Button
              size="lg"
              disabled={!prompts || generateStatus === 'running'}
              onClick={() => generateMutation.mutate()}
            >
              Generate videos
            </Button>
          )
        }
      />
    </>
  )
}
