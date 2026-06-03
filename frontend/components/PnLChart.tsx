'use client'
import { useEffect, useRef } from 'react'
import { usePortfolioStore } from '@/store/portfolioStore'

export default function PnLChart() {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)
  const seriesRef = useRef<any>(null)
  const history = usePortfolioStore((s) => s.history)

  useEffect(() => {
    if (!ref.current) return
    let chart: any = null

    import('lightweight-charts').then(({ createChart, ColorType, AreaSeries }) => {
      if (!ref.current) return
      chart = createChart(ref.current, {
        layout: { background: { type: ColorType.Solid, color: '#0d1117' }, textColor: '#8b949e' },
        grid: { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
        rightPriceScale: { borderColor: '#30363d' },
        timeScale: { borderColor: '#30363d' },
        width: ref.current.clientWidth,
        height: ref.current.clientHeight,
      })

      let series: any
      if (AreaSeries) {
        series = chart.addSeries(AreaSeries, {
          lineColor: '#ecad0a',
          topColor: 'rgba(236,173,10,0.15)',
          bottomColor: 'rgba(236,173,10,0)',
          lineWidth: 2,
        })
      } else {
        series = chart.addAreaSeries({
          lineColor: '#ecad0a',
          topColor: 'rgba(236,173,10,0.15)',
          bottomColor: 'rgba(236,173,10,0)',
          lineWidth: 2,
        })
      }

      chartRef.current = chart
      seriesRef.current = series

      const observer = new ResizeObserver(() => {
        if (ref.current && chart) chart.resize(ref.current.clientWidth, ref.current.clientHeight)
      })
      observer.observe(ref.current)
      ;(chart as any)._observer = observer
    })

    return () => {
      (chart as any)?._observer?.disconnect()
      chart?.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || history.length === 0) return
    const data = history.map((h, i) => ({ time: (i + 1) as any, value: h.total_value }))
    try {
      seriesRef.current.setData(data)
      chartRef.current?.timeScale().fitContent()
    } catch { /* ignore */ }
  }, [history])

  return <div ref={ref} style={{ width: '100%', height: '100%' }} />
}
