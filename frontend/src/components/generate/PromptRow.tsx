import { artifactUrl } from '@/api/client'

interface PromptRowProps {
  projectId: string
  pairKey: string
  frameA: string
  frameB: string
  value: string
  onChange: (next: string) => void
  poster?: React.ReactNode
}

export function PromptRow({
  projectId,
  pairKey,
  frameA,
  frameB,
  value,
  onChange,
  poster,
}: PromptRowProps) {
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
        {poster ? <div className="ml-auto">{poster}</div> : null}
      </div>
      <textarea
        aria-label={`Prompt for pair ${pairKey}`}
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      />
    </div>
  )
}
