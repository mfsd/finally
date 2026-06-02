# Market Data Backend — Detailed Design

> A single, self-contained implementation guide for FinAlly's market-data layer: the
> **unified provider API**, the **GBM simulator** (default), and the **Massive REST client**
> (optional). It covers every piece needed to stream live prices — data model, shared cache,
> background poller, SSE endpoint, and FastAPI wiring — with working code snippets and
> examples.
>
> Scope maps to PLAN.md §6 (Market Data), §8 (API endpoints), and §12 (testing). This document
> can be read on its own; companion deep-dives live in
> [`MARKET_INTERFACE.md`](./MARKET_INTERFACE.md), [`MARKET_SIMULATOR.md`](./MARKET_SIMULATOR.md),
> and [`MASSIVE_API.md`](./MASSIVE_API.md).

---

## 1. Architecture at a Glance

```
                          ┌──────────────────────────────────────────────┐
                          │                FastAPI app                    │
                          │                                              │
  watchlist ∪ positions   │   tracked_set()  ─────────────┐               │
  (SQLite tables)  ───────┼─────────────────────────────► │               │
                          │                               ▼               │
                          │   ┌─────────────┐      ┌──────────────┐        │
   MASSIVE_API_KEY? ──────┼──►│  factory    │─────►│ MarketPoller │        │
                          │   └─────────────┘      │ (1 bg task)  │        │
                          │        selects         └──────┬───────┘        │
                          │   ┌──────────────────┐        │ get_prices()   │
                          │   │ MarketDataProvider│◄───────┘                │
                          │   │  ├ Simulator      │        │ writes         │
                          │   │  └ Massive        │        ▼                │
                          │   └──────────────────┘   ┌───────────┐         │
                          │                          │ PriceCache│         │
                          │                          └─────┬─────┘         │
                          │   GET /api/stream/prices       │ snapshot()    │
                          │   (SSE, ~500ms + heartbeat) ◄──┘               │
                          └──────────────────────────────────────────────┘
                                          │ EventSource
                                          ▼
                                      Frontend
```

**Key invariants (PLAN §6):**

1. **One seam.** All downstream code (SSE, portfolio math, frontend) depends only on the
   abstract `MarketDataProvider` and reads from the shared `PriceCache`. It never branches on
   the data source.
2. **One writer, many readers.** A single background `MarketPoller` task writes to the cache;
   SSE connections only read snapshots.
3. **Dynamic tracked set.** The system tracks the **union of the watchlist and held
   positions**, recomputed each poll, so a held-but-unwatched ticker keeps streaming.
4. **Source by environment.** `MASSIVE_API_KEY` present and non-empty → Massive; otherwise →
   simulator.
5. **Immediate availability in sim mode.** The simulator assigns a deterministic seed price
   synchronously on add (no empty-state gap). Massive may lag one poll → "price not yet
   available."

### Module layout

```
backend/market/
├── types.py        # Quote dataclass (the record that flows provider → cache → SSE)
├── base.py         # MarketDataProvider ABC (the unified API)
├── cache.py        # PriceCache: prev-price / session-open / direction bookkeeping
├── seeds.py        # SEED_PRICES table + deterministic seed_price()
├── sim_engine.py   # SimEngine: GBM walk, correlation, random events
├── simulator.py    # SimulatorMarketData adapter (MarketDataProvider)
├── massive.py      # MassiveMarketData adapter (Polygon-compatible REST)
├── poller.py       # MarketPoller: single background loop
├── factory.py      # env-based provider selection
└── stream.py       # SSE event formatting for /api/stream/prices
```

---

## 2. Data Model

A single immutable record flows from provider → cache → SSE. Providers answer only "what is
the latest price?"; the cache layers on previous-price, session-open, and direction so the
providers stay tiny.

