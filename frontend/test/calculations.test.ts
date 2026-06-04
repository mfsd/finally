import { describe, expect, it } from "vitest";
import { calculateLivePortfolio, mergePortfolioWithPrices } from "@/lib/calculations";

describe("portfolio calculations", () => {
  it("uses streamed prices to calculate live position P&L", () => {
    const positions = mergePortfolioWithPrices(
      [{ ticker: "AAPL", quantity: 10, avg_cost: 100 }],
      {
        AAPL: {
          ticker: "AAPL",
          price: 112,
          prev_price: 110,
          session_open: 105,
          ts: 1000,
          direction: "up"
        }
      }
    );

    expect(positions[0].market_value).toBe(1120);
    expect(positions[0].unrealized_pnl).toBe(120);
    expect(positions[0].pnl_pct).toBe(12);
    expect(positions[0].daily_change_pct).toBeCloseTo(6.666, 2);
  });

  it("combines cash and positions for live portfolio value", () => {
    const positions = mergePortfolioWithPrices([{ ticker: "MSFT", quantity: 2, avg_cost: 50, current_price: 75 }], {});
    const summary = calculateLivePortfolio(900, positions);

    expect(summary.totalValue).toBe(1050);
    expect(summary.totalPnl).toBe(50);
    expect(summary.totalPnlPct).toBe(50);
  });
});
