import type { ReactNode } from 'react'

export function PageContainer({
  title,
  subtitle,
  children,
}: {
  title?: string
  subtitle?: string
  children: ReactNode
}) {
  return (
    <main className="mx-auto w-full max-w-[960px] px-6 py-8 pb-28">
      {(title || subtitle) && (
        <header className="mb-8 space-y-1">
          {title && <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>}
          {subtitle && <p className="text-muted-foreground">{subtitle}</p>}
        </header>
      )}
      {children}
    </main>
  )
}
