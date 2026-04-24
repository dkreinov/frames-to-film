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
  await page.getByRole('button', { name: /^save$/i }).click()
  // Show the key so the screenshot captures a non-empty field visibly.
  await page.getByRole('button', { name: /show key/i }).click()
  await page.getByRole('radio', { name: /generate prompts — api/i }).check()
  await page.waitForTimeout(300)

  await page.screenshot({
    path: path.join(GOLDEN_DIR, 'phase_4_settings.png'),
    fullPage: true,
  })
})
