"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bot, CircleDollarSign, Plus, Radio, Send, Trash2 } from "lucide-react";
import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { Heatmap } from "@/components/Heatmap";
import { LineChartPanel } from "@/components/LineChartPanel";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { WatchlistPanel } from "@/components/WatchlistPanel";
import { addWatchlistTicker, deleteWatchlistTicker, executeTrade, fetchJson, getPortfolio, getWatchlist, sendChat } from "@/lib/api";
import { calculateLivePortfolio, mergePortfolioWithPrices } from "@/lib/calculations";
import { usePriceStream } from "@/lib/usePriceStream";
import type { ChatMessage, ChatResponse, MarketDataStatus, PortfolioResponse, PortfolioSnapshot, WatchlistItem } from "@/lib/types";

const initialPortfolio: PortfolioResponse = {
  cash_balance: 10000,
  positions: [],
  total_value: 10000,
  total_pnl: 0,
  total_pnl_pct: 0
};

const initialMarketData: MarketDataStatus = {
  source: "unknown",
  mode: "unknown",
  label: "Unknown"
};

function createMessageId(prefix: string) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function Home() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioResponse>(initialPortfolio);
  const [history, setHistory] = useState<PortfolioSnapshot[]>([]);
  const [selectedTicker, setSelectedTicker] = useState("AAPL");
  const [hydrated, setHydrated] = useState(false);
  const [marketData, setMarketData] = useState<MarketDataStatus>(initialMarketData);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "assistant-welcome",
      role: "assistant",
      content: "FinAlly online. Ask for portfolio analysis or a simulated trade.",
      created_at: new Date().toISOString()
    }
  ]);
  const [busy, setBusy] = useState(false);
  const { status, prices, seriesByTicker } = usePriceStream();

  useEffect(() => {
    setHydrated(true);
  }, []);

  const refreshPortfolio = useCallback(async () => {
    const nextPortfolio = await getPortfolio();
    setPortfolio(nextPortfolio);
  }, []);

  const refreshWatchlist = useCallback(async () => {
    const data = await getWatchlist();
    setWatchlist(data);
    if (!selectedTicker && data[0]) setSelectedTicker(data[0].ticker);
  }, [selectedTicker]);

  const refreshMarketData = useCallback(async () => {
    const data = await fetchJson<{ market_data: MarketDataStatus }>("/api/health");
    setMarketData(data.market_data);
  }, []);

  useEffect(() => {
    Promise.all([
      refreshWatchlist().catch(() => undefined),
      refreshPortfolio().catch(() => undefined),
      refreshMarketData().catch(() => undefined),
      fetchJson<{ history: PortfolioSnapshot[] }>("/api/portfolio/history")
        .then((data) => setHistory(data.history))
        .catch(() => undefined)
    ]);
  }, [refreshMarketData, refreshPortfolio, refreshWatchlist]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshMarketData().catch(() => undefined);
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [refreshMarketData]);

  useEffect(() => {
    if (!watchlist.length) return;
    const exists = watchlist.some((item) => item.ticker === selectedTicker);
    if (!exists) setSelectedTicker(watchlist[0].ticker);
  }, [selectedTicker, watchlist]);

  const positions = useMemo(() => mergePortfolioWithPrices(portfolio.positions, prices), [portfolio.positions, prices]);
  const livePortfolio = useMemo(() => calculateLivePortfolio(portfolio.cash_balance, positions), [portfolio.cash_balance, positions]);
  const liveWatchlist = useMemo(
    () =>
      watchlist.map((item) => {
        const quote = prices[item.ticker];
        return quote
          ? {
              ...item,
              price: quote.price,
              prev_price: quote.prev_price,
              session_open: quote.session_open,
              daily_change_pct: quote.session_open ? ((quote.price - quote.session_open) / quote.session_open) * 100 : 0
            }
          : item;
      }),
    [prices, watchlist]
  );

  const handleTrade = async (ticker: string, quantity: number, side: "buy" | "sell") => {
    setBusy(true);
    try {
      await executeTrade({ ticker, quantity, side });
      await Promise.all([refreshPortfolio(), refreshWatchlist()]);
    } finally {
      setBusy(false);
    }
  };

  const handleAddTicker = async (ticker: string) => {
    await addWatchlistTicker(ticker);
    await refreshWatchlist();
    setSelectedTicker(ticker.toUpperCase());
  };

  const handleDeleteTicker = async (ticker: string) => {
    await deleteWatchlistTicker(ticker);
    await refreshWatchlist();
  };

  const handleChat = async (content: string) => {
    const userMessage: ChatMessage = {
      id: createMessageId("user"),
      role: "user",
      content,
      created_at: new Date().toISOString()
    };
    setChatMessages((messages) => [...messages, userMessage]);
    setBusy(true);
    try {
      const response: ChatResponse = await sendChat(content);
      const resultActions = response.actions ?? {};
      setChatMessages((messages) => [
        ...messages,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          content: response.message,
          actions: {
            ...resultActions,
            trades_executed:
              resultActions.trades_executed ??
              response.results
                ?.filter((result) => result.type === "trade" && result.status === "executed")
                .map((result) => {
                  const trade = result.trade as { ticker?: string; side?: "buy" | "sell"; quantity?: number } | undefined;
                  return {
                    ticker: trade?.ticker ?? "",
                    side: trade?.side ?? "buy",
                    quantity: trade?.quantity ?? 0,
                    success: true
                  };
                }),
            trades_failed:
              resultActions.trades_failed ??
              response.errors
                ?.filter((error) => error.action === "trade")
                .map((error) => {
                  const request = error.request as { ticker?: string; side?: "buy" | "sell"; quantity?: number } | undefined;
                  return {
                    ticker: request?.ticker ?? "",
                    side: request?.side ?? "buy",
                    quantity: request?.quantity ?? 0,
                    error: typeof error.error === "string" ? error.error : JSON.stringify(error.error)
                  };
                })
          },
          created_at: new Date().toISOString()
        }
      ]);
      await Promise.all([refreshPortfolio(), refreshWatchlist()]);
    } catch (error) {
      setChatMessages((messages) => [
        ...messages,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          content: error instanceof Error ? error.message : "Chat request failed.",
          created_at: new Date().toISOString()
        }
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-terminal-bg text-terminal-text" data-testid="app-shell" data-hydrated={hydrated ? "true" : "false"}>
      <Header status={status} cash={portfolio.cash_balance} total={livePortfolio.totalValue} pnl={livePortfolio.totalPnl} marketData={marketData} />
      <div className="grid h-[calc(100vh-56px)] grid-cols-[minmax(260px,300px)_minmax(0,1fr)_minmax(300px,340px)] gap-2 p-2 max-xl:h-auto max-xl:grid-cols-1">
        <section className="grid min-h-0 min-w-0 grid-rows-[minmax(0,1fr)_auto] gap-2">
          <WatchlistPanel
            items={liveWatchlist}
            selectedTicker={selectedTicker}
            seriesByTicker={seriesByTicker}
            onSelect={setSelectedTicker}
            onAddTicker={handleAddTicker}
            onDeleteTicker={handleDeleteTicker}
          />
          <TradeBar selectedTicker={selectedTicker} busy={busy} onTrade={handleTrade} />
        </section>
        <section className="grid min-h-0 min-w-0 grid-rows-[minmax(340px,1.15fr)_minmax(220px,.85fr)] gap-2">
          <LineChartPanel
            title={`${selectedTicker} Live Tape`}
            subtitle="Session stream"
            color="#209dd7"
            data={seriesByTicker[selectedTicker] ?? []}
            emptyLabel="Waiting for streamed ticks"
          />
          <div className="grid min-h-0 min-w-0 grid-cols-[1.2fr_.8fr] gap-2 max-lg:grid-cols-1">
            <PositionsTable positions={positions} />
            <Heatmap positions={positions} totalValue={livePortfolio.totalValue} />
          </div>
        </section>
        <aside className="grid min-h-0 min-w-0 grid-rows-[240px_minmax(0,1fr)] gap-2">
          <LineChartPanel
            title="Portfolio P&L"
            subtitle="Server snapshots"
            color="#ecad0a"
            data={history.map((point) => ({ time: Math.floor(new Date(point.recorded_at).getTime() / 1000), value: point.total_value }))}
            emptyLabel="No portfolio snapshots yet"
          />
          <ChatPanel messages={chatMessages} busy={busy} onSend={handleChat} />
        </aside>
      </div>
      <div
        className="fixed bottom-2 left-2 z-20 max-w-[min(680px,calc(100vw-16px))] border border-terminal-border bg-terminal-panel2/95 px-3 py-1.5 font-mono text-[11px] leading-4 text-terminal-muted shadow-lg"
        data-testid="market-data-disclosure"
      >
        <span className="text-terminal-text">{marketData.label}</span>
        <span className="mx-2 text-terminal-border">|</span>
        <span>{marketData.description ?? "Market data source is loading."}</span>
      </div>
      <div className="hidden">
        <Bot />
        <CircleDollarSign />
        <Plus />
        <Radio />
        <Send />
        <Trash2 />
      </div>
    </main>
  );
}