```python
# backend/market/types.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Quote:
    """A single price observation for one ticker."""
    ticker: str
    price: float          # latest price
    prev_price: float     # previous tick's price (drives up/down flash direction)
    session_open: float   # first price seen this backend session (daily-change baseline)
    ts: float             # epoch seconds of the observation

    @property
    def direction(self) -> str:
        if self.price > self.prev_price:
            return "up"
        if self.price < self.prev_price:
            return "down"
        return "flat"

    def to_event(self) -> dict:
        """Shape pushed over SSE. The frontend computes daily change % as
        (price - session_open) / session_open."""
        return {
            "ticker": self.ticker,
            "price": round(self.price, 4),
            "prev_price": round(self.prev_price, 4),
            "session_open": round(self.session_open, 4),
            "ts": self.ts,
            "direction": self.direction,
        }
```

> **Why `session_open`, not previous-close?** There is no real previous-close in the system.
> The session-open (first price recorded after the backend starts, or after a ticker first
> enters the cache) is the deliberate, simple substitute for the watchlist/positions/header
> "daily change %". It is **not persisted** and resets on backend restart (PLAN §6).

---

## 3. The Unified Provider API

The single abstraction the rest of the backend depends on. Two implementations conform to it:
`SimulatorMarketData` and `MassiveMarketData`.

```python
# backend/market/base.py
from abc import ABC, abstractmethod
from collections.abc import Iterable

class MarketDataProvider(ABC):
    """Source of latest prices for a dynamic set of tickers."""

    @abstractmethod
    async def get_prices(self, tickers: Iterable[str]) -> dict[str, float]:
        """Latest price per ticker. Tickers with no available price are OMITTED
        from the returned dict (a missing key means 'no price yet')."""

    @abstractmethod
    def seed_price(self, ticker: str) -> float | None:
        """Synchronously return an immediately-usable price for a newly added
        ticker, or None if one cannot be produced without I/O.
          - Simulator: deterministic hash-derived seed (never None).
          - Massive:   None (price only known after the next poll)."""

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

**Behavioral contract** — both implementations MUST satisfy this (it is the thing the test
suite asserts):

| Concern | Simulator | Massive |
|---|---|---|
| `validate_ticker` | True for any well-formed symbol | True only if snapshot resolves it |
| `seed_price` | Deterministic, synchronous, never None | `None` (await first poll) |
| First trade on a new ticker | Always priced immediately | "price not yet available" until first poll |
| Update cadence | ~0.5s | 15s free tier / 2–15s paid |
| `get_prices` omits a key | Only if not seeded (shouldn't happen) | Symbol unknown or not yet returned |
| Determinism across restarts | Same seed → same start price | Real (delayed) market data |

> **Pull provider, push system.** `get_prices` is pull-based, but the system is push-based: a
> single `MarketPoller` (§6) calls `get_prices` on a cadence and writes the cache. Modeling
> both sources as "give me the latest snapshot of these tickers when asked" keeps the poller
> identical for both. The simulator simply advances its internal random walk between calls.

---

## 4. The Shared Price Cache

The single source of truth read by SSE and portfolio math. It owns prev-price / session-open /
direction bookkeeping so providers stay dumb.

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
                # First sight this session: open == prev == price.
                q = Quote(ticker, price, price, price, ts)
            else:
                q = Quote(ticker, price, existing.price, existing.session_open, ts)
            self._quotes[ticker] = q
            return q

    def seed(self, ticker: str, price: float) -> Quote:
        """Insert a ticker with no prior entry (synchronous sim seeding).
        No-op if already present."""
        with self._lock:
            if ticker not in self._quotes:
                return self.update(ticker, price)
            return self._quotes[ticker]
```

Notes:
- **`session_open` is set on first insert and never overwritten** until backend restart.
- In-memory and process-local — matches the single-container design and is forward-compatible
  with multi-user (key by `(user_id, ticker)` later).
- `RLock` guards the dict against the poller task and SSE readers touching it concurrently.

---

## 5. The Simulator (default source)

