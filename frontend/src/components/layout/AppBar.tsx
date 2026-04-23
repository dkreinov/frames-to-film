import { Link } from 'react-router-dom'
import { Settings } from 'lucide-react'
import { WizardStepper, type WizardStep } from './WizardStepper'

export function AppBar({ currentStep }: { currentStep: WizardStep }) {
  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur">
      <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
        <span className="grid h-6 w-6 place-items-center rounded-md bg-primary text-primary-foreground text-xs">om</span>
        <span>olga_movie</span>
      </Link>

      <div className="flex-1 flex justify-center px-10">
        <WizardStepper currentStep={currentStep} />
      </div>

      <Link
        to="/settings"
        className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        aria-label="Settings"
      >
        <Settings className="h-4 w-4" />
      </Link>
    </header>
  )
}
