"use client";

import { useEffect, useRef } from "react";
import { ColorType, createChart, type IChartApi, type ISeriesApi, type LineData, type Time } from "lightweight-charts";
import { Panel } from "./Panel";
import type { ChartPoint } from "@/lib/types";

export function LineChartPanel({
  title,
  subtitle,
  data,
  color,
  emptyLabel
}: {
  title: string;
  subtitle: string;
  data: ChartPoint[];
  color: string;
  emptyLabel: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const chart = createChart(element, {
      width: element.clientWidth,
      height: element.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "#111827" },
        textColor: "#8b949e"
      },
      grid: {
        vertLines: { color: "rgba(45,55,72,.45)" },
        horzLines: { color: "rgba(45,55,72,.45)" }
      },
      rightPriceScale: { borderColor: "#2d3748" },
      timeScale: { borderColor: "#2d3748", timeVisible: true, secondsVisible: true },
      crosshair: { mode: 0 }
    });
    const series = chart.addLineSeries({ color, lineWidth: 2, priceLineVisible: false });
    chartRef.current = chart;
    seriesRef.current = series;

    const resize = new ResizeObserver(([entry]) => {
      chart.applyOptions({
        width: Math.floor(entry.contentRect.width),
        height: Math.floor(entry.contentRect.height)
      });
    });
    resize.observe(element);
    return () => {
      resize.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [color]);

  useEffect(() => {
    seriesRef.current?.setData(data.map((point) => ({ time: point.time as Time, value: point.value }) satisfies LineData));
    if (data.length > 1) chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <Panel
      title={title}
      action={<span className="font-mono text-[11px] uppercase text-terminal-muted">{subtitle}</span>}
      className="relative"
    >
      <div ref={containerRef} className="h-[calc(100%-36px)] min-h-[170px]" data-testid={`chart-${title}`} />
      {!data.length && (
        <div className="pointer-events-none absolute inset-9 flex items-center justify-center font-mono text-sm text-terminal-muted">
          {emptyLabel}
        </div>
      )}
    </Panel>
  );
}
