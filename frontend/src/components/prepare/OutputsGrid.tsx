import { artifactUrl } from '@/api/client'

interface OutputsGridProps {
  projectId: string
  stage: string
  names: string[]
  /** Accessible label prefix for each img alt; e.g. "prepared photo" */
  altPrefix?: string
}

export function OutputsGrid({
  projectId,
  stage,
  names,
  altPrefix = 'photo',
}: OutputsGridProps) {
  if (names.length === 0) {
    return (
      <p className="mt-6 text-center text-sm text-muted-foreground">
        No outputs yet
      </p>
    )
  }
  return (
    <>
      <p className="mb-4 text-sm text-muted-foreground">
        Prepared {names.length} photo{names.length === 1 ? '' : 's'}
      </p>
      <ul className="grid grid-cols-3 gap-4 md:grid-cols-4 lg:grid-cols-5">
        {names.map((name, idx) => (
          <li
            key={name}
            className="aspect-[4/3] overflow-hidden rounded-xl border border-border bg-muted"
          >
            <img
              src={artifactUrl(projectId, stage, name)}
              alt={`${altPrefix} ${idx + 1}`}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          </li>
        ))}
      </ul>
    </>
  )
}
