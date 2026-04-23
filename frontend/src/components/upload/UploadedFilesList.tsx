import { X, ImageIcon } from 'lucide-react'
import { useEffect, useMemo } from 'react'
import { Button } from '@/components/ui/button'

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

interface UploadedFilesListProps {
  files: File[]
  onRemove: (index: number) => void
}

export function UploadedFilesList({ files, onRemove }: UploadedFilesListProps) {
  const previews = useMemo(
    () => files.map((f) => ({ file: f, url: URL.createObjectURL(f) })),
    [files]
  )

  useEffect(() => {
    return () => previews.forEach((p) => URL.revokeObjectURL(p.url))
  }, [previews])

  if (files.length === 0) {
    return (
      <p className="mt-6 text-center text-sm text-muted-foreground">No photos yet</p>
    )
  }

  return (
    <ul className="mt-6 divide-y divide-border rounded-xl border border-border">
      {previews.map(({ file, url }, idx) => (
        <li key={`${file.name}-${idx}`} className="flex items-center gap-4 p-3">
          <div className="grid h-12 w-12 place-items-center overflow-hidden rounded-md bg-muted">
            {url ? (
              <img src={url} alt="" className="h-full w-full object-cover" />
            ) : (
              <ImageIcon className="h-5 w-5 text-muted-foreground" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium">{file.name}</p>
            <p className="text-xs text-muted-foreground">{humanSize(file.size)}</p>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Remove ${file.name}`}
            onClick={() => onRemove(idx)}
          >
            <X className="h-4 w-4" />
          </Button>
        </li>
      ))}
    </ul>
  )
}
