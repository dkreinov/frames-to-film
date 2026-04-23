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

test('golden: Upload screen empty + with-files states', async ({ page }) => {
  // Empty state
  await page.goto('/projects/new/upload')
  await page.getByRole('heading', { name: /upload your photos/i }).waitFor()
  // Give Tailwind a moment to settle + hide the BackendStatus dot
  await page.waitForTimeout(400)
  await page.screenshot({
    path: path.join(GOLDEN_DIR, 'phase_4_upload_empty.png'),
    fullPage: true,
  })

  // With-files state
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles([
    path.join(FIXTURE_DIR, 'frame_1_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_2_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_3_gemini.png'),
  ])
  await page.getByText('frame_1_gemini.png').waitFor()
  await page.screenshot({
    path: path.join(GOLDEN_DIR, 'phase_4_upload_with_files.png'),
    fullPage: true,
  })
})
