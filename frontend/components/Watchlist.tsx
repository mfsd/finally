'use client'
import { useEffect, useRef, useState, useCallback } from 'react'
import { usePriceStore } from '@/store/priceStore'
import { addToWatchlist, getWatchlist, removeFromWatchlist } from '@/lib/api'

interface WatchlistItem { ticker: string; price: number | null; daily_change_pct: number | null }

function Sparkline({ history }: { history: number[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)
  const seriesRef = useRef<any>(null)
  const initializedRef = useRef(false)

  useEffect(() => {
    if (!ref.current || initializedRef.current) return
    initializedRef.current = true
    import('lightweight-charts').then(({ createChart, ColorType, AreaSeries }) => {
      if (!ref.current) return
      const chart = createChart(ref.current, {
        width: 80, height: 36,
        layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: 'transparent' },
        grid: { vertLines: { visible: false }, horzLines: { visible: false } },
        crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
        rightPriceScale: { visible: false }, leftPriceScale: { visible: false },
        timeScale: { visible: false }, handleScroll: false, handleScale: false,
      })
      let series: any
      if (AreaSeries) {
        series = chart.addSeries(AreaSeries, { lineColor: '#209dd7', topColor: 'rgba(32,157,215,0.25)', bottomColor: 'rgba(32,157,215,0)', lineWidth: 1 })
      } else {
        series = (chart as any).addAreaSeries({ lineColor: '#209dd7', topColor: 'rgba(32,157,215,0.25)', bottomColor: 'rgba(32,157,215,0)', lineWidth: 1 })
      }
      chartRef.current = chart
      seriesRef.current = series
    })
    return () => { chartRef.current?.remove(); chartRef.current = null; seriesRef.current = null; initializedRef.current = false }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || history.length === 0) return
    const data = history.map((price, i) => ({ time: (i + 1) as any, value: price }))
    try { seriesRef.current.setData(data); chartRef.current?.timeScale().fitContent() } catch {}
  }, [history])

  return <div ref={ref} style={{ width: 80, height: 36, flexShrink: 0 }} />
}
export default function Watchlist({ selectedTicker, onSelect }: { selectedTicker: string | null; onSelect: (t: string) => void }) {
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [newTicker, setNewTicker] = useState('')
  const [adding, setAdding] = useState(false)
  const prices = usePriceStore((s) => s.prices)
  const [flashState, setFlashState] = useState<Record<string, 'up' | 'down' | null>>({})
  const prevPricesRef = useRef<Record<string, number>>({})

  const load = useCallback(async () => {
    try { const data = await getWatchlist(); setItems(data.watchlist ?? []) } catch {}
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const updates: Record<string, 'up' | 'down'> = {}
    for (const [ticker, data] of Object.entries(prices)) {
      const prev = prevPricesRef.current[ticker]
      if (prev !== undefined && Math.abs(prev - data.price) > 0.001) updates[ticker] = data.price > prev ? 'up' : 'down'
      prevPricesRef.current[ticker] = data.price
    }
    if (Object.keys(updates).length === 0) return
    setFlashState((prev) => ({ ...prev, ...updates }))
    const t = setTimeout(() => setFlashState((prev) => { const next = { ...prev }; for (const k of Object.keys(updates)) next[k] = null; return next }), 500)
    return () => clearTimeout(t)
  }, [prices])

  async function handleAdd() {
    const t = newTicker.trim().toUpperCase()
    if (!t) return
    setAdding(true)
    try { await addToWatchlist(t); setNewTicker(''); await load() } catch {} finally { setAdding(false) }
  }

  async function handleRemove(e: React.MouseEvent, ticker: string) {
    e.stopPropagation(); await removeFromWatchlist(ticker); await load()
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', borderRight: '1px solid #30363d' }}>
      <div style={{ padding: '8px', borderBottom: '1px solid #30363d', display: 'flex', gap: 6 }}>
        <input style={{ flex: 1, padding: '4px 8px', fontSize: 12, borderRadius: 4, backgroundColor: '#0d1117', border: '1px solid #30363d', color: '#e6edf3', outline: 'none' }} placeholder='Add ticker...' value={newTicker} onChange={(e) => setNewTicker(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && handleAdd()} />
        <button style={{ padding: '4px 10px', fontSize: 12, borderRadius: 4, fontWeight: 'bold', backgroundColor: '#209dd7', color: '#fff', border: 'none', cursor: 'pointer', opacity: adding ? 0.6 : 1 }} onClick={handleAdd} disabled={adding}>+</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {items.map((item) => {
          const live = prices[item.ticker]
          const price = live?.price ?? item.price
          const chg = live ? ((live.price - live.sessionOpen) / live.sessionOpen) * 100 : item.daily_change_pct
          const flash = flashState[item.ticker]
          const isSelected = selectedTicker === item.ticker
          return (
            <div key={item.ticker} onClick={() => onSelect(item.ticker)} className={flash ? 'flash-' + flash : undefined} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', cursor: 'pointer', borderBottom: '1px solid #21262d', backgroundColor: isSelected ? '#1f2937' : undefined, transition: 'background-color 0.15s' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 12, fontWeight: 'bold', color: '#ecad0a' }}>{item.ticker}</span>
                  <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#e6edf3' }}>{price != null ? '$' + price.toFixed(2) : '—'}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
                  <span style={{ fontSize: 11, color: chg != null ? (chg >= 0 ? '#3fb950' : '#f85149') : '#8b949e' }}>{chg != null ? (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%' : '—'}</span>
                  <button onClick={(e) => handleRemove(e, item.ticker)} style={{ fontSize: 11, color: '#f85149', background: 'none', border: 'none', cursor: 'pointer', opacity: 0.4, padding: 0 }} onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')} onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.4')}>&times;</button>
                </div>
              </div>
              <Sparkline history={live?.history ?? []} />
            </div>
          )
        })}
      </div>
    </div>
  )
}
