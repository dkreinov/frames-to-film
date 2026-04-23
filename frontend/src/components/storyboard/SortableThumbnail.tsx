import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'
import { artifactUrl } from '@/api/client'
import { cn } from '@/lib/utils'

interface SortableThumbnailProps {
  projectId: string
  stage: string
  name: string
  index: number
}

export function SortableThumbnail({
  projectId,
  stage,
  name,
  index,
}: SortableThumbnailProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: name })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  }

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={cn(
        'relative aspect-video overflow-hidden rounded-xl border border-border bg-muted',
        isDragging && 'shadow-lg ring-2 ring-primary'
      )}
    >
      <img
        src={artifactUrl(projectId, stage, name)}
        alt={`Frame ${index + 1}, ${name}`}
        className="h-full w-full object-cover"
        loading="lazy"
        draggable={false}
      />
      <span className="absolute left-2 top-2 rounded-md bg-background/80 px-1.5 py-0.5 text-xs font-medium tabular-nums backdrop-blur">
        {index + 1}
      </span>
      <button
        type="button"
        aria-label={`Drag frame ${index + 1} (${name}). Press space to pick up, arrow keys to move, space to drop.`}
        className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-md bg-background/80 text-muted-foreground backdrop-blur hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-4 w-4" />
      </button>
    </li>
  )
}
