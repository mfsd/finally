# Market Data Interface — Unified Price Provider

> The single abstraction FinAlly's backend uses to obtain stock prices. One interface, two
> implementations: a **simulator** (default) and a **Massive** REST client (when
> `MASSIVE_API_KEY` is set). All downstream code — the shared price cache, SSE streaming,
> portfolio math, the frontend — is agnostic to which is running.
>
> See also: [MASSIVE_API.md](./MASSIVE_API.md) (real-data source) and
> [MARKET_SIMULATOR.md](./MARKET_SIMULATOR.md) (default source).

## 1. Goals

1. **One seam.** Downstream code never branches on data source. It depends only on the
   abstract `MarketDataProvider` and reads from the shared `PriceCache`.
2. **Source selected by environment.** `MASSIVE_API_KEY` present and non-empty → Massive;
   otherwise → simulator (PLAN §5).
3. **Push model.** A single background task drives updates into the cache at a regular
   cadence. SSE reads the cache; it never calls a provider directly.
4. **Dynamic tracked set.** The provider tracks the **union of the watchlist and held
   positions** (PLAN §6), which changes at runtime as the user trades and edits the watchlist.
5. **Immediate availability in sim mode; tolerant in Massive mode.** Simulator assigns a seed
   price synchronously on add. Massive may lag one poll; that race is surfaced as
   "price not yet available."

## 2. The Data Model

A single immutable record flows from provider → cache → SSE.

```python
# backend/market/types.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Quote:
    """A single price observation for one ticker."""
    ticker: str
    price: float          # latest price
    prev_price: float     # previous tick's price (for up/down flash direction)
    session_open: float   # first price seen this backend session (daily-change baseline)
    ts: float             # epoch seconds of the observation

    @property
    def direction(self) -> str:
        if self.price > self.prev_price:
            return "up"
        if self.price < self.prev_price:
            return "down"
        return "flat"
```

`session_open`, `prev_price`, and `direction` are concerns of the **cache**, not the
provider. A provider only needs to answer "what is the latest price for these tickers?"; the
cache layers on prev/open/direction bookkeeping. This keeps both providers tiny.

## 3. The Abstract Interface

```python
# backend/market/base.py
from abc import ABC, abstractmethod
from collections.abc import Iterable

class MarketDataProvider(ABC):
    """Source of latest prices for a dynamic set of tickers."""

    @abstractmethod
    async def get_prices(self, tickers: Iterable[str]) -> dict[str, float]:
        """Latest price per ticker. Tickers with no available price are omitted
        from the returned dict (caller treats a missing key as 'no price yet')."""

    @abstractmethod
    def seed_price(self, ticker: str) -> float | None:
        """Synchronously return an immediately-usable price for a newly added ticker,
        or None if one cannot be produced without I/O.

        - Simulator: returns a deterministic hash-derived seed (never None).
        - Massive:   returns None (price only known after the next poll)."""

    @abstractmethod
    async def validate_ticker(self, ticker: str) -> bool:
        """Whether the symbol is tradeable/known.
        - Simulator: True for any well-formed symbol.
        - Massive:   True only if the snapshot endpoint resolves the symbol."""

    async def start(self) -> None:
        """Optional one-time setup (e.g. open an httpx client). Default: no-op."""

    async def aclose(self) -> None:
        """Optional teardown. Default: no-op."""
```

**Why `get_prices` is pull-based (provider) but the system is push-based (cache).** A single
background poller (§5) calls `get_prices` on a cadence and writes results into the cache. The
simulator could in principle push continuously, but modeling both providers as "give me the
latest snapshot of these tickers when asked" keeps the interface uniform and the poller
identical for both. The simulator simply advances its internal random walk between calls (see
MARKET_SIMULATOR.md §4).

## 4. The Shared Price Cache

The cache is the single source of truth read by SSE and portfolio math. It owns
prev-price/session-open/direction bookkeeping so providers stay dumb.

