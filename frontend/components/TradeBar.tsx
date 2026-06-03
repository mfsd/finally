'use client'
import { useState } from 'react'
import { executeTrade } from '@/lib/api'
import { usePortfolioStore } from '@/store/portfolioStore'

export default function TradeBar() {
  const [ticker, setTicker] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [status, setStatus] = useState<{ msg: string; ok: boolean } | null>(null)
  const refresh = usePortfolioStore((s) => s.refresh)

  async function trade(side: 'buy' | 'sell') {
    const t = ticker.trim().toUpperCase()
    const q = parseFloat(quantity)
    if (!t || isNaN(q) || q <= 0) return
    try {
      const result = await executeTrade(t, q, side)
      if (result.success) {
        setStatus({ msg: side.toUpperCase() + ' ' + q + ' ' + t + ' @ $' + (result.trade?.price?.toFixed(2) ?? '?') + ' ✓', ok: true })
        await refresh()
      } else {
        setStatus({ msg: result.detail || result.message || 'Trade failed', ok: false })
      }
    } catch {
      setStatus({ msg: 'Error executing trade', ok: false })
    }
    setTimeout(() => setStatus(null), 4000)
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderTop: '1px solid #30363d', borderBottom: '1px solid #30363d', backgroundColor: '#161b22', flexShrink: 0 }}>
      <input style={{ width: 80, padding: '4px 8px', fontSize: 12, borderRadius: 4, fontFamily: 'monospace', backgroundColor: '#0d1117', border: '1px solid #30363d', color: '#ecad0a', outline: 'none' }} placeholder='TICKER' value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} />
      <input type='number' style={{ width: 64, padding: '4px 8px', fontSize: 12, borderRadius: 4, fontFamily: 'monospace', backgroundColor: '#0d1117', border: '1px solid #30363d', color: '#e6edf3', outline: 'none' }} placeholder='Qty' value={quantity} onChange={(e) => setQuantity(e.target.value)} min='0.01' step='1' />
      <button onClick={() => trade('buy')} style={{ padding: '4px 14px', fontSize: 12, borderRadius: 4, fontWeight: 'bold', backgroundColor: '#209dd7', color: '#fff', border: 'none', cursor: 'pointer' }}>BUY</button>
      <button onClick={() => trade('sell')} style={{ padding: '4px 14px', fontSize: 12, borderRadius: 4, fontWeight: 'bold', backgroundColor: '#da3633', color: '#fff', border: 'none', cursor: 'pointer' }}>SELL</button>
      {status && (<span style={{ fontSize: 12, marginLeft: 8, color: status.ok ? '#3fb950' : '#f85149' }}>{status.msg}</span>)}
    </div>
  )
}
