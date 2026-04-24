import { test, expect } from '@playwright/test'

test.setTimeout(120_000)

test('settings: save Gemini key, toggle Generate prompts api, verify header on request', async ({
  page,
}) => {
  // Visit the Settings screen (AppBar links here via the gear icon).
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: /^Settings$/ })).toBeVisible()

  // Paste a fake Gemini key and save.
  const input = page.getByLabel(/gemini api key/i)
  await input.fill('test-key-abc')
  await page.getByRole('button', { name: /^save$/i }).click()

  // Flip Generate prompts to api.
  const apiRadio = page.getByRole('radio', {
    name: /generate prompts — api/i,
  })
  await apiRadio.check()
  await expect(apiRadio).toBeChecked()

  // Navigate into the wizard flow and trigger a request that passes
  // through the api client. Easiest: hit /projects/abc/prepare —
  // PrepareScreen mounts, fires POST /prepare, and our header must
  // arrive on that request. (The project won't exist and the backend
  // will 404 the prepare POST, but the headers still travel.)
  const reqPromise = page.waitForRequest(
    (req) =>
      req.headers()['x-gemini-key'] === 'test-key-abc' &&
      ['POST', 'GET', 'PUT'].includes(req.method()),
    { timeout: 10_000 }
  )
  await page.goto('/projects/does-not-exist/prepare')
  const req = await reqPromise
  expect(req.headers()['x-gemini-key']).toBe('test-key-abc')
})
