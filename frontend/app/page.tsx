'use client'
import { useEffect, useState } from 'react'
import { usePriceStore } from '@/store/priceStore'
import { usePortfolioStore } from '@/store/portfolioStore'
import Header from '@/components/Header'
import Watchlist from '@/components/Watchlist'
import MainChart from '@/components/MainChart'
import PortfolioHeatmap from '@/components/PortfolioHeatmap'
import PnLChart from '@/components/PnLChart'
import PositionsTable from '@/components/PositionsTable'
import TradeBar from '@/components/TradeBar'
import ChatPanel from '@/components/ChatPanel'

export default function TradingTerminal() {
  const [selectedTicker, setSelectedTicker] = useState<string | null>('AAPL')
  const [chatCollapsed, setChatCollapsed] = useState(false)
  const connect = usePriceStore((s) => s.connect)
  const { refresh, refreshHistory } = usePortfolioStore()

  useEffect(() => {
    connect()
    refresh()
    refreshHistory()
    const interval = setInterval(refreshHistory, 30000)
    return () => clearInterval(interval)
  }, [])
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#0d1117', overflow: 'hidden' }}>
      <Header />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ width: 260, flexShrink: 0, overflow: 'hidden' }}>
          <Watchlist selectedTicker={selectedTicker} onSelect={setSelectedTicker} />
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ display: 'flex', height: '44%', borderBottom: '1px solid #30363d', flexShrink: 0 }}>
            <div style={{ flex: 1, overflow: 'hidden' }}><MainChart ticker={selectedTicker} /></div>
            <div style={{ width: 260, borderLeft: '1px solid #30363d', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
              <div style={{ padding: '4px 12px', fontSize: 11, color: '#8b949e', fontWeight: 500, borderBottom: '1px solid #30363d', flexShrink: 0 }}>PORTFOLIO HEATMAP</div>
              <div style={{ flex: 1, overflow: 'hidden' }}><PortfolioHeatmap /></div>
            </div>
          </div>
          <div style={{ height: '22%', borderBottom: '1px solid #30363d', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '4px 12px', fontSize: 11, color: '#8b949e', fontWeight: 500, borderBottom: '1px solid #30363d', flexShrink: 0 }}>PORTFOLIO VALUE</div>
            <div style={{ flex: 1, overflow: 'hidden' }}><PnLChart /></div>
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <TradeBar />
            <div style={{ flex: 1, overflowY: 'auto' }}><PositionsTable /></div>
          </div>
        </div>
        <ChatPanel collapsed={chatCollapsed} onToggle={() => setChatCollapsed((v) => !v)} />
      </div>
    </div>
  )
}