Generates believable streaming prices for any set of tickers with zero external dependencies,
so the app is fully functional out of the box.

### 5.1 Price model — Geometric Brownian Motion

Each ticker evolves by discrete GBM over a step of size `dt`:

```
S_{t+dt} = S_t · exp( (μ − ½σ²)·dt  +  σ·√dt·Z )
```

- `μ` (drift): small per-ticker annualized bias
- `σ` (volatility): per-ticker annualized volatility (tech > defensives)
- `dt`: step in years, tuned for *visual* pacing rather than literal calendar time
- `Z`: a standard-normal shock, **correlated across tickers** (§5.3)

GBM keeps prices positive and produces the multiplicative, percentage-based motion real
equities show.

### 5.2 Deterministic seed prices

The 10 default tickers start from a small hardcoded realistic table. Any other symbol gets a
seed derived from a hash of its name, mapped into **$50–$300** — so the same symbol always
opens at the same price across restarts.

```python
# backend/market/seeds.py
import hashlib

SEED_PRICES: dict[str, float] = {
    "AAPL": 190.0, "GOOGL": 175.0, "MSFT": 420.0, "AMZN": 185.0, "TSLA": 240.0,
    "NVDA": 1180.0, "META": 500.0, "JPM": 200.0, "V": 280.0, "NFLX": 650.0,
}

def seed_price(ticker: str) -> float:
    """Deterministic starting price. Known tickers use the realistic table;
    everything else hashes into the $50–$300 band."""
    if ticker in SEED_PRICES:
        return SEED_PRICES[ticker]
    digest = hashlib.sha256(ticker.encode()).digest()
    frac = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF   # [0, 1)
    return round(50.0 + frac * 250.0, 2)
```

### 5.3 Correlation

Real markets move together. We model that cheaply with a **shared market factor plus a
per-ticker idiosyncratic shock**, with a sector sub-factor:

```
Z_i = β_i · Z_market  +  γ_i · Z_sector  +  resid_i · Z_idio
```

- `Z_market`: one standard-normal draw per step shared by all tickers ("the market")
- `Z_sector`: a sub-factor shared within a sector (e.g. tech)
- `Z_idio`: an independent draw per ticker
- weights chosen so `var(Z_i) ≈ 1`

When the market ticks up, most names rise, with tech amplified — without a full covariance
matrix. Sector assignment for unknown tickers comes from the symbol hash, so it is
deterministic too.

### 5.4 Random events (drama)

Each step, with small probability, inject a one-off **2–5% jump** on a single tracked ticker so
the screen feels alive. Bounded and rare so it reads as "news," not chaos.

### 5.5 The engine

The **engine** holds all math and mutable state; the **adapter** (§5.6) is a thin
`MarketDataProvider` wrapper, keeping the GBM logic independently unit-testable.

