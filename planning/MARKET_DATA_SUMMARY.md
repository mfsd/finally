# Market Data — Summary

> Condensed reference for FinAlly's market-data layer, distilled from the detailed design
> documents now archived under `planning/archive/`:
> `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md`,
> `MARKET_DATA_DESIGN.md`, and the post-implementation `MARKET_DATA_REVIEW.md`.
> This file is the single starting point; consult the archived originals for full code
> listings and rationale.

---

## 1. The Big Picture

FinAlly needs *one* stream of live stock prices regardless of where they come from. The
market-data layer provides exactly one abstraction — `MarketDataProvider` — with two
interchangeable implementations:

- **Simulator** (default) — a self-contained geometric-Brownian-motion price generator.
  Used whenever `MASSIVE_API_KEY` is absent/empty. Zero external dependencies, so the app
  works out of the box.
- **Massive** (optional) — a REST client for the Polygon.io-compatible Massive API. Used
  when `MASSIVE_API_KEY` is set.

Everything downstream — the shared price cache, SSE streaming, portfolio math, the
frontend — is **agnostic** to which provider is running. The source is selected once, by
environment variable, at startup.

```
provider (sim | massive)  ──poller──>  PriceCache  ──SSE──>  frontend
        get_prices()                  (prev/open/dir)      /api/stream/prices
```

---

## 2. Data Flow & Components

| Component | File | Responsibility |
|---|---|---|
| `Quote` | `market/types.py` | Immutable price record: `ticker, price, prev_price, session_open, ts`, plus `direction` property (`up`/`down`/`flat`). |
| `MarketDataProvider` (ABC) | `market/base.py` | The one seam: `get_prices`, `seed_price`, `validate_ticker`, `start`/`aclose`. |
| `PriceCache` | `market/cache.py` | In-memory source of truth. Derives `prev_price`/`direction`, preserves `session_open`. `RLock`-guarded. |
| `MarketPoller` | `market/poller.py` | Single asyncio task; on a cadence, asks provider for the tracked set and writes the cache. Never dies on transient errors. |
| factory | `market/factory.py` | `make_provider()` → `(provider, interval)` chosen by `MASSIVE_API_KEY`. |
| `SimEngine` / `SimulatorMarketData` | `market/sim_engine.py`, `market/simulator.py` | GBM math + the thin provider adapter. |
| `MassiveMarketData` | `market/massive.py` | `httpx` adapter over the Massive snapshot endpoint with tolerant parsing. |
| seeds | `market/seeds.py` | Hardcoded realistic prices for the 10 defaults; deterministic hash seed ($50–$300) for anything else. |

### Key contracts

- **Push via a single poller.** Providers are *pull*-based (`get_prices` answers "latest price
  for these tickers"); the poller turns that into a *push* into the cache. The SSE endpoint
  reads `cache.snapshot()` on its own ~500ms cadence, decoupled from the poll interval.
- **Dynamic tracked set.** The poller is given a callable returning the **union of the
  watchlist and held positions**, recomputed each tick as the user trades/edits.
- **`get_prices` returns `dict[str, tuple[float, float]]`** — `(price, ts_epoch_seconds)` —
  so real trade timestamps flow through to the cache (this was tightened during review; the
  original design returned bare floats).
- **`session_open`** is set on first insert per ticker and never overwritten until the backend
  restarts. It is the daily-change baseline (no real previous-close); not persisted.

---

## 3. The Simulator (default)

Per ticker, price evolves by discrete geometric Brownian motion:

```
S_{t+dt} = S_t · exp( (μ − ½σ²)·dt  +  σ·√dt·Z )
```

- **Deterministic seeding** — starting price and per-symbol `μ`/`σ`/`β`/sector are pure
  functions of the symbol hash, so the same ticker always opens identically across restarts.
  The 10 defaults use a realistic hardcoded table (AAPL ~$190, NVDA ~$1180, …); unknowns hash
  into $50–$300.
- **Correlation** — `Z_i = β_i·Z_market + sector_beta·Z_sector + resid·Z_idio`, weights chosen
  so `var(Z) ≈ 1`. A shared market factor (plus a sector sub-factor for tech) makes related
  tickers move together — coherent heatmap and watchlist.
- **Drama** — with small probability per step, one ticker gets an extra bounded jump so the
  screen feels alive ("news" not chaos).
- **No internal timer** — the shared poller calls `step()` ~every 500ms; each call advances
  the walk one `dt`. The walk uses a fresh per-session RNG, so paths differ run-to-run while
  starting prices stay stable.

**Calibration (locked in during review):** `DT = 7.111e-6`, giving per-step `σ·√DT` of
~0.05–0.16% (on the design's 0.05–0.15% target). Events: `EVENT_PROB_PER_STEP = 0.003`,
magnitude `0.5%–2%`. The earlier values made events dominate variance and drove inter-ticker
correlation to ~0; the recalibration restored correlation (~0.69 for same-sector pairs).

---

## 4. The Massive Provider (optional)

- **Polygon.io-compatible** REST API. Base URL `https://api.massive.com`, Bearer-header auth.
  Treat Polygon's JSON schema as the working assumption; keep the parser tolerant.
- **Poll endpoint:** the filtered full-market snapshot —
  `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,TSLA,…` — returns the whole
  tracked set in **one request per poll** (critical for the free tier's ~5 req/min limit →
  default 15s interval; 2–15s on paid tiers).
- **Latest-price resolution (tolerant):** `lastTrade.p` → `min.c` → `day.c`, first present.
- **Timestamp normalization:** `lastTrade.t` is **nanoseconds** (`/1e9`), `min.t` is
  **milliseconds** (`/1e3`) → epoch seconds.
- **Unknown tickers** are simply *omitted* from the response array (no error). That's how an
  invalid symbol is detected on add (reject with `400`). A just-added valid ticker may have no
  cached price until the next poll lands → trades against it return "price not yet available."

---

## 5. Behavioral Contract (both implementations)

| Concern | Simulator | Massive |
|---|---|---|
| `validate_ticker` | True for any well-formed symbol | True only if snapshot resolves it |
| `seed_price` | Deterministic, synchronous, never None | None (await first poll) |
| First trade on a new ticker | Always priced immediately | "price not yet available" until first poll |
| Update cadence | ~0.5s | 15s free / 2–15s paid |
| Determinism across restarts | Same seed → same start price | Real (delayed) market data |

---

## 6. Implementation Status

The market-data layer is **fully implemented and wired** (PR #4 + review fixes in PR #5):

- All `market/*` modules above, plus `backend/db.py` (6-table lazy-init schema + seed),
  `backend/app.py` (FastAPI lifespan wiring), and routes `GET /api/stream/prices` and
  `GET /api/health`.
- **Tests: 117 passing, 0 failing.** Coverage spans cache bookkeeping, GBM validity &
  correlation, deterministic seeding, event injection, tolerant Massive parsing, poller
  resilience, SSE framing, and DB seeding/idempotency.

**Remaining (next milestones, per PLAN §8–§10):** portfolio routes, watchlist routes, the AI
chat route, the snapshot background task, and the full frontend. The market layer is the
foundation for all of these.
