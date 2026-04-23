import { useState } from 'react'
import { Play } from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

interface VideoLightboxProps {
  src: string
  pairKey: string
}

export function VideoLightbox({ src, pairKey }: VideoLightboxProps) {
  const [open, setOpen] = useState(false)
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          aria-label={`Play ${pairKey}`}
          className="flex h-14 w-24 items-center justify-center rounded-md border border-border bg-muted text-foreground transition hover:bg-muted/80 focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <Play className="size-5" />
        </button>
      </DialogTrigger>
      <DialogContent aria-describedby={undefined}>
        <DialogTitle>Pair {pairKey}</DialogTitle>
        {open ? (
          <video
            src={src}
            controls
            autoPlay
            playsInline
            className="mt-3 w-full rounded-md"
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
