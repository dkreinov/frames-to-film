import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE_DIR = path.resolve(__dirname, '../../tests/fixtures/fake_project')

test('prepare screen: mount polls job, shows grid, next -> storyboard', async ({ page, request }) => {
  // Seed: create project + upload 2 Cosmo frames via the Upload screen.
  await page.goto('/projects/new/upload')
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles([
    path.join(FIXTURE_DIR, 'frame_1_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_2_gemini.png'),
  ])
  await page.getByRole('button', { name: /next/i }).click()
  await page.waitForURL(/\/projects\/[a-f0-9]{32}\/prepare$/, { timeout: 15_000 })

  // Prepare screen auto-posts /prepare — wait for the grid.
  await expect(page.getByText(/prepared \d+ photos?/i)).toBeVisible({ timeout: 15_000 })

  // Outputs grid has the right image count (6 fixture frames -> 6 outpainted)
  const images = page.locator('img')
  await expect.poll(async () => await images.count()).toBeGreaterThanOrEqual(6)

  // Next -> storyboard placeholder
  const nextBtn = page.getByRole('button', { name: /next/i })
  await expect(nextBtn).toBeEnabled()
  await nextBtn.click()
  await page.waitForURL(/\/storyboard$/, { timeout: 5_000 })

  // Cleanup: scrape project id from previous URL param
  const match = page.url().match(/\/projects\/([a-f0-9]{32})\//)
  if (match) {
    await request.delete(`http://127.0.0.1:8000/projects/${match[1]}`)
  }
})
