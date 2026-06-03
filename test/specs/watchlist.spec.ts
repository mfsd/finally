import { test, expect } from '@playwright/test'

test.describe('Watchlist Management', () => {
  test('add and remove a ticker', async ({ request }) => {
    // Add PYPL
    const addResp = await request.post('/api/watchlist', {
      data: { ticker: 'PYPL' },
    })
    expect(addResp.status()).toBe(200)
    const addResult = await addResp.json()
    expect(addResult.ticker).toBe('PYPL')

    // Verify it's in the list
    const listResp = await request.get('/api/watchlist')
    const list = await listResp.json()
    expect(list.watchlist.map((w: any) => w.ticker)).toContain('PYPL')

    // Remove it
    const delResp = await request.delete('/api/watchlist/PYPL')
    expect(delResp.status()).toBe(204)

    // Verify gone
    const listAfter = await (await request.get('/api/watchlist')).json()
    expect(listAfter.watchlist.map((w: any) => w.ticker)).not.toContain('PYPL')
  })

  test('add duplicate is idempotent (not an error)', async ({ request }) => {
    const r1 = await request.post('/api/watchlist', { data: { ticker: 'AMZN' } })
    // AMZN is already in default list; should not error
    expect([200, 200]).toContain(r1.status())

    const r2 = await request.post('/api/watchlist', { data: { ticker: 'AMZN' } })
    expect(r2.status()).toBe(200)
  })

  test('remove non-existent ticker returns 404', async ({ request }) => {
    const resp = await request.delete('/api/watchlist/ZZZNOTREAL')
    expect(resp.status()).toBe(404)
  })
})
