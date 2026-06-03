import { test, expect } from '@playwright/test'

test.describe('FinAlly Smoke Tests', () => {
  test('homepage loads and shows trading terminal', async ({ page }) => {
    await page.goto('/')
    // Should show FinAlly branding in the header
    await expect(page.locator('text=FinAlly').first()).toBeVisible({ timeout: 10000 })
  })

  test('health endpoint returns ok', async ({ request }) => {
    const resp = await request.get('/api/health')
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body.status).toBe('ok')
  })

  test('portfolio API returns initial state', async ({ request }) => {
    const resp = await request.get('/api/portfolio')
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    // cash_balance and total_value may differ from 10000 if prior tests ran trades
    expect(typeof body.cash_balance).toBe('number')
    expect(body.cash_balance).toBeGreaterThan(0)
    expect(Array.isArray(body.positions)).toBe(true)
    expect(typeof body.total_value).toBe('number')
    expect(body.total_value).toBeGreaterThan(0)
  })

  test('watchlist API returns 10 default tickers', async ({ request }) => {
    const resp = await request.get('/api/watchlist')
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body.watchlist).toHaveLength(10)
    const tickers = body.watchlist.map((w: any) => w.ticker)
    expect(tickers).toContain('AAPL')
    expect(tickers).toContain('NVDA')
  })

  test('SSE stream delivers price events', async ({ page }) => {
    // Navigate to the app first so relative URL resolution works
    await page.goto('/')
    // Use the browser page to open the SSE stream and read the first chunk
    // The server sends named events: "event: prices"
    const sseData = await page.evaluate(async () => {
      return new Promise<string>((resolve, reject) => {
        const es = new EventSource('/api/stream/prices')
        const timeout = setTimeout(() => {
          es.close()
          reject(new Error('SSE timeout: no event received within 8s'))
        }, 8000)
        // Named event listener for "prices"
        es.addEventListener('prices', (event: MessageEvent) => {
          clearTimeout(timeout)
          es.close()
          resolve(event.data)
        })
        es.onerror = () => {
          clearTimeout(timeout)
          es.close()
          reject(new Error('SSE connection error'))
        }
      })
    })
    // sseData should be a JSON array of price objects
    expect(sseData).toBeTruthy()
    const parsed = JSON.parse(sseData)
    expect(Array.isArray(parsed)).toBe(true)
    expect(parsed.length).toBeGreaterThan(0)
    expect(parsed[0]).toHaveProperty('ticker')
    expect(parsed[0]).toHaveProperty('price')
  })
})
