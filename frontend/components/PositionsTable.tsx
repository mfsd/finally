'use client'
import { usePortfolioStore } from '@/store/portfolioStore'
import { usePriceStore } from '@/store/priceStore'
import { executeTrade } from '@/lib/api'

function fmt(n: number) {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function fmtPct(n: number) {
  const sign = n >= 0 ? '+' : ''
  return sign + n.toFixed(2) + '%'
}
export default function PositionsTable() {
  const { positions, refresh } = usePortfolioStore()
  const prices = usePriceStore((s) => s.prices)

  if (positions.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px', color: '#8b949e', fontSize: 12 }}>
        No positions. Buy something!
      </div>
    )
  }

  async function quickTrade(ticker: string, side: 'buy' | 'sell') {
    await executeTrade(ticker, 1, side)
    await refresh()
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #30363d' }}>
            {['Ticker', 'Qty', 'Avg Cost', 'Price', 'P&L', 'P&L %', 'Daily %', ''].map((h) => (
              <th key={h} style={{ padding: '6px 12px', textAlign: 'left', color: '#8b949e', fontWeight: 500, whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const live = prices[p.ticker]
            const price = live?.price ?? p.current_price
            const pnl = (price - p.avg_cost) * p.quantity
            const pnlPct = p.avg_cost > 0 ? ((price - p.avg_cost) / p.avg_cost) * 100 : 0
            const dailyChg = live?.sessionOpen ? ((live.price - live.sessionOpen) / live.sessionOpen) * 100 : null
            const pnlColor = pnl >= 0 ? '#3fb950' : '#f85149'
            return (
              <tr key={p.ticker} style={{ borderBottom: '1px solid #21262d' }}>
                <td style={{ padding: '6px 12px', fontWeight: 'bold', color: '#ecad0a' }}>{p.ticker}</td>
                <td style={{ padding: '6px 12px', color: '#e6edf3' }}>{p.quantity}</td>
                <td style={{ padding: '6px 12px', color: '#8b949e' }}>{fmt(p.avg_cost)}</td>
                <td style={{ padding: '6px 12px', fontFamily: 'monospace', color: '#e6edf3' }}>{fmt(price)}</td>
                <td style={{ padding: '6px 12px', fontWeight: 600, color: pnlColor }}>{fmt(pnl)}</td>
                <td style={{ padding: '6px 12px', color: pnlColor }}>{fmtPct(pnlPct)}</td>
                <td style={{ padding: '6px 12px', color: dailyChg != null ? (dailyChg >= 0 ? '#3fb950' : '#f85149') : '#8b949e' }}>{dailyChg != null ? fmtPct(dailyChg) : '—'}</td>
                <td style={{ padding: '6px 12px' }}>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button onClick={() => quickTrade(p.ticker, 'buy')} style={{ padding: '2px 8px', fontSize: 11, borderRadius: 3, backgroundColor: '#209dd7', color: '#fff', border: 'none', cursor: 'pointer' }}>B</button>
                    <button onClick={() => quickTrade(p.ticker, 'sell')} style={{ padding: '2px 8px', fontSize: 11, borderRadius: 3, backgroundColor: '#da3633', color: '#fff', border: 'none', cursor: 'pointer' }}>S</button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