```python
# backend/market/sim_engine.py
import math
import random
import hashlib
from dataclasses import dataclass
from .seeds import seed_price

EVENT_PROB_PER_STEP = 0.01
EVENT_MIN, EVENT_MAX = 0.02, 0.05

@dataclass
class TickerParams:
    drift: float        # μ, annualized
    vol: float          # σ, annualized
    beta: float         # market-factor loading
    sector: str
    sector_beta: float
    resid: float        # idiosyncratic weight (so total variance ≈ 1)


class SimEngine:
    """In-process GBM simulator with correlation and random events.

    Seeding is deterministic (pure function of the symbol); the walk uses a
    per-session RNG, so paths differ run-to-run while starting prices stay stable.
    """

    # dt tuned for visual pacing, not literal calendar time.
    DT = 0.5 / (252 * 6.5 * 3600)

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._price: dict[str, float] = {}
        self._params: dict[str, TickerParams] = {}

    # ---- deterministic synchronous seeding -------------------------------
    def ensure_seeded(self, ticker: str) -> float:
        """Assign a starting price + params the moment a ticker is tracked.
        Idempotent; returns the current (or freshly seeded) price."""
        if ticker not in self._price:
            self._price[ticker] = seed_price(ticker)
            self._params[ticker] = self._derive_params(ticker)
        return self._price[ticker]

    def _derive_params(self, ticker: str) -> TickerParams:
        h = hashlib.sha256(ticker.encode()).digest()
        def unit(i: int) -> float:                  # stable [0,1) from byte i
            return h[i] / 255.0
        sector = "tech" if unit(7) > 0.5 else "other"
        beta = 0.6 + 0.6 * unit(8)                  # 0.6–1.2
        sector_beta = 0.3 if sector == "tech" else 0.15
        vol = 0.20 + 0.40 * unit(9)                 # 20%–60% annualized
        drift = 0.00 + 0.10 * (unit(10) - 0.5)      # mild ±5% annualized
        resid = max(0.2, math.sqrt(max(0.0, 1 - 0.25 * beta**2 - sector_beta**2)))
        return TickerParams(drift, vol, beta, sector, sector_beta, resid)

    # ---- stepping --------------------------------------------------------
    def step(self, tickers: set[str]) -> dict[str, float]:
        """Advance one step for the tracked set; return latest prices."""
        for t in tickers:
            self.ensure_seeded(t)

        z_market = self._rng.gauss(0, 1)
        z_tech = self._rng.gauss(0, 1)

        for t in tickers:
            p = self._params[t]
            z_sector = z_tech if p.sector == "tech" else self._rng.gauss(0, 1)
            z = (p.beta * z_market
                 + p.sector_beta * z_sector
                 + p.resid * self._rng.gauss(0, 1))
            self._apply_gbm(t, z)

        self._maybe_event(tickers)
        return {t: self._price[t] for t in tickers}

    def _apply_gbm(self, ticker: str, z: float) -> None:
        p = self._params[ticker]
        dt = self.DT
        drift_term = (p.drift - 0.5 * p.vol**2) * dt
        shock_term = p.vol * math.sqrt(dt) * z
        self._price[ticker] *= math.exp(drift_term + shock_term)

    def _maybe_event(self, tickers: set[str]) -> None:
        if not tickers or self._rng.random() >= EVENT_PROB_PER_STEP:
            return
        sym = self._rng.choice(list(tickers))
        magnitude = self._rng.uniform(EVENT_MIN, EVENT_MAX)
        direction = self._rng.choice((-1, 1))
        self._price[sym] *= (1 + direction * magnitude)
```

### 5.6 The adapter

```python
# backend/market/simulator.py
from collections.abc import Iterable
from .base import MarketDataProvider
from .sim_engine import SimEngine

class SimulatorMarketData(MarketDataProvider):
    def __init__(self) -> None:
        self._engine = SimEngine()

    async def get_prices(self, tickers: Iterable[str]) -> dict[str, float]:
        # Advance the walk and return the latest price for each tracked ticker.
        return self._engine.step(set(tickers))

    def seed_price(self, ticker: str) -> float | None:
        # Deterministic, synchronous, never None.
        return self._engine.ensure_seeded(ticker)

    async def validate_ticker(self, ticker: str) -> bool:
        return ticker.isalpha() and 1 <= len(ticker) <= 6   # any well-formed symbol
```

---

## 6. The Massive Client (optional real-data source)

Massive (formerly **Polygon.io**) is a Polygon-compatible REST provider. We need only a tiny
slice: *the latest price for a set of tickers*.

### 6.1 Endpoint, auth, rate limits

| Item | Value |
|---|---|
| REST base URL | `https://api.massive.com` (legacy `https://api.polygon.io` also accepted) |
| Auth (preferred) | `Authorization: Bearer <MASSIVE_API_KEY>` header (keeps the key out of logs) |
| Poll endpoint | `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,TSLA,…` |
| Free tier | ~5 req/min, 15-min delayed → poll every **≥15s** |
| Paid tiers | higher limits, real-time → poll every **2–15s** |

