import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
} from '@dnd-kit/sortable'
import { SortableThumbnail } from './SortableThumbnail'

interface SortableGridProps {
  projectId: string
  stage: string
  names: string[]
  onChange: (newNames: string[]) => void
}

export function SortableGrid({ projectId, stage, names, onChange }: SortableGridProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  const handleDragEnd = (e: DragEndEvent) => {
    if (!e.over || e.active.id === e.over.id) return
    const oldIdx = names.indexOf(String(e.active.id))
    const newIdx = names.indexOf(String(e.over.id))
    if (oldIdx === -1 || newIdx === -1) return
    onChange(arrayMove(names, oldIdx, newIdx))
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={names} strategy={rectSortingStrategy}>
        <ul className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {names.map((name, idx) => (
            <SortableThumbnail
              key={name}
              projectId={projectId}
              stage={stage}
              name={name}
              index={idx}
            />
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  )
}