```python
# backend/market/cache.py
import time
from threading import RLock
from .types import Quote

class PriceCache:
    def __init__(self) -> None:
        self._quotes: dict[str, Quote] = {}
        self._lock = RLock()

    def snapshot(self) -> dict[str, Quote]:
        with self._lock:
            return dict(self._quotes)

    def get(self, ticker: str) -> Quote | None:
        with self._lock:
            return self._quotes.get(ticker)

    def update(self, ticker: str, price: float, ts: float | None = None) -> Quote:
        """Apply a new price, deriving prev_price and preserving session_open."""
        ts = ts if ts is not None else time.time()
        with self._lock:
            existing = self._quotes.get(ticker)
            if existing is None:
                # First time we see this ticker this session: open == price.
                q = Quote(ticker=ticker, price=price, prev_price=price,
                          session_open=price, ts=ts)
            else:
                q = Quote(ticker=ticker, price=price, prev_price=existing.price,
                          session_open=existing.session_open, ts=ts)
            self._quotes[ticker] = q
            return q

    def seed(self, ticker: str, price: float) -> Quote:
        """Insert a ticker that has no prior entry (used by synchronous sim seeding).
        No-op if already present."""
        with self._lock:
            if ticker not in self._quotes:
                return self.update(ticker, price)
            return self._quotes[ticker]
```

Notes:
- **`session_open` is set on first insert and never overwritten** until the backend restarts
  (PLAN §6). It is *not* persisted.
- The cache is in-memory and process-local; this matches PLAN's single-container design and
  is forward-compatible with multi-user (key by `(user_id, ticker)` later).
- `RLock` guards against the poller task and SSE readers touching the dict concurrently.

## 5. The Poller (single background task)

One asyncio task, identical for both providers, computes the tracked set, asks the provider
for prices, and writes the cache. It runs every `POLL_INTERVAL` seconds.

```python
# backend/market/poller.py
import asyncio
from collections.abc import Callable
from .base import MarketDataProvider
from .cache import PriceCache

class MarketPoller:
    def __init__(
        self,
        provider: MarketDataProvider,
        cache: PriceCache,
        tracked_set: Callable[[], set[str]],   # union of watchlist + held positions
        interval: float,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._tracked_set = tracked_set
        self._interval = interval
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        await self._provider.start()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        await self._provider.aclose()

    async def _run(self) -> None:
        while True:
            try:
                tickers = self._tracked_set()
                if tickers:
                    prices = await self._provider.get_prices(tickers)
                    for ticker, price in prices.items():
                        self._cache.update(ticker, price)
            except Exception:
                # Never let a transient provider/network error kill the loop.
                # (log here)
                pass
            await asyncio.sleep(self._interval)
```

- `tracked_set()` is supplied by the app (it queries the watchlist + positions tables). The
  poller does not know about the database.
- The cadence differs by source but the loop is the same:
  - **Simulator:** `~0.5s` (PLAN §6 — updates ~500ms).
  - **Massive free tier:** `15s` (respects ~5 req/min, one request per poll — MASSIVE_API §3).
  - **Massive paid:** `2–15s`, configurable.
- SSE streams to clients on its **own** ~500ms cadence reading `cache.snapshot()`, decoupled
  from the poll interval. In Massive mode the cache simply holds steady between polls.

## 6. Selection / Factory

```python
# backend/market/factory.py
import os
from .base import MarketDataProvider
from .simulator import SimulatorMarketData
from .massive import MassiveMarketData

def make_provider() -> tuple[MarketDataProvider, float]:
    """Return (provider, poll_interval_seconds) based on environment."""
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if key:
        interval = float(os.environ.get("MASSIVE_POLL_INTERVAL", "15"))
        return MassiveMarketData(api_key=key), interval
    return SimulatorMarketData(), 0.5
```

Wiring at app startup (FastAPI lifespan):

