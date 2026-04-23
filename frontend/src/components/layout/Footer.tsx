import type { ReactNode } from 'react'

export function Footer({
  left,
  right,
}: {
  left?: ReactNode
  right?: ReactNode
}) {
  return (
    <footer className="fixed bottom-0 left-0 right-0 flex h-[72px] items-center justify-between border-t border-border bg-background/90 px-6 backdrop-blur">
      <div>{left}</div>
      <div>{right}</div>
    </footer>
  )
}
