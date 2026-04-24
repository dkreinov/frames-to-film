import { test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const GOLDEN_DIR = path.resolve(__dirname, '../../docs/design/golden')

test.beforeAll(() => fs.mkdirSync(GOLDEN_DIR, { recursive: true }))

test.setTimeout(120_000)

test('golden: Settings screen with filled Gemini key + Generate prompts api', async ({
  page,
}) => {
  await page.goto('/settings')
  await page.getByLabel(/gemini api key/i).fill('test-key-abc')
  await page.getByLabel(/fal\.ai api key/i).fill('fal-key-xyz')
  // Two Save buttons now (Gemini + fal) — click each by index.
  const saves = page.getByRole('button', { name: /^save$/i })
  await saves.nth(0).click()
  await saves.nth(1).click()
  // Show both keys so the screenshot captures non-empty field values.
  await page.getByRole('button', { name: /show gemini-key value/i }).click()
  await page.getByRole('button', { name: /show fal-key value/i }).click()
  await page.getByRole('radio', { name: /generate prompts — api/i }).check()
  await page.getByRole('radio', { name: /generate videos — api/i }).check()
  await page.waitForTimeout(300)

  await page.screenshot({
    path: path.join(GOLDEN_DIR, 'phase_4_settings.png'),
    fullPage: true,
  })
})
