import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

export const WIZARD_STEPS = [
  { id: 'upload', label: 'Upload' },
  { id: 'prepare', label: 'Prepare' },
  { id: 'storyboard', label: 'Storyboard' },
  { id: 'generate', label: 'Generate' },
  { id: 'review', label: 'Review' },
] as const

export type WizardStep = (typeof WIZARD_STEPS)[number]['id']

export function WizardStepper({ currentStep }: { currentStep?: WizardStep }) {
  const currentIdx = currentStep
    ? WIZARD_STEPS.findIndex((s) => s.id === currentStep)
    : -1
  return (
    <ol className="flex items-center gap-2 text-xs">
      {WIZARD_STEPS.map((step, idx) => {
        const done = idx < currentIdx
        const active = idx === currentIdx
        return (
          <li
            key={step.id}
            aria-current={active ? 'step' : undefined}
            className="flex items-center gap-2"
          >
            <span
              className={cn(
                'grid h-5 w-5 place-items-center rounded-full text-[10px]',
                done && 'bg-primary text-primary-foreground',
                active && 'bg-primary/10 text-primary ring-2 ring-primary/40',
                !done && !active && 'bg-muted text-muted-foreground'
              )}
            >
              {done ? <Check className="h-3 w-3" /> : idx + 1}
            </span>
            <span
              className={cn(
                'hidden sm:inline',
                active ? 'font-medium text-foreground' : 'text-muted-foreground'
              )}
            >
              {step.label}
            </span>
            {idx < WIZARD_STEPS.length - 1 && (
              <span className="mx-1 h-px w-4 bg-border" aria-hidden />
            )}
          </li>
        )
      })}
    </ol>
  )
}
