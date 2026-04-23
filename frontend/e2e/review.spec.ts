import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE_DIR = path.resolve(__dirname, '../../tests/fixtures/fake_project')

test.setTimeout(120_000)

test('review: rows render, verdict persists, stitch exports and shows download link', async ({
  page,
  request,
}) => {
  // Full wizard: Upload -> Prepare -> Storyboard -> Generate -> Review.
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
  await expect(generateBtn).toBeEnabled({ timeout: 10_000 })
  await generateBtn.click()
  const posters = page.getByRole('button', { name: /^play /i })
  await posters.first().waitFor({ timeout: 45_000 })

  await page.getByRole('button', { name: /next: review/i }).click()
  await page.waitForURL(/\/review$/, { timeout: 5_000 })

  // One verdict button per pair x 3 verdicts. Seed frames = 4 (upload
  // produced 4 via outpaint) -> pairs = 3; so 9 verdict buttons.
  const winnerBtns = page.getByRole('button', { name: /mark .+ as winner/i })
  await expect
    .poll(async () => await winnerBtns.count(), { timeout: 30_000 })
    .toBeGreaterThanOrEqual(1)

  // Click winner on the first pair, verify POST /segments/.../review fires.
  const first = winnerBtns.first()
  const postPromise = page.waitForRequest(
    (req) => req.url().includes('/segments/') && req.method() === 'POST',
    { timeout: 10_000 }
  )
  await first.click()
  await postPromise
  await expect.poll(async () => first.getAttribute('aria-pressed'), {
    timeout: 5_000,
  }).toBe('true')

  // Stitch & Export -> Download link appears.
  const stitchBtn = page.getByRole('button', { name: /stitch & export/i })
  await expect(stitchBtn).toBeEnabled()
  await stitchBtn.click()
  const downloadLink = page.getByRole('link', { name: /download full movie/i })
  await downloadLink.waitFor({ timeout: 30_000 })
  expect(await downloadLink.getAttribute('href')).toMatch(/\/projects\/[a-f0-9]{32}\/download$/)
  expect(await downloadLink.getAttribute('download')).not.toBeNull()
  // Don't click it — would trigger an actual file download in headless.

  // Cleanup.
  await request.delete(`http://127.0.0.1:8000/projects/${projectId}`)
})
