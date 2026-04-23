import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE_DIR = path.resolve(__dirname, '../../tests/fixtures/fake_project')

test('upload screen: drop 2 photos, click next, land on prepare', async ({ page, request }) => {
  await page.goto('/projects/new/upload')
  await expect(page.getByRole('heading', { name: /upload your photos/i })).toBeVisible()

  // Click-to-browse via hidden input (can't simulate DataTransfer reliably in
  // Playwright; setInputFiles on the hidden <input type=file> is the canonical
  // way to drive this flow).
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles([
    path.join(FIXTURE_DIR, 'frame_1_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_2_gemini.png'),
  ])

  // Files listed
  await expect(page.getByText('frame_1_gemini.png')).toBeVisible()
  await expect(page.getByText('frame_2_gemini.png')).toBeVisible()

  // Next button enabled; click it and await navigation to prepare
  const nextBtn = page.getByRole('button', { name: /next/i })
  await expect(nextBtn).toBeEnabled()
  await nextBtn.click()

  // URL becomes /projects/<id>/prepare
  await page.waitForURL(/\/projects\/[a-f0-9]{32}\/prepare$/, { timeout: 15_000 })

  // Backend should have both uploads under the created project
  const match = page.url().match(/\/projects\/([a-f0-9]{32})\//)
  expect(match).not.toBeNull()
  const projectId = match![1]

  const uploadsRes = await request.get(`http://127.0.0.1:8000/projects/${projectId}/uploads`)
  expect(uploadsRes.ok()).toBeTruthy()
  const uploads = (await uploadsRes.json()) as Array<{ filename: string }>
  expect(uploads.map((u) => u.filename).sort()).toEqual([
    'frame_1_gemini.png',
    'frame_2_gemini.png',
  ])

  // Cleanup — delete the project so the test is idempotent
  await request.delete(`http://127.0.0.1:8000/projects/${projectId}`)
})
