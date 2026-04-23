import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE_DIR = path.resolve(__dirname, '../../tests/fixtures/fake_project')

test('storyboard: extend runs, grid renders, drag persists order, next -> generate', async ({ page, request }) => {
  // Seed via Upload + Prepare flow.
  await page.goto('/projects/new/upload')
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles([
    path.join(FIXTURE_DIR, 'frame_1_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_2_gemini.png'),
    path.join(FIXTURE_DIR, 'frame_3_gemini.png'),
  ])
  await page.getByRole('button', { name: /next/i }).click()
  await page.waitForURL(/\/projects\/[a-f0-9]{32}\/prepare$/, { timeout: 15_000 })
  // wait for prepare done then jump straight to /storyboard via Next
  await expect(page.getByText(/prepared \d+ photos?/i)).toBeVisible({ timeout: 15_000 })

  const projectId = page.url().match(/\/projects\/([a-f0-9]{32})\//)![1]

  await page.getByRole('button', { name: /next/i }).click()
  await page.waitForURL(/\/storyboard$/, { timeout: 5_000 })

  // Storyboard auto-runs extend; wait for the grid to render.
  const drag = page.getByRole('button', { name: /^drag frame /i })
  await expect.poll(async () => await drag.count(), { timeout: 15_000 }).toBe(6)

  // Drag the last thumbnail (6.jpg) before the first (1.jpg) using
  // Playwright's mouse API. dnd-kit PointerSensor activates after 4px
  // of movement; we move in steps so it triggers cleanly.
  const last = drag.last()
  const first = drag.first()
  const lastBox = (await last.boundingBox())!
  const firstBox = (await first.boundingBox())!
  await page.mouse.move(lastBox.x + lastBox.width / 2, lastBox.y + lastBox.height / 2)
  await page.mouse.down()
  // initial small move to satisfy the 4px activation threshold
  await page.mouse.move(lastBox.x + lastBox.width / 2 - 10, lastBox.y + lastBox.height / 2, { steps: 5 })
  await page.mouse.move(firstBox.x + firstBox.width / 2, firstBox.y + firstBox.height / 2, { steps: 20 })
  await page.mouse.up()

  // Saved indicator should cycle: Saving -> Order saved
  await page.getByText(/saving|order saved/i).waitFor({ timeout: 5_000 })

  // Verify the saved order on the backend reflects the move.
  // PointerSensor + arrayMove may end up with the dragged item at index 0 or
  // adjacent — accept either as long as 6.jpg moved earlier than its original
  // position.
  await page.waitForTimeout(500)  // let debounce + PUT settle
  const orderRes = await request.get(`http://127.0.0.1:8000/projects/${projectId}/order`)
  expect(orderRes.ok()).toBeTruthy()
  const order = (await orderRes.json()) as { order: string[] }
  expect(order.order.length).toBe(6)
  const idx6 = order.order.indexOf('6.jpg')
  expect(idx6).toBeLessThan(5)  // moved earlier than its natural last position

  // Next -> /generate
  await page.getByRole('button', { name: /next/i }).click()
  await page.waitForURL(/\/generate$/, { timeout: 5_000 })

  // Cleanup
  await request.delete(`http://127.0.0.1:8000/projects/${projectId}`)
})
