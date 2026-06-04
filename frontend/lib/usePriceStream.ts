"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ChartPoint, ConnectionStatus, PriceEvent } from "./types";

const STALE_TIMEOUT_MS = 31000;
const MAX_POINTS = 240;

export function usePriceStream() {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [prices, setPrices] = useState<Record<string, PriceEvent>>({});
  const [seriesByTicker, setSeriesByTicker] = useState<Record<string, ChartPoint[]>>({});
  const lastActivity = useRef(Date.now());

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const source = new EventSource("/api/stream/prices");

    source.onopen = () => {
      lastActivity.current = Date.now();
      setStatus("connected");
    };

    source.addEventListener("prices", (event) => {
      lastActivity.current = Date.now();
      const updates = JSON.parse((event as MessageEvent).data) as PriceEvent[];
      setPrices((current) => {
        const next = { ...current };
        updates.forEach((quote) => {
          next[quote.ticker] = quote;
        });
        return next;
      });
      setSeriesByTicker((current) => {
        const next = { ...current };
        updates.forEach((quote) => {
          const point = { time: Math.floor(quote.ts), value: quote.price };
          const series = [...(next[quote.ticker] ?? []), point].slice(-MAX_POINTS);
          next[quote.ticker] = series;
        });
        return next;
      });
    });

    source.onerror = () => {
      setStatus(source.readyState === EventSource.CONNECTING ? "reconnecting" : "disconnected");
    };

    const staleTimer = window.setInterval(() => {
      if (Date.now() - lastActivity.current > STALE_TIMEOUT_MS) {
        setStatus("disconnected");
      }
    }, 5000);

    return () => {
      window.clearInterval(staleTimer);
      source.close();
    };
  }, []);

  return useMemo(() => ({ status, prices, seriesByTicker }), [prices, seriesByTicker, status]);
}
