import type { ChatResponse, PortfolioResponse, PriceEvent, TradeRequest, WatchlistItem } from "./types";

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown; error?: unknown };
      const backendDetail = body.detail ?? body.error;
      detail = typeof backendDetail === "string" ? backendDetail : backendDetail ? JSON.stringify(backendDetail) : detail;
    } catch {
      // Keep status text fallback.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

function flattenQuote(item: WatchlistItem): WatchlistItem {
  const quote = item.quote;
  if (!quote) return item;
  return {
    ...item,
    price: quote.price,
    prev_price: quote.prev_price,
    session_open: quote.session_open,
    daily_change_pct: quote.session_open ? ((quote.price - quote.session_open) / quote.session_open) * 100 : 0
  };
}

function normalizePosition(position: PortfolioResponse["positions"][number]) {
  const quote = position.quote as PriceEvent | null | undefined;
  const currentPrice = quote?.price ?? position.current_price ?? position.avg_cost;
  const marketValue = position.market_value ?? currentPrice * position.quantity;
  const basis = position.avg_cost * position.quantity;
  const unrealizedPnl = position.unrealized_pnl ?? position.unrealized_pl ?? marketValue - basis;
  const pnlPct = position.pnl_pct ?? (position.unrealized_pl_pct != null ? position.unrealized_pl_pct * 100 : basis ? (unrealizedPnl / basis) * 100 : 0);
  return {
    ...position,
    current_price: currentPrice,
    market_value: marketValue,
    unrealized_pnl: unrealizedPnl,
    pnl_pct: pnlPct,
    session_open: quote?.session_open ?? position.session_open ?? currentPrice
  };
}

export async function getPortfolio() {
  const data = await fetchJson<{ portfolio: PortfolioResponse }>("/api/portfolio");
  const portfolio = data.portfolio;
  const totalPnl = portfolio.total_pnl ?? portfolio.unrealized_pl ?? 0;
  return {
    ...portfolio,
    positions: portfolio.positions.map(normalizePosition),
    total_pnl: totalPnl,
    total_pnl_pct: portfolio.total_pnl_pct ?? (portfolio.unrealized_pl_pct != null ? portfolio.unrealized_pl_pct * 100 : 0)
  };
}

export async function getWatchlist() {
  const data = await fetchJson<{ watchlist: WatchlistItem[] }>("/api/watchlist");
  return data.watchlist.map(flattenQuote);
}

export function executeTrade(trade: TradeRequest) {
  return fetchJson("/api/portfolio/trade", {
    method: "POST",
    body: JSON.stringify({
      ticker: trade.ticker.toUpperCase(),
      quantity: trade.quantity,
      side: trade.side
    })
  });
}

export function addWatchlistTicker(ticker: string) {
  return fetchJson("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker: ticker.toUpperCase() })
  });
}

export function deleteWatchlistTicker(ticker: string) {
  return fetchJson(`/api/watchlist/${encodeURIComponent(ticker.toUpperCase())}`, {
    method: "DELETE"
  });
}

export function sendChat(message: string) {
  return fetchJson<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message })
  });
}
