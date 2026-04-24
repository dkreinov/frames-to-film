import { useEffect, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

import { AppBar } from '@/components/layout/AppBar'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { useSettings, type StageKey, type Mode } from './useSettings'

const STAGE_ROWS: Array<{ id: StageKey; label: string; enabled: boolean }> = [
  { id: 'prepare', label: 'Prepare', enabled: false },
  { id: 'extend', label: 'Storyboard extend', enabled: false },
  { id: 'generatePrompts', label: 'Generate prompts', enabled: true },
  { id: 'generateVideos', label: 'Generate videos', enabled: false },
  { id: 'stitch', label: 'Stitch', enabled: false },
]

const PHASE_5_NOTE = 'api mode arrives in Phase 5'

export default function SettingsScreen() {
  const { keys, modes, setKey, clearKey, setMode } = useSettings()
  const [draft, setDraft] = useState(keys.gemini)
  const [show, setShow] = useState(false)

  // Hydrate the draft when stored keys change (e.g., Clear or
  // cross-tab storage event).
  useEffect(() => {
    setDraft(keys.gemini)
  }, [keys.gemini])

  return (
    <>
      <AppBar />
      <PageContainer
        title="Settings"
        subtitle="API keys are stored in this browser only. Run modes control whether each stage uses real APIs or mock data."
      >
        <section className="mb-10">
          <h2 className="mb-3 text-lg font-semibold">API keys</h2>
          <div className="space-y-3">
            <div>
              <label
                htmlFor="gemini-key"
                className="mb-1 block text-sm font-medium"
              >
                Gemini API key
              </label>
              <div className="flex items-center gap-2">
                <input
                  id="gemini-key"
                  type={show ? 'text' : 'password'}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  className="w-96 rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  placeholder="sk-..."
                />
                <Button
                  variant="outline"
                  size="sm"
                  aria-label={show ? 'Hide key' : 'Show key'}
                  onClick={() => setShow((v) => !v)}
                >
                  {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </Button>
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => setKey('gemini', draft.trim())}
                >
                  Save
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setDraft('')
                    clearKey('gemini')
                  }}
                >
                  Clear
                </Button>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Used for api-mode prompts generation. Stored in this
                browser's localStorage and sent as X-Gemini-Key on
                every backend request.
              </p>
            </div>
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
              {STAGE_ROWS.map(({ id, label, enabled }) => (
                <tr key={id}>
                  <td className="pr-6 py-2">
                    <span className="font-medium">{label}</span>
                    {!enabled && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({PHASE_5_NOTE})
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
                        disabled={!enabled && m === 'api'}
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