The **filtered full-market snapshot** returns all tracked tickers in **one request**, so the
whole tracked set costs one request per poll (critical for the free-tier limit). A symbol that
doesn't exist is simply **omitted** from the response array — that's how we detect unknown
tickers on add.

Example response (trimmed):

```json
{
  "status": "OK",
  "count": 2,
  "tickers": [
    { "ticker": "AAPL", "lastTrade": { "p": 183.12, "t": 1605192894600000000 },
      "min": { "c": 183.10, "t": 1605192894000 }, "day": { "c": 183.1 }, "prevDay": { "c": 181.7 } },
    { "ticker": "TSLA", "lastTrade": { "p": 242.55, "t": 1605192894500000000 }, "prevDay": { "c": 240.10 } }
  ]
}
```

### 6.2 Tolerant parsing

Latest-price resolution per row, first present wins: `lastTrade.p` → `min.c` → `day.c`. If none
are present, the ticker is "no price yet." Timestamps need normalizing: `lastTrade.t` is **Unix
nanoseconds**, `min.t` is **milliseconds**.

```python
# backend/market/massive.py
import httpx
from collections.abc import Iterable
from .base import MarketDataProvider

BASE_URL = "https://api.massive.com"
SNAPSHOT_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"

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
        resp = await self._client.get(SNAPSHOT_PATH, params={"tickers": symbols})
        resp.raise_for_status()
        out: dict[str, float] = {}
        for row in resp.json().get("tickers", []):
            sym = row.get("ticker")
            price = _resolve_price(row)
            if sym and price is not None:
                out[sym] = price
        return out

    def seed_price(self, ticker: str) -> float | None:
        return None   # price only known after a poll

    async def validate_ticker(self, ticker: str) -> bool:
        # The snapshot omits unknown symbols, so a resolvable price == valid.
        prices = await self.get_prices([ticker])
        return ticker in prices


def _resolve_price(row: dict) -> float | None:
    for parent, child in (("lastTrade", "p"), ("min", "c"), ("day", "c")):
        val = (row.get(parent) or {}).get(child)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    return None
```

> **Items to confirm against a live key** (the parser already tolerates all of these): exact
> host and Bearer-header support; whether `lastTrade` is present on the free tier or we rely on
> `min.c`/`day.c`; real free-tier rate limit; and the empty-result behavior when every
> requested symbol is invalid (`count: 0`, empty `tickers`).

---

## 7. The Poller — single background task

One asyncio task, **identical for both providers**: compute the tracked set, ask the provider
for prices, write the cache. Cadence is the only difference.

```python
# backend/market/poller.py
import asyncio
import logging
from collections.abc import Callable
from .base import MarketDataProvider
from .cache import PriceCache

log = logging.getLogger("finally.market")

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
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._provider.aclose()

    async def _run(self) -> None:
        while True:
            try:
                tickers = self._tracked_set()
                if tickers:
                    prices = await self._provider.get_prices(tickers)
                    for ticker, price in prices.items():
                        self._cache.update(ticker, price)
            except Exception:   # never let a transient error kill the loop
                log.exception("market poll failed")
            await asyncio.sleep(self._interval)
```

- `tracked_set()` is injected by the app; the poller knows nothing about the database (§9).
- **Cadence:** simulator `~0.5s`; Massive free `15s`; Massive paid `2–15s`.
- SSE streams to clients on its **own** ~500ms cadence (§8), decoupled from the poll interval.
  In Massive mode the cache simply holds steady between polls.

---

## 8. SSE Streaming — `GET /api/stream/prices`

A long-lived Server-Sent Events connection. The client uses the native `EventSource` API. The
server pushes a snapshot of all tracked tickers on a ~500ms cadence and a `: keepalive` comment
every ~15s so the client can detect a silently dropped connection (drives the red status dot).

