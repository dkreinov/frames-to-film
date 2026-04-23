import { useQuery } from '@tanstack/react-query'
import { getHealth } from '@/api/client'

export function BackendStatus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15_000,
    retry: false,
  })

  const colour = isError
    ? 'bg-red-500'
    : isLoading
      ? 'bg-zinc-400'
      : data?.status === 'ok'
        ? 'bg-emerald-500'
        : 'bg-amber-500'

  const label = isError
    ? 'backend offline'
    : isLoading
      ? 'connecting...'
      : `backend ${data?.status ?? 'unknown'}`

  return (
    <div
      className="fixed bottom-3 right-3 flex items-center gap-2 rounded-full border border-border/50 bg-card/80 px-3 py-1 text-xs backdrop-blur"
      role="status"
    >
      <span className={`h-2 w-2 rounded-full ${colour}`} aria-hidden />
      <span className="text-muted-foreground">{label}</span>
    </div>
  )
}
