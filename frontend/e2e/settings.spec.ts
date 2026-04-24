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

test('settings: without a saved key, no request carries x-gemini-key', async ({
  page,
}) => {
  // Authenticity (plan-skill #9): the positive test above would
  // pass even if apiFetch hardcoded the header. This negative test
  // fails unless the header is truly sourced from localStorage.
  await page.addInitScript(() => {
    try {
      window.localStorage.removeItem('olga.keys')
      window.localStorage.removeItem('olga.modes')
    } catch {
      // some browsers throw on storage access; test still meaningful
    }
  })

  // Collect every outbound request made while the Prepare screen mounts
  // and its initial queries fire. Then assert none of them carry the
  // header.
  const requests: Array<{ url: string; header: string | undefined }> = []
  page.on('request', (r) => {
    requests.push({ url: r.url(), header: r.headers()['x-gemini-key'] })
  })

  await page.goto('/projects/does-not-exist/prepare')
  // Give the screen time to fire its initial mutation + polling.
  await page.waitForTimeout(1500)

  const apiCalls = requests.filter((r) => r.url.includes('/api/') || r.url.includes('/projects/'))
  expect(apiCalls.length).toBeGreaterThan(0) // ensure we actually observed traffic
  for (const r of apiCalls) {
    expect(r.header, `request ${r.url} leaked x-gemini-key`).toBeUndefined()
  }
})
