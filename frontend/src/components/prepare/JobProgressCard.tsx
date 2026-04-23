import { Loader2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

interface JobProgressCardProps {
  status: 'pending' | 'running' | 'done' | 'error'
  headline: string
  subheadline: string
  errorText?: string | null
  onRetry?: () => void
}

export function JobProgressCard({
  status,
  headline,
  subheadline,
  errorText,
  onRetry,
}: JobProgressCardProps) {
  if (status === 'error') {
    return (
      <Card
        className="mx-auto max-w-md p-8 text-center"
        role="alert"
      >
        <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-destructive" aria-hidden />
        <h2 className="text-lg font-semibold">Preparation failed</h2>
        {errorText && (
          <p className="mt-2 text-sm text-muted-foreground">{errorText}</p>
        )}
        {onRetry && (
          <Button variant="outline" className="mt-4" onClick={onRetry}>
            Try again
          </Button>
        )}
      </Card>
    )
  }

  return (
    <Card
      className="mx-auto max-w-md p-8 text-center"
      role="status"
      aria-live="polite"
    >
      <Loader2
        className="mx-auto mb-3 h-6 w-6 animate-spin text-muted-foreground"
        aria-hidden
      />
      <h2 className="text-lg font-semibold">{headline}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{subheadline}</p>
    </Card>
  )
}
