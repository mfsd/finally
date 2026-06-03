import { test, expect } from '@playwright/test'

test.describe('Trading Flow', () => {
  test('buy shares: cash decreases, position appears', async ({ request }) => {
    // Get initial state
    const initial = await (await request.get('/api/portfolio')).json()
    const initialCash = initial.cash_balance

    // Buy 5 shares of AAPL
    const tradeResp = await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', quantity: 5, side: 'buy' },
    })
    expect(tradeResp.status()).toBe(200)
    const trade = await tradeResp.json()
    expect(trade.success).toBe(true)
    expect(trade.trade.ticker).toBe('AAPL')
    expect(trade.trade.side).toBe('buy')
    expect(trade.cash_balance).toBeLessThan(initialCash)

    // Verify position created/increased by 5
    const portfolio = await (await request.get('/api/portfolio')).json()
    const aaplPos = portfolio.positions.find((p: any) => p.ticker === 'AAPL')
    expect(aaplPos).toBeDefined()
    const initialAaplQty = initial.positions.find((p: any) => p.ticker === 'AAPL')?.quantity ?? 0
    expect(aaplPos.quantity).toBe(initialAaplQty + 5)
  })

  test('sell shares: cash increases, position updates', async ({ request }) => {
    // Ensure we have a position first
    await request.post('/api/portfolio/trade', {
      data: { ticker: 'MSFT', quantity: 10, side: 'buy' },
    })

    const beforeSell = await (await request.get('/api/portfolio')).json()
    const cashBefore = beforeSell.cash_balance
    const msftQtyBefore = beforeSell.positions.find((p: any) => p.ticker === 'MSFT')?.quantity ?? 0

    // Sell 3 shares
    const sellResp = await request.post('/api/portfolio/trade', {
      data: { ticker: 'MSFT', quantity: 3, side: 'sell' },
    })
    expect(sellResp.status()).toBe(200)
    const sellResult = await sellResp.json()
    expect(sellResult.success).toBe(true)
    expect(sellResult.cash_balance).toBeGreaterThan(cashBefore)

    // Verify position reduced by 3
    const portfolio = await (await request.get('/api/portfolio')).json()
    const msftPos = portfolio.positions.find((p: any) => p.ticker === 'MSFT')
    expect(msftPos).toBeDefined()
    expect(msftPos.quantity).toBe(msftQtyBefore - 3)
  })

  test('buy with insufficient cash returns 422', async ({ request }) => {
    const resp = await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', quantity: 999999, side: 'buy' },
    })
    expect(resp.status()).toBe(422)
  })

  test('sell more than owned returns 422', async ({ request }) => {
    const resp = await request.post('/api/portfolio/trade', {
      data: { ticker: 'GOOGL', quantity: 999999, side: 'sell' },
    })
    expect(resp.status()).toBe(422)
  })
})
