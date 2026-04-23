import { test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE_DIR = path.resolve(__dirname, '../../tests/fixtures/fake_project')
const GOLDEN_DIR = path.resolve(__dirname, '../../docs/design/golden')

test.beforeAll(() => fs.mkdirSync(GOLDEN_DIR, { recursive: true }))

test('golden: Storyboard grid', async ({ page, request }) => {
  // Seed via Upload + Prepare
  await page.goto('/projects/new/upload')
  await page.locator('input[type="file"]').setInputFiles([
    path.join(FIXTURE_DIR, 'frame_1_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_2_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_3_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_4_gemini.png'),
  ])
  await page.getByRole('button', { name: /next/i }).click()
  await page.waitForURL(/\/prepare$/, { timeout: 15_000 })
  await page.getByText(/prepared \d+ photos?/i).waitFor({ timeout: 15_000 })
  const projectId = page.url().match(/\/projects\/([a-f0-9]{32})\//)![1]

  await page.getByRole('button', { name: /next/i }).click()
  await page.waitForURL(/\/storyboard$/, { timeout: 5_000 })
  // Wait for grid
  const drag = page.getByRole('button', { name: /^drag frame /i })
  await drag.first().waitFor({ timeout: 15_000 })
  await page.waitForTimeout(400)
  await page.screenshot({
    path: path.join(GOLDEN_DIR, 'phase_4_storyboard_grid.png'),
    fullPage: true,
  })

  await request.delete(`http://127.0.0.1:8000/projects/${projectId}`)
})
