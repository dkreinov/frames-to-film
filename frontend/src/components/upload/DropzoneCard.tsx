import { useCallback, useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import { CloudUpload } from 'lucide-react'
import { cn } from '@/lib/utils'

interface DropzoneCardProps {
  onFilesPicked: (files: File[]) => void
}

const ACCEPTED = ['image/png', 'image/jpeg', 'image/webp']

export function DropzoneCard({ onFilesPicked }: DropzoneCardProps) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(
    (list: FileList | File[]) => {
      const incoming = Array.from(list).filter((f) => ACCEPTED.includes(f.type))
      if (incoming.length > 0) onFilesPicked(incoming)
    },
    [onFilesPicked]
  )

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files)
  }

  const openPicker = () => inputRef.current?.click()

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openPicker()
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Drag photos here or click to browse"
      onClick={openPicker}
      onKeyDown={onKey}
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={onDrop}
      className={cn(
        'flex h-80 flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border/80 bg-card/40 text-center transition-colors cursor-pointer',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        isDragging && 'border-primary bg-primary/5'
      )}
    >
      <CloudUpload className="mb-4 h-10 w-10 text-muted-foreground" aria-hidden />
      <p className="text-lg font-medium">Drag photos here or click to browse</p>
      <p className="mt-2 text-sm text-muted-foreground">
        We&apos;ll preserve every face exactly. JPG, PNG, or WebP.
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(',')}
        multiple
        className="hidden"
        onChange={(e) => e.target.files && handleFiles(e.target.files)}
      />
    </div>
  )
}
