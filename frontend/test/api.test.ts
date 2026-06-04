import { afterEach, describe, expect, it, vi } from "vitest";
import { addWatchlistTicker, executeTrade, fetchJson, sendChat } from "@/lib/api";

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends trade requests to the same-origin portfolio endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ success: true })
    } as Response);

    await executeTrade({ ticker: "aapl", quantity: 1.5, side: "buy" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/portfolio/trade",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ ticker: "AAPL", quantity: 1.5, side: "buy" })
      })
    );
  });

  it("normalizes ticker casing for watchlist adds", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ ticker: "NVDA" })
    } as Response);

    await addWatchlistTicker("nvda");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/watchlist",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ ticker: "NVDA" }) })
    );
  });

  it("throws backend detail messages on failed responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({ detail: "insufficient cash" })
    } as Response);

    await expect(fetchJson("/api/portfolio/trade")).rejects.toThrow("insufficient cash");
  });

  it("posts chat messages to /api/chat", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ message: "ok" })
    } as Response);

    await sendChat("rebalance");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ message: "rebalance" }) })
    );
  });
});
