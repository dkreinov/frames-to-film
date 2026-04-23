import { test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE_DIR = path.resolve(__dirname, '../../tests/fixtures/fake_project')
const GOLDEN_DIR = path.resolve(__dirname, '../../docs/design/golden')

test.beforeAll(() => fs.mkdirSync(GOLDEN_DIR, { recursive: true }))

test('golden: Generate screen videos ready', async ({ page, request }) => {
  await page.goto('/projects/new/upload')
  await page.locator('input[type="file"]').setInputFiles([
    path.join(FIXTURE_DIR, 'frame_1_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_2_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_3_gemini.png'),
  ])
  await page.getByRole('button', { name: /next/i }).click()
  await page.waitForURL(/\/prepare$/, { timeout: 15_000 })
  await page.getByText(/prepared \d+ photos?/i).waitFor({ timeout: 15_000 })
  const projectId = page.url().match(/\/projects\/([a-f0-9]{32})\//)![1]

  await page.getByRole('button', { name: /next/i }).click()
  await page.waitForURL(/\/storyboard$/, { timeout: 5_000 })
  await page.getByRole('button', { name: /^drag frame /i }).first().waitFor({ timeout: 15_000 })

  await page.getByRole('button', { name: /next: generate/i }).click()
  await page.waitForURL(/\/generate$/, { timeout: 5_000 })

  const rows = page.getByRole('textbox', { name: /^prompt for pair /i })
  await rows.first().waitFor({ timeout: 20_000 })

  const generateBtn = page.getByRole('button', { name: /generate videos/i })
  await generateBtn.click()
  const posters = page.getByRole('button', { name: /^play /i })
  await posters.first().waitFor({ timeout: 45_000 })
  // Give the page a moment to settle before the snap.
  await page.waitForTimeout(500)

  await page.screenshot({
    path: path.join(GOLDEN_DIR, 'phase_4_generate_ready.png'),
    fullPage: true,
  })

  await request.delete(`http://127.0.0.1:8000/projects/${projectId}`)
})
