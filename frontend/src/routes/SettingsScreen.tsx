import { useEffect, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

import { AppBar } from '@/components/layout/AppBar'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { useSettings, type StageKey, type Mode } from './useSettings'

const STAGE_ROWS: Array<{
  id: StageKey
  label: string
  apiEnabled: boolean
}> = [
  { id: 'prepare', label: 'Prepare', apiEnabled: false },
  { id: 'extend', label: 'Storyboard extend', apiEnabled: false },
  { id: 'generatePrompts', label: 'Generate prompts', apiEnabled: true },
  { id: 'generateVideos', label: 'Generate videos', apiEnabled: true },
  { id: 'stitch', label: 'Stitch', apiEnabled: false },
]

const API_NOTE = 'api mode arrives in Phase 5'

interface KeyFieldProps {
  id: string
  label: string
  placeholder: string
  helpText: string
  value: string
  onSave: (next: string) => void
  onClear: () => void
}

function KeyField({
  id,
  label,
  placeholder,
  helpText,
  value,
  onSave,
  onClear,
}: KeyFieldProps) {
  const [draft, setDraft] = useState(value)
  const [show, setShow] = useState(false)

  useEffect(() => {
    setDraft(value)
  }, [value])

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          type={show ? 'text' : 'password'}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="w-96 rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          placeholder={placeholder}
        />
        <Button
          variant="outline"
          size="sm"
          aria-label={show ? `Hide ${id} value` : `Show ${id} value`}
          onClick={() => setShow((v) => !v)}
        >
          {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </Button>
        <Button variant="default" size="sm" onClick={() => onSave(draft.trim())}>
          Save
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setDraft('')
            onClear()
          }}
        >
          Clear
        </Button>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{helpText}</p>
    </div>
  )
}

export default function SettingsScreen() {
  const { keys, modes, setKey, clearKey, setMode } = useSettings()

  return (
    <>
      <AppBar />
      <PageContainer
        title="Settings"
        subtitle="API keys are stored in this browser only. Run modes control whether each stage uses real APIs or mock data."
      >
        <section className="mb-10">
          <h2 className="mb-3 text-lg font-semibold">API keys</h2>
          <div className="space-y-4">
            <KeyField
              id="gemini-key"
              label="Gemini API key"
              placeholder="sk-..."
              helpText="Used for api-mode prompts generation. Stored in this browser's localStorage and sent as X-Gemini-Key on every backend request."
              value={keys.gemini}
              onSave={(v) => setKey('gemini', v)}
              onClear={() => clearKey('gemini')}
            />
            <KeyField
              id="fal-key"
              label="fal.ai API key"
              placeholder="fal-..."
              helpText="Used for api-mode video generation (Kling O3 on fal.ai, 5-second clips, audio off, ~$0.42 per clip). Stored in this browser's localStorage and sent as X-Fal-Key on every backend request."
              value={keys.fal}
              onSave={(v) => setKey('fal', v)}
              onClear={() => clearKey('fal')}
            />
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-semibold">Run modes</h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Each stage can run in mock (free, fast, preset output) or
            api (real external calls, requires keys above). Only stages
            with implemented api paths can be toggled today.
          </p>
          <table className="text-sm">
            <thead>
              <tr className="text-left">
                <th className="pr-6 pb-2 font-medium text-muted-foreground">
                  Stage
                </th>
                <th className="px-4 pb-2 font-medium text-muted-foreground">
                  mock
                </th>
                <th className="px-4 pb-2 font-medium text-muted-foreground">
                  api
                </th>
              </tr>
            </thead>
            <tbody>
              {STAGE_ROWS.map(({ id, label, apiEnabled }) => (
                <tr key={id}>
                  <td className="pr-6 py-2">
                    <span className="font-medium">{label}</span>
                    {!apiEnabled && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({API_NOTE})
                      </span>
                    )}
                  </td>
                  {(['mock', 'api'] as Mode[]).map((m) => (
                    <td key={m} className="px-4 py-2 text-center">
                      <input
                        type="radio"
                        name={`mode-${id}`}
                        aria-label={`${label} — ${m}`}
                        checked={modes[id] === m}
                        disabled={!apiEnabled && m === 'api'}
                        onChange={() => setMode(id, m)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </PageContainer>
    </>
  )
}
