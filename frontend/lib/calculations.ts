import type { LivePosition, Position, PriceEvent } from "./types";

export function mergePortfolioWithPrices(positions: Position[], prices: Record<string, PriceEvent>): LivePosition[] {
  return positions.map((position) => {
    const quote = prices[position.ticker];
    const currentPrice = quote?.price ?? position.current_price ?? position.avg_cost;
    const marketValue = currentPrice * position.quantity;
    const basis = position.avg_cost * position.quantity;
    const unrealizedPnl = marketValue - basis;
    const pnlPct = basis > 0 ? (unrealizedPnl / basis) * 100 : 0;
    const sessionOpen = quote?.session_open ?? position.session_open ?? currentPrice;
    const dailyChangePct = sessionOpen ? ((currentPrice - sessionOpen) / sessionOpen) * 100 : 0;

    return {
      ...position,
      current_price: currentPrice,
      market_value: marketValue,
      unrealized_pnl: unrealizedPnl,
      pnl_pct: pnlPct,
      session_open: sessionOpen,
      daily_change_pct: dailyChangePct
    };
  });
}

export function calculateLivePortfolio(cash: number, positions: LivePosition[]) {
  const positionsValue = positions.reduce((sum, position) => sum + position.market_value, 0);
  const totalValue = cash + positionsValue;
  const totalPnl = positions.reduce((sum, position) => sum + position.unrealized_pnl, 0);
  const invested = positions.reduce((sum, position) => sum + position.avg_cost * position.quantity, 0);
  return {
    totalValue,
    totalPnl,
    totalPnlPct: invested > 0 ? (totalPnl / invested) * 100 : 0
  };
}