```python
# backend/market/stream.py
import asyncio
import json
from collections.abc import AsyncIterator
from .cache import PriceCache

PUSH_INTERVAL = 0.5       # seconds between price pushes
HEARTBEAT_INTERVAL = 15   # seconds between keepalive comments

async def price_event_stream(cache: PriceCache) -> AsyncIterator[str]:
    """Yield SSE-formatted frames: periodic price snapshots + heartbeats."""
    last_heartbeat = 0.0
    loop = asyncio.get_event_loop()
    while True:
        snap = cache.snapshot()
        if snap:
            payload = [q.to_event() for q in snap.values()]
            yield f"event: prices\ndata: {json.dumps(payload)}\n\n"

        now = loop.time()
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            yield ": keepalive\n\n"
            last_heartbeat = now

        await asyncio.sleep(PUSH_INTERVAL)
```

```python
# backend/routes/stream.py
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from ..market.stream import price_event_stream

router = APIRouter()

@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    cache = request.app.state.price_cache
    return StreamingResponse(
        price_event_stream(cache),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # disable proxy buffering (e.g. nginx)
        },
    )
```

**Event shape on the wire** (one `prices` event every ~500ms):

```
event: prices
data: [{"ticker":"AAPL","price":190.12,"prev_price":190.05,"session_open":190.0,"ts":1717340000.5,"direction":"up"}, ...]

: keepalive
```

The frontend computes daily change % client-side as `(price - session_open) / session_open`
and recomputes the header total value from current positions × latest streamed prices (no
polling).

### Client sketch

```js
const es = new EventSource("/api/stream/prices");
es.addEventListener("prices", (e) => {
  for (const q of JSON.parse(e.data)) applyTick(q);   // flash, sparkline, totals
});
// Connection-status dot is derived from es.readyState + heartbeat arrival:
//   green = OPEN & heartbeats arriving; yellow = CONNECTING (onerror retry);
//   red = CLOSED or no message/heartbeat within ~2× the 15s keepalive window.
```

---

## 9. Selection, Tracked Set & App Wiring

### 9.1 Factory — env-based selection

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

### 9.2 Tracked set — the watchlist ∪ positions query

The provider tracks the **union of the watchlist and held positions**, so a held-but-unwatched
ticker keeps streaming (its live value stays current in the header, positions table, and P&L).
This is a synchronous SQLite read, fast enough to call every poll.

```python
# backend/market/tracked.py
import sqlite3

def get_tracked_symbols(db: sqlite3.Connection, user_id: str = "default") -> set[str]:
    rows = db.execute(
        """
        SELECT ticker FROM watchlist WHERE user_id = ?
        UNION
        SELECT ticker FROM positions WHERE user_id = ?
        """,
        (user_id, user_id),
    ).fetchall()
    return {r[0] for r in rows}
```

### 9.3 FastAPI lifespan wiring

On startup: build the cache and provider, **synchronously seed the current tracked set** so
prices exist before the first poll (simulator only — Massive returns `None`), then start the
poller. On shutdown: stop the poller and close the provider.

```python
# backend/app.py (sketch)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .db import get_connection, init_db
from .market.cache import PriceCache
from .market.poller import MarketPoller
from .market.factory import make_provider
from .market.tracked import get_tracked_symbols

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_connection()
    init_db(db)                                   # lazy schema + seed (PLAN §7)

    cache = PriceCache()
    provider, interval = make_provider()
    tracked = lambda: get_tracked_symbols(db)

    # Synchronously seed so prices exist before the first poll (sim mode).
    for ticker in tracked():
        seed = provider.seed_price(ticker)
        if seed is not None:
            cache.seed(ticker, seed)

    poller = MarketPoller(provider, cache, tracked_set=tracked, interval=interval)
    app.state.price_cache = cache
    app.state.market_provider = provider
    await poller.start()
    try:
        yield
    finally:
        await poller.stop()

app = FastAPI(lifespan=lifespan)
```

