"use client";

import { FormEvent, useEffect, useState } from "react";
import { ArrowDownToLine, ArrowUpFromLine } from "lucide-react";
import { Panel } from "./Panel";

export function TradeBar({
  selectedTicker,
  busy,
  onTrade
}: {
  selectedTicker: string;
  busy: boolean;
  onTrade: (ticker: string, quantity: number, side: "buy" | "sell") => Promise<void>;
}) {
  const [ticker, setTicker] = useState(selectedTicker);
  const [quantity, setQuantity] = useState("1");

  useEffect(() => setTicker(selectedTicker), [selectedTicker]);

  async function submit(event: FormEvent, side: "buy" | "sell") {
    event.preventDefault();
    const parsed = Number(quantity);
    if (!ticker.trim() || !Number.isFinite(parsed) || parsed <= 0) return;
    await onTrade(ticker.trim().toUpperCase(), parsed, side);
  }

  return (
    <Panel title="Trade Bar" testId="trade-bar">
      <form className="grid grid-cols-2 gap-2 p-3 font-mono text-xs">
        <label className="col-span-1">
          <span className="mb-1 block uppercase text-terminal-muted">Ticker</span>
          <input
            value={ticker}
            onChange={(event) => setTicker(event.target.value.toUpperCase())}
            className="h-9 w-full border border-terminal-border bg-terminal-bg px-2 uppercase outline-none focus:border-ally-blue"
            aria-label="Trade ticker"
            data-testid="trade-symbol-input"
          />
        </label>
        <label>
          <span className="mb-1 block uppercase text-terminal-muted">Qty</span>
          <input
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            type="number"
            min="0"
            step="0.01"
            className="h-9 w-full border border-terminal-border bg-terminal-bg px-2 outline-none focus:border-ally-blue"
            aria-label="Trade quantity"
            data-testid="trade-quantity-input"
          />
        </label>
        <button
          disabled={busy}
          onClick={(event) => submit(event, "buy")}
          className="flex h-9 items-center justify-center gap-2 bg-ally-green/85 font-semibold text-white disabled:opacity-50"
          data-testid="buy-button"
        >
          <ArrowDownToLine size={15} /> Buy
        </button>
        <button
          disabled={busy}
          onClick={(event) => submit(event, "sell")}
          className="flex h-9 items-center justify-center gap-2 bg-ally-red/85 font-semibold text-white disabled:opacity-50"
          data-testid="sell-button"
        >
          <ArrowUpFromLine size={15} /> Sell
        </button>
      </form>
    </Panel>
  );
}
