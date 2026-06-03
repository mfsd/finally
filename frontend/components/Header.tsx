'use client'
import { usePriceStore } from '@/store/priceStore'
import { usePortfolioStore } from '@/store/portfolioStore'

function fmt(n: number) {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function StatusDot({ status }: { status: 'connected' | 'reconnecting' | 'disconnected' }) {
  const colors = {
    connected: '#3fb950',
    reconnecting: '#f0ad4e',
    disconnected: '#f85149',
  }
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#8b949e', fontSize: '11px' }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: colors[status], display: 'inline-block' }} />
      {status}
    </span>
  )
}

export default function Header() {
  const status = usePriceStore((s) => s.status)
  const { totalValue, totalPnl, totalPnlPct, cashBalance } = usePortfolioStore()
  const pnlColor = totalPnl >= 0 ? '#3fb950' : '#f85149'
  const sign = totalPnl >= 0 ? '+' : ''

  return (
    <header style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 16px', height: 52,
      backgroundColor: '#161b22', borderBottom: '1px solid #30363d',
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 20, fontWeight: 'bold', color: '#ecad0a', letterSpacing: 1 }}>FinAlly</span>
        <span style={{ fontSize: 11, color: '#8b949e' }}>AI Trading Workstation</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: '#8b949e' }}>PORTFOLIO</div>
          <div style={{ fontSize: 18, fontWeight: 'bold', color: '#e6edf3', lineHeight: 1.2 }}>{fmt(totalValue)}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: '#8b949e' }}>P&amp;L</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: pnlColor }}>
            {sign}{fmt(totalPnl)} ({sign}{totalPnlPct.toFixed(2)}%)
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: '#8b949e' }}>CASH</div>
          <div style={{ fontSize: 13, color: '#e6edf3' }}>{fmt(cashBalance)}</div>
        </div>
        <StatusDot status={status} />
      </div>
    </header>
  )
}
