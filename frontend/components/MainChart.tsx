'use client'
import { useEffect, useRef } from 'react'
import { usePriceStore } from '@/store/priceStore'

export default function MainChart({ ticker }: { ticker: string | null }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)
  const seriesRef = useRef<any>(null)
  const prices = usePriceStore((s) => s.prices)
  const tickerData = ticker ? prices[ticker] : null

  useEffect(() => {
    if (!ref.current) return
    let chart: any = null

    import('lightweight-charts').then(({ createChart, ColorType, AreaSeries }) => {
      if (!ref.current) return
      chart = createChart(ref.current, {
        layout: { background: { type: ColorType.Solid, color: '#0d1117' }, textColor: '#8b949e' },
        grid: { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
        rightPriceScale: { borderColor: '#30363d' },
        timeScale: { borderColor: '#30363d', timeVisible: true },
        crosshair: { mode: 1 },
        width: ref.current.clientWidth,
        height: ref.current.clientHeight,
      })

      let series: any
      if (AreaSeries) {
        series = chart.addSeries(AreaSeries, {
          lineColor: '#209dd7',
          topColor: 'rgba(32,157,215,0.15)',
          bottomColor: 'rgba(32,157,215,0)',
          lineWidth: 2,
        })
      } else {
        series = (chart as any).addAreaSeries({
          lineColor: '#209dd7',
          topColor: 'rgba(32,157,215,0.15)',
          bottomColor: 'rgba(32,157,215,0)',
          lineWidth: 2,
        })
      }

      chartRef.current = chart
      seriesRef.current = series

      const observer = new ResizeObserver(() => {
        if (ref.current && chart) {
          chart.resize(ref.current.clientWidth, ref.current.clientHeight)
        }
      })
      observer.observe(ref.current)
      ;(chart as any)._observer = observer
    })

    return () => {
      (chart as any)?._observer?.disconnect()
      chart?.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || !tickerData || tickerData.history.length === 0) return
    const data = tickerData.history.map((price, i) => ({ time: (i + 1) as any, value: price }))
    try {
      seriesRef.current.setData(data)
      chartRef.current?.timeScale().fitContent()
    } catch { /* ignore */ }
  }, [tickerData?.history?.length, ticker])

  if (!ticker) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#8b949e', fontSize: 13 }}>
        Select a ticker to view chart
      </div>
    )
  }

  const price = tickerData?.price
  const sessionOpen = tickerData?.sessionOpen
  const dailyChg = price && sessionOpen ? ((price - sessionOpen) / sessionOpen) * 100 : null
  const chgColor = dailyChg != null ? (dailyChg >= 0 ? '#3fb950' : '#f85149') : '#8b949e'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, padding: '8px 16px', borderBottom: '1px solid #30363d', flexShrink: 0 }}>
        <span style={{ fontSize: 16, fontWeight: 'bold', color: '#ecad0a' }}>{ticker}</span>
        <span style={{ fontSize: 24, fontWeight: 'bold', color: '#e6edf3', fontFamily: 'monospace' }}>
          {price != null ? `$${price.toFixed(2)}` : '․'}
        </span>
        {dailyChg != null && (
          <span style={{ fontSize: 13, fontWeight: 600, color: chgColor }}>
            {dailyChg >= 0 ? '+' : ''}{dailyChg.toFixed(2)}%
          </span>
        )}
      </div>
      <div ref={ref} style={{ flex: 1 }} />
    </div>
  )
}
