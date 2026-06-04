"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { formatCurrency, formatPercent, pnlClass } from "@/lib/format";
import type { ChartPoint, WatchlistItem } from "@/lib/types";
import { Panel } from "./Panel";
import { Sparkline } from "./Sparkline";

export function WatchlistPanel({
  items,
  selectedTicker,
  seriesByTicker,
  onSelect,
  onAddTicker,
  onDeleteTicker
}: {
  items: WatchlistItem[];
  selectedTicker: string;
  seriesByTicker: Record<string, ChartPoint[]>;
  onSelect: (ticker: string) => void;
  onAddTicker: (ticker: string) => Promise<void>;
  onDeleteTicker: (ticker: string) => Promise<void>;
}) {
  const [ticker, setTicker] = useState("");
  const [flash, setFlash] = useState<Record<string, "up" | "down">>({});
  const prevPrices = useRef<Record<string, number>>({});

  useEffect(() => {
    items.forEach((item) => {
      if (item.price == null) return;
      const price = item.price;
      const previous = prevPrices.current[item.ticker];
      if (previous !== undefined && previous !== price) {
        setFlash((current) => ({ ...current, [item.ticker]: price > previous ? "up" : "down" }));
        window.setTimeout(() => {
          setFlash((current) => {
            const next = { ...current };
            delete next[item.ticker];
            return next;
          });
        }, 540);
      }
      prevPrices.current[item.ticker] = price;
    });
  }, [items]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!ticker.trim()) return;
    await onAddTicker(ticker.trim());
    setTicker("");
  }

  return (
    <Panel
      title="Watchlist"
      testId="watchlist"
      action={
        <form onSubmit={submit} className="flex items-center gap-1">
          <input
            value={ticker}
            onChange={(event) => setTicker(event.target.value.toUpperCase())}
            className="h-6 w-20 border border-terminal-border bg-terminal-bg px-2 font-mono text-xs uppercase outline-none focus:border-ally-blue"
            placeholder="TICKER"
            aria-label="Ticker"
            data-testid="watchlist-symbol-input"
          />
          <button
            className="flex h-6 w-6 items-center justify-center bg-ally-purple text-white"
            aria-label="Add ticker"
            data-testid="add-watchlist-button"
          >
            <Plus size={14} />
          </button>
        </form>
      }
    >
      <div className="terminal-scrollbar h-[calc(100%-36px)] overflow-auto">
        <div className="grid grid-cols-[70px_86px_70px_1fr_28px] border-b border-terminal-border px-2 py-1 font-mono text-[11px] uppercase text-terminal-muted">
          <span>Symbol</span>
          <span className="text-right">Last</span>
          <span className="text-right">Chg%</span>
          <span className="text-center">Tape</span>
          <span />
        </div>
        {items.map((item) => {
          const change = item.daily_change_pct ?? 0;
          const flashClass = flash[item.ticker] === "up" ? "flash-up" : flash[item.ticker] === "down" ? "flash-down" : "";
          return (
            <button
              key={item.ticker}
              type="button"
              onClick={() => onSelect(item.ticker)}
              data-testid={`watchlist-row-${item.ticker}`}
              className={`grid w-full grid-cols-[70px_86px_70px_1fr_28px] items-center border-b border-terminal-border/70 px-2 py-1.5 text-left font-mono text-xs hover:bg-white/5 ${
                selectedTicker === item.ticker ? "bg-ally-blue/10 text-white" : ""
              } ${flashClass}`}
            >
              <span className="font-semibold text-white">{item.ticker}</span>
              <span className="text-right">{formatCurrency(item.price)}</span>
              <span className={`text-right ${pnlClass(change)}`}>{formatPercent(change)}</span>
              <span className="flex justify-center">
                <Sparkline data={seriesByTicker[item.ticker] ?? []} positive={change >= 0} />
              </span>
              <span
                role="button"
                tabIndex={0}
                onClick={(event) => {
                  event.stopPropagation();
                  onDeleteTicker(item.ticker);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.stopPropagation();
                    onDeleteTicker(item.ticker);
                  }
                }}
                className="flex h-6 w-6 items-center justify-center text-terminal-muted hover:text-ally-red"
                aria-label={`Remove ${item.ticker}`}
                data-testid={`remove-${item.ticker}`}
              >
                <Trash2 size={13} />
              </span>
            </button>
          );
        })}
      </div>
    </Panel>
  );
}
