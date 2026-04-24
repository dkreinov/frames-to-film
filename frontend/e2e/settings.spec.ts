import { test, expect } from '@playwright/test'

test.setTimeout(120_000)

test('settings: save Gemini + fal keys, flip api radios, verify both headers on request', async ({
  page,
}) => {
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: /^Settings$/ })).toBeVisible()

  // Paste fake Gemini + fal.ai keys.
  await page.getByLabel(/gemini api key/i).fill('test-key-abc')
  await page.getByLabel(/fal\.ai api key/i).fill('fal-key-xyz')

  // Two Save buttons now — one per field. Click both.
  const saves = page.getByRole('button', { name: /^save$/i })
  await expect(saves).toHaveCount(2)
  await saves.nth(0).click()
  await saves.nth(1).click()

  // Flip both api radios that are enabled this phase.
  const promptsApi = page.getByRole('radio', { name: /generate prompts — api/i })
  await promptsApi.check()
  await expect(promptsApi).toBeChecked()
  const videosApi = page.getByRole('radio', { name: /generate videos — api/i })
  await videosApi.check()
  await expect(videosApi).toBeChecked()

  // Navigate into the wizard flow and trigger a request that passes
  // through the api client. Hit /projects/abc/prepare — PrepareScreen
  // mounts, fires POST /prepare, and BOTH headers must arrive on that
  // request. (The project won't exist and the backend will 404 the
  // prepare POST, but the headers still travel.)
  const reqPromise = page.waitForRequest(
    (req) =>
      req.headers()['x-gemini-key'] === 'test-key-abc' &&
      req.headers()['x-fal-key'] === 'fal-key-xyz' &&
      ['POST', 'GET', 'PUT'].includes(req.method()),
    { timeout: 10_000 }
  )
  await page.goto('/projects/does-not-exist/prepare')
  const req = await reqPromise
  expect(req.headers()['x-gemini-key']).toBe('test-key-abc')
  expect(req.headers()['x-fal-key']).toBe('fal-key-xyz')
})

test('settings: without saved keys, no request carries x-gemini-key or x-fal-key', async ({
  page,
}) => {
  // Authenticity (plan-skill #9): the positive test above would pass
  // even if apiFetch hardcoded both headers. This negative test fails
  // unless each header is truly sourced from localStorage.
  await page.addInitScript(() => {
    try {
      window.localStorage.removeItem('olga.keys')
      window.localStorage.removeItem('olga.modes')
    } catch {
      // some browsers throw on storage access; test still meaningful
    }
  })

  const requests: Array<{
    url: string
    gemini: string | undefined
    fal: string | undefined
  }> = []
  page.on('request', (r) => {
    requests.push({
      url: r.url(),
      gemini: r.headers()['x-gemini-key'],
      fal: r.headers()['x-fal-key'],
    })
  })

  await page.goto('/projects/does-not-exist/prepare')
  await page.waitForTimeout(1500)

  const apiCalls = requests.filter((r) => r.url.includes('/api/') || r.url.includes('/projects/'))
  expect(apiCalls.length).toBeGreaterThan(0) // confirm traffic actually observed
  for (const r of apiCalls) {
    expect(r.gemini, `request ${r.url} leaked x-gemini-key`).toBeUndefined()
    expect(r.fal, `request ${r.url} leaked x-fal-key`).toBeUndefined()
  }
})

test('settings: only fal key saved → only x-fal-key travels (independent of Gemini)', async ({
  page,
}) => {
  // Authenticity: the two headers must attach independently. Saving
  // only fal must produce X-Fal-Key + no X-Gemini-Key on subsequent
  // requests.
  await page.goto('/settings')
  await page.getByLabel(/fal\.ai api key/i).fill('fal-solo-abc')
  const saves = page.getByRole('button', { name: /^save$/i })
  await saves.nth(1).click() // fal's Save (second button)

  const reqPromise = page.waitForRequest(
    (req) =>
      req.headers()['x-fal-key'] === 'fal-solo-abc' &&
      ['POST', 'GET', 'PUT'].includes(req.method()),
    { timeout: 10_000 }
  )
  await page.goto('/projects/does-not-exist/prepare')
  const req = await reqPromise
  expect(req.headers()['x-fal-key']).toBe('fal-solo-abc')
  expect(req.headers()['x-gemini-key']).toBeUndefined()
})
