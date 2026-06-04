"use client";

import { useEffect, useRef } from "react";
import { ColorType, createChart, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";
import type { ChartPoint } from "@/lib/types";

export function Sparkline({ data, positive }: { data: ChartPoint[]; positive: boolean }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      width: 82,
      height: 34,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "transparent" },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      leftPriceScale: { visible: false },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      handleScale: false,
      handleScroll: false,
      crosshair: { mode: 0 }
    });
    const series = chart.addLineSeries({
      color: positive ? "#22c55e" : "#ef4444",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false
    });
    chartRef.current = chart;
    seriesRef.current = series;
    return () => chart.remove();
  }, [positive]);

  useEffect(() => {
    seriesRef.current?.setData(data.map((point) => ({ time: point.time as Time, value: point.value })));
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return <div ref={ref} className="h-[34px] w-[82px]" aria-label="sparkline" />;
}