---

## 10. Integration with Trades & Watchlist (PLAN §8)

The market layer is consumed by the portfolio and watchlist routes. The relevant rules:

**`POST /api/watchlist` (add a ticker)**
```python
# simulator mode: any well-formed symbol is accepted and seeded synchronously.
# massive mode:   validate against the snapshot; reject unknown symbols with 400.
if not await provider.validate_ticker(ticker):
    raise HTTPException(400, f"Unknown ticker: {ticker}")
# Insert into watchlist table; in sim mode prime the cache so a price is instantly available:
seed = provider.seed_price(ticker)
if seed is not None:
    cache.seed(ticker, seed)
```

**`POST /api/portfolio/trade` (execute a trade)**
```python
quote = cache.get(ticker)
if quote is None:
    # Massive mode, symbol added but not yet polled.
    raise HTTPException(409, f"Price not yet available for {ticker}")
fill_price = quote.price
# ... validate cash (buy) / shares (sell), update positions + cash, append trade,
#     record a portfolio snapshot. Trading is NOT restricted to the watchlist:
#     a successful trade in an unwatched ticker implicitly adds it to the watchlist
#     (and therefore the tracked set / cache) so the user can monitor what they hold.
```

Because the tracked set is the union of watchlist and positions, an implicitly-added or
held-but-removed ticker keeps streaming without any special handling.

---

## 11. Testing Strategy (PLAN §12)

Both providers are tested against the **same** contract suite (§3) so they remain
interchangeable.

**Cache (`cache.py`)**
- First insert sets `session_open == prev_price == price`.
- Subsequent updates roll `prev_price` and preserve `session_open`.
- `direction` is `up`/`down`/`flat` correctly; `seed` is a no-op when already present.

**Simulator (`sim_engine.py`)**
- Determinism: `seed_price("PYPL")` is identical across processes; known tickers use the table,
  unknown land in `$50–$300`.
- GBM validity: over many seeded-RNG steps, prices stay `> 0`; log-returns have ~zero mean and
  the configured volatility (statistical assertion with tolerance).
- Correlation: with a fixed RNG, two same-sector tickers show positive return correlation over
  a window; cross-sector is lower.
- Events: with `EVENT_PROB_PER_STEP` forced to `1.0`, one step produces a 2–5% move on exactly
  one ticker.
- Synchronous seeding: `ensure_seeded` on a fresh symbol returns a price and is idempotent.

**Massive (`massive.py`)**
- `_resolve_price` against captured JSON fixtures: `lastTrade` present / absent / only a day
  bar — locks in the tolerant fallback order.
- `validate_ticker` returns `False` when the symbol is omitted from `tickers`.
- HTTP errors are surfaced and don't crash the poller (covered via the poller test).

**Poller (`poller.py`)**
- With a fake provider returning scripted prices, the cache reflects them and prev/open/
  direction bookkeeping is correct across ticks.
- A provider that raises does not kill the loop (next tick still runs).

**SSE (`stream.py`)**
- The generator emits a `prices` event with the expected JSON shape and periodic `: keepalive`
  comments.

**E2E (Playwright, `LLM_MOCK=true`)**
- Fresh start: default watchlist streams prices; flashes occur.
- SSE resilience: disconnect → reconnect, status dot transitions green → yellow/red → green.

---

## 12. Cross-References

| Topic | Deep-dive document |
|---|---|
| Unified API, cache, poller, factory, contract | [`MARKET_INTERFACE.md`](./MARKET_INTERFACE.md) |
| Simulator math, seeding, correlation, events | [`MARKET_SIMULATOR.md`](./MARKET_SIMULATOR.md) |
| Massive/Polygon REST reference, endpoints, parsing | [`MASSIVE_API.md`](./MASSIVE_API.md) |
| Overall product & architecture | [`PLAN.md`](./PLAN.md) |
