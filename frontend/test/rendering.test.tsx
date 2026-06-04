import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Header } from "@/components/Header";
import { PositionsTable } from "@/components/PositionsTable";

vi.mock("lightweight-charts", () => ({
  ColorType: { Solid: "solid" },
  createChart: () => ({
    addLineSeries: () => ({ setData: vi.fn() }),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() })
  })
}));

describe("workstation rendering", () => {
  it("renders header portfolio status", () => {
    render(
      <Header
        status="connected"
        cash={5000}
        total={12500}
        pnl={250}
        marketData={{ source: "massive", mode: "free_eod", label: "Massive EOD + sim", description: "End-of-day Massive closes with simulated intraday variation." }}
      />
    );

    expect(screen.getByText("FinAlly")).toBeInTheDocument();
    expect(screen.getByText("$12,500.00")).toBeInTheDocument();
    expect(screen.getByText("connected")).toBeInTheDocument();
    expect(screen.getByText("Massive EOD + sim")).toBeInTheDocument();
  });

  it("renders position metrics", () => {
    render(
      <PositionsTable
        positions={[
          {
            ticker: "AAPL",
            quantity: 3,
            avg_cost: 100,
            current_price: 120,
            market_value: 360,
            unrealized_pnl: 60,
            pnl_pct: 20,
            daily_change_pct: 1
          }
        ]}
      />
    );

    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("$360.00")).toBeInTheDocument();
    expect(screen.getByText("+20.00%")).toBeInTheDocument();
  });
});
