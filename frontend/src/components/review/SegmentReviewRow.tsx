import { artifactUrl, videoUrl } from '@/api/client'
import type { Verdict } from '@/api/client'
import { Button } from '@/components/ui/button'
import { VideoLightbox } from '@/components/generate/VideoLightbox'

interface SegmentReviewRowProps {
  projectId: string
  pairKey: string
  frameA: string
  frameB: string
  videoName: string
  verdict: Verdict | null
  onVerdict: (v: Verdict) => void
}

const VERDICTS: Verdict[] = ['winner', 'redo', 'bad']

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export function SegmentReviewRow({
  projectId,
  pairKey,
  frameA,
  frameB,
  videoName,
  verdict,
  onVerdict,
}: SegmentReviewRowProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-center gap-3">
        <img
          src={artifactUrl(projectId, 'kling_test', frameA)}
          alt={`Frame ${frameA}`}
          className="h-14 w-24 rounded-md border border-border object-cover"
          loading="lazy"
        />
        <span aria-hidden className="text-muted-foreground">→</span>
        <img
          src={artifactUrl(projectId, 'kling_test', frameB)}
          alt={`Frame ${frameB}`}
          className="h-14 w-24 rounded-md border border-border object-cover"
          loading="lazy"
        />
        <code className="ml-3 text-xs text-muted-foreground">{pairKey}</code>
        <div className="ml-auto">
          <VideoLightbox
            src={videoUrl(projectId, videoName)}
            pairKey={pairKey}
          />
        </div>
      </div>
      <div className="flex gap-2">
        {VERDICTS.map((v) => {
          const selected = verdict === v
          return (
            <Button
              key={v}
              variant={selected ? 'default' : 'outline'}
              size="sm"
              aria-pressed={selected}
              aria-label={`Mark ${pairKey} as ${v}`}
              onClick={() => onVerdict(v)}
            >
              {capitalize(v)}
            </Button>
          )
        })}
      </div>
    </div>
  )
}