```python
# backend/app.py  (sketch)
from contextlib import asynccontextmanager
from .market.cache import PriceCache
from .market.poller import MarketPoller
from .market.factory import make_provider

@asynccontextmanager
async def lifespan(app):
    cache = PriceCache()
    provider, interval = make_provider()
    poller = MarketPoller(provider, cache, tracked_set=app.state.tracked_set, interval=interval)

    # Synchronously seed current tracked set so prices exist before first poll.
    for ticker in app.state.tracked_set():
        seed = provider.seed_price(ticker)
        if seed is not None:
            cache.seed(ticker, seed)

    app.state.price_cache = cache
    await poller.start()
    try:
        yield
    finally:
        await poller.stop()
```

## 7. Massive Provider (adapter over MASSIVE_API.md)

```python
# backend/market/massive.py
import httpx
from collections.abc import Iterable
from .base import MarketDataProvider

BASE_URL = "https://api.massive.com"

class MassiveMarketData(MarketDataProvider):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=10.0,
        )

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()

    async def get_prices(self, tickers: Iterable[str]) -> dict[str, float]:
        symbols = ",".join(sorted(set(tickers)))
        if not symbols:
            return {}
        resp = await self._client.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"tickers": symbols},
        )
        resp.raise_for_status()
        out: dict[str, float] = {}
        for row in resp.json().get("tickers", []):
            sym = row.get("ticker")
            price = _resolve_price(row)           # lastTrade.p -> min.c -> day.c
            if sym and price is not None:
                out[sym] = price
        return out

    def seed_price(self, ticker: str) -> float | None:
        return None   # price only known after a poll

    async def validate_ticker(self, ticker: str) -> bool:
        prices = await self.get_prices([ticker])
        return ticker in prices


def _resolve_price(row: dict) -> float | None:
    for parent, child in (("lastTrade", "p"), ("min", "c"), ("day", "c")):
        val = (row.get(parent) or {}).get(child)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    return None
```

(Field/timestamp normalization and tolerant-parsing rationale live in MASSIVE_API.md §5/§8.)

## 8. Simulator Provider (adapter over MARKET_SIMULATOR.md)

```python
# backend/market/simulator.py  (interface surface only; engine in MARKET_SIMULATOR.md)
from collections.abc import Iterable
from .base import MarketDataProvider
from .sim_engine import SimEngine   # GBM walk + deterministic seeding

class SimulatorMarketData(MarketDataProvider):
    def __init__(self) -> None:
        self._engine = SimEngine()

    async def get_prices(self, tickers: Iterable[str]) -> dict[str, float]:
        # Advance the walk and return the latest price for each tracked ticker.
        return self._engine.step(set(tickers))

    def seed_price(self, ticker: str) -> float | None:
        # Deterministic hash-derived seed, assigned synchronously (never None).
        return self._engine.ensure_seeded(ticker)

    async def validate_ticker(self, ticker: str) -> bool:
        return ticker.isalpha() and 1 <= len(ticker) <= 6   # any well-formed symbol
```

## 9. Behavioral Contract (must hold for both implementations)

| Concern | Simulator | Massive |
|---|---|---|
| `validate_ticker` | True for any well-formed symbol | True only if snapshot resolves it |
| `seed_price` | Deterministic seed, synchronous, never None | None (await first poll) |
| First trade on a new ticker | Always priced immediately | "price not yet available" until first poll |
| Update cadence | ~0.5s | 15s free / 2–15s paid |
| `get_prices` missing key | Only if ticker not seeded (shouldn't happen) | Symbol unknown or not yet returned |
| Determinism across restarts | Same seed → same start price | Real market data |

These guarantees are exactly what PLAN §6 and §8 require (synchronous seeding in sim mode,
"price not yet available" race in Massive mode, union tracked set, session-open baseline).

## 10. Testing Hooks (PLAN §12)

- Both providers are unit-tested against the **same** suite asserting the §9 contract.
- `MarketPoller` is tested with a fake provider returning scripted prices, asserting cache
  prev/open/direction bookkeeping.
- `PriceCache.update` is tested for: first-insert sets `session_open == price`; subsequent
  updates preserve `session_open` and roll `prev_price`; direction computed correctly.
- Massive `_resolve_price` is tested against captured JSON fixtures (lastTrade present /
  absent / only day bar) to lock in tolerant parsing.
