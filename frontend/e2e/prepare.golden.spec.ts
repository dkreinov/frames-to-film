import { test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE_DIR = path.resolve(__dirname, '../../tests/fixtures/fake_project')
const GOLDEN_DIR = path.resolve(__dirname, '../../docs/design/golden')

test.beforeAll(() => {
  fs.mkdirSync(GOLDEN_DIR, { recursive: true })
})

test('golden: Prepare screen (running + done states)', async ({ page, request }) => {
  // Seed via Upload flow
  await page.goto('/projects/new/upload')
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles([
    path.join(FIXTURE_DIR, 'frame_1_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_2_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_3_gemini.png'),
  ])
  await page.getByRole('button', { name: /next/i }).click()
  await page.waitForURL(/\/projects\/[a-f0-9]{32}\/prepare$/, { timeout: 15_000 })

  // Running state screenshot — try to catch while still polling.
  // TestClient's BackgroundTasks run before response returns, so by the time
  // we navigate, the job is likely already done. Hard to capture running
  // state deterministically — just snapshot whatever the screen is showing
  // right after navigation.
  await page.waitForTimeout(200)
  await page.screenshot({
    path: path.join(GOLDEN_DIR, 'phase_4_prepare_early.png'),
    fullPage: true,
  })

  // Wait for the grid, then snapshot the done state.
  await page.getByText(/prepared \d+ photos?/i).waitFor({ timeout: 15_000 })
  await page.waitForTimeout(400)  // give images a moment to paint
  await page.screenshot({
    path: path.join(GOLDEN_DIR, 'phase_4_prepare_done.png'),
    fullPage: true,
  })

  // Cleanup
  const match = page.url().match(/\/projects\/([a-f0-9]{32})\//)
  if (match) {
    await request.delete(`http://127.0.0.1:8000/projects/${match[1]}`)
  }
})
