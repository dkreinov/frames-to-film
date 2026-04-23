import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE_DIR = path.resolve(__dirname, '../../tests/fixtures/fake_project')

test('generate: prompts auto-load, edit persists, generate renders videos', async ({ page, request }) => {
  // Seed via Upload -> Prepare -> Storyboard Next -> Generate.
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

  // Prompts auto-gen spinner then editable rows.
  const rows = page.getByRole('textbox', { name: /^prompt for pair /i })
  await expect.poll(async () => await rows.count(), { timeout: 20_000 }).toBeGreaterThan(0)
  const rowCount = await rows.count()
  expect(rowCount).toBeGreaterThanOrEqual(3)  // 4 frames -> 3 pairs

  // Edit the first textarea, assert the debounced PUT /prompts fires.
  const firstRow = rows.first()
  const putPromise = page.waitForRequest(
    (req) => req.url().includes('/prompts') && req.method() === 'PUT',
    { timeout: 5_000 }
  )
  await firstRow.fill('custom e2e prompt')
  const putReq = await putPromise
  const putBody = JSON.parse(putReq.postData() ?? '{}') as { prompts: Record<string, string> }
  expect(Object.values(putBody.prompts)).toContain('custom e2e prompt')

  // Click Generate videos, wait for job done + posters.
  const generateBtn = page.getByRole('button', { name: /generate videos/i })
  await expect(generateBtn).toBeEnabled({ timeout: 10_000 })
  await generateBtn.click()
  const posters = page.getByRole('button', { name: /^play /i })
  await expect.poll(async () => await posters.count(), { timeout: 45_000 }).toBeGreaterThan(0)

  // Next: Review button is enabled now.
  await expect(page.getByRole('button', { name: /next: review/i })).toBeEnabled()

  // Cleanup.
  await request.delete(`http://127.0.0.1:8000/projects/${projectId}`)
})
