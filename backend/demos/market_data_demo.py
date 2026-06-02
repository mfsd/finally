#!/usr/bin/env python3
"""Market Data Demo — watch the FinAlly market simulator stream live prices.

This is a standalone terminal demo that wires together the *real* market-data
components (the same ones the FastAPI app uses):

    MarketDataProvider  ->  MarketPoller  ->  PriceCache  ->  (this renderer)

By default it runs the built-in GBM simulator (no API key, no network). If
MASSIVE_API_KEY is set in the environment it will instead poll the real Massive
API — same code path, the demo doesn't care which provider is selected.

Run it:

    cd backend
    uv run python demos/market_data_demo.py
    uv run python demos/market_data_demo.py --tickers AAPL,NVDA,TSLA,PYPL --duration 20

Press Ctrl-C to stop early.
"""
import argparse
import asyncio
import os
import sys
import time

# Make the backend package importable whether run from backend/ or repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market.cache import PriceCache
from market.factory import make_provider
from market.poller import MarketPoller

DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                   "NVDA", "META", "JPM", "V", "NFLX"]

# ANSI colors for uptick/downtick flashes.
GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"   # clear screen + home cursor


def _arrow(direction: str) -> str:
    return {"up": f"{GREEN}▲{RESET}", "down": f"{RED}▼{RESET}"}.get(direction, f"{DIM}={RESET}")


def _color_price(direction: str, price: float) -> str:
    color = {"up": GREEN, "down": RED}.get(direction, "")
    end = RESET if color else ""
    return f"{color}{price:>10.2f}{end}"


def render(cache: PriceCache, tickers: list[str], mode: str, elapsed: float) -> None:
    snap = cache.snapshot()
    lines = [
        f"{BOLD}FinAlly — Market Data Demo{RESET}   "
        f"source={BOLD}{mode}{RESET}   elapsed={elapsed:5.1f}s   "
        f"{DIM}(Ctrl-C to stop){RESET}",
        "",
        f"  {'TICKER':<8}{'PRICE':>10}  {'':<2}{'CHG%':>9}{'OPEN':>11}{'PREV':>11}",
        f"  {DIM}{'-' * 56}{RESET}",
    ]
    for t in tickers:
        q = snap.get(t)
        if q is None:
            lines.append(f"  {t:<8}{DIM}{'(awaiting price...)':>30}{RESET}")
            continue
        chg = (q.price - q.session_open) / q.session_open * 100 if q.session_open else 0.0
        chg_color = GREEN if chg > 0 else RED if chg < 0 else DIM
        lines.append(
            f"  {t:<8}{_color_price(q.direction, q.price)}  "
            f"{_arrow(q.direction)} {chg_color}{chg:>+7.2f}%{RESET}"
            f"{q.session_open:>11.2f}{q.prev_price:>11.2f}"
        )
    sys.stdout.write(CLEAR + "\n".join(lines) + "\n")
    sys.stdout.flush()


async def run(tickers: list[str], duration: float, fps: float) -> None:
    cache = PriceCache()
    provider, interval = make_provider()
    mode = "MASSIVE (real)" if os.environ.get("MASSIVE_API_KEY", "").strip() else "SIMULATOR (GBM)"

    # Seed synchronously so prices exist on the very first frame (sim mode).
    for t in tickers:
        seed = provider.seed_price(t)
        if seed is not None:
            cache.seed(t, seed)

    tracked = lambda: set(tickers)
    poller = MarketPoller(provider, cache, tracked_set=tracked, interval=interval)
    await poller.start()

    start = time.monotonic()
    try:
        while True:
            elapsed = time.monotonic() - start
            render(cache, tickers, mode, elapsed)
            if duration > 0 and elapsed >= duration:
                break
            await asyncio.sleep(1.0 / fps)
    except asyncio.CancelledError:
        pass
    finally:
        await poller.stop()

    # Final summary so non-interactive runs leave a record.
    snap = cache.snapshot()
    print(f"\n{BOLD}Demo complete.{RESET} Final prices after {time.monotonic() - start:.1f}s:")
    for t in tickers:
        q = snap.get(t)
        if q:
            chg = (q.price - q.session_open) / q.session_open * 100 if q.session_open else 0.0
            print(f"  {t:<8} {q.price:>10.2f}  ({chg:+.2f}% from open {q.session_open:.2f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="FinAlly market data terminal demo")
    parser.add_argument(
        "--tickers", default=",".join(DEFAULT_TICKERS),
        help="Comma-separated tickers to track (default: the 10 FinAlly defaults)",
    )
    parser.add_argument(
        "--duration", type=float, default=15.0,
        help="Seconds to run, then print a summary and exit (0 = run until Ctrl-C)",
    )
    parser.add_argument(
        "--fps", type=float, default=4.0,
        help="Screen refresh rate (frames per second, default 4)",
    )
    args = parser.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    try:
        asyncio.run(run(tickers, args.duration, args.fps))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
