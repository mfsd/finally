'use client'
import { usePortfolioStore } from '@/store/portfolioStore'
import { usePriceStore } from '@/store/priceStore'
import { ResponsiveTreeMap } from '@nivo/treemap'

function getPnlColor(pnlPct: number): string {
  if (pnlPct > 5) return '#238636'
  if (pnlPct > 2) return '#3fb950'
  if (pnlPct > 0.5) return '#56d364'
  if (pnlPct > -0.5) return '#6e7681'
  if (pnlPct > -2) return '#da3633'
  if (pnlPct > -5) return '#f85149'
  return '#ff7b72'
}

export default function PortfolioHeatmap() {
  const positions = usePortfolioStore((s) => s.positions)
  const prices = usePriceStore((s) => s.prices)

  if (positions.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#8b949e', fontSize: 12 }}>
        No positions yet
      </div>
    )
  }

  const data = {
    id: 'portfolio',
    children: positions.map((p) => {
      const livePrice = prices[p.ticker]?.price ?? p.current_price
      const value = Math.max(livePrice * p.quantity, 0.01)
      const pnlPct = p.avg_cost > 0 ? ((livePrice - p.avg_cost) / p.avg_cost) * 100 : 0
      return { id: p.ticker, value, pnlPct }
    })
  }

  return (
    <ResponsiveTreeMap
      data={data}
      identity="id"
      value="value"
      margin={{ top: 4, right: 4, bottom: 4, left: 4 }}
      labelSkipSize={20}
      label={(node: any) => node.id}
      colors={(node: any) => getPnlColor(node.data?.pnlPct ?? 0)}
      borderColor="#0d1117"
      borderWidth={2}
      labelTextColor="#e6edf3"
      parentLabelTextColor="#e6edf3"
      nodeOpacity={0.9}
      theme={{
        labels: { text: { fontSize: 11, fontWeight: 'bold' } },
      }}
    />
  )
}
