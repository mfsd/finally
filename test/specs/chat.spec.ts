import { test, expect } from '@playwright/test'

test.describe('AI Chat (Mock Mode)', () => {
  test('chat endpoint returns message and empty action arrays', async ({ request }) => {
    const resp = await request.post('/api/chat', {
      data: { message: 'How is my portfolio?' },
    })
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body.message).toBeTruthy()
    expect(typeof body.message).toBe('string')
    expect(Array.isArray(body.trades_executed)).toBe(true)
    expect(Array.isArray(body.trades_failed)).toBe(true)
    expect(Array.isArray(body.watchlist_changes)).toBe(true)
  })

  test('portfolio history endpoint returns data', async ({ request }) => {
    const resp = await request.get('/api/portfolio/history')
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(Array.isArray(body.history)).toBe(true)
  })
})
