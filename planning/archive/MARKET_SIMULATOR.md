# Market Simulator — Design & Code Structure

> FinAlly's **default** price source, used whenever `MASSIVE_API_KEY` is absent. It generates
> believable streaming prices for any set of tickers with zero external dependencies, so the
> app is fully functional out of the box.
>
> Implements the `MarketDataProvider` contract from
> [MARKET_INTERFACE.md](./MARKET_INTERFACE.md); the real-data alternative is
> [MASSIVE_API.md](./MASSIVE_API.md).

## 1. Goals

1. **Realistic-looking motion** — prices wander like real stocks (geometric Brownian motion),
   not white noise.
2. **Visual drama** — occasional sudden jumps so the terminal feels alive (PLAN §6 "events").
3. **Correlation** — related tickers (e.g. tech names) move together, so the heatmap and
   watchlist feel coherent rather than independent.
4. **Deterministic seeding** — the *starting* price for any symbol is a pure function of the
   symbol, so the same ticker always opens at the same price across restarts (PLAN §6).
5. **Synchronous availability** — a newly added ticker gets a usable price the instant it
   enters the cache; no empty-state gap for display or trading (PLAN §6/§8).
6. **Cheap & in-process** — a plain object advanced by the poller every ~500ms; no threads of
   its own, no I/O.

## 2. Price Model — Geometric Brownian Motion

Each ticker's price evolves by discrete GBM. Over one step of size `dt`:

```
S_{t+dt} = S_t · exp( (μ − ½σ²)·dt  +  σ·√dt·Z )
```

- `S_t` — current price
- `μ` (drift) — small annualized upward/downward bias per ticker
- `σ` (volatility) — annualized volatility per ticker (tech > utilities, etc.)
- `dt` — step in years; at ~500ms steps, `dt = 0.5 / (252·6.5·3600)` ≈ one trading-second
  fraction. In practice we pick a `dt` tuned for *visual* pacing rather than literal calendar
  time (see §6).
- `Z` — a standard-normal shock, **correlated across tickers** (§4).

GBM guarantees prices stay positive and produces the multiplicative, percentage-based motion
real equities show.

## 3. Seed Prices (deterministic starting point)

- The 10 default tickers start from a small **hardcoded realistic table** (PLAN §6).
- **Any other symbol** (user- or AI-added, e.g. `PYPL`) gets a deterministic seed derived from
  a hash of the symbol, mapped into **\$50–\$300**. Same symbol → same seed, every run.

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
    # First 4 bytes -> [0, 1) -> map into [50, 300].
    frac = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    return round(50.0 + frac * 250.0, 2)
```

The same hash also seeds that ticker's per-symbol `μ`/`σ` and its correlation group, so an
unknown ticker gets stable, sensible dynamics too (§4–§5).

## 4. Correlation

Real markets move together. We model this cheaply with a **shared market factor plus a
per-ticker idiosyncratic shock**, with an optional sector grouping:

```
Z_i = β_i · Z_market  +  √(1 − β_i²) · Z_i^idio
```

- `Z_market` — one standard-normal draw per step shared by all tickers (the "market").
- `Z_i^idio` — an independent draw per ticker.
- `β_i` — how tightly ticker *i* tracks the market (its "beta"); higher for tech, lower for
  defensives. Sector members additionally share a sector sub-factor for tighter intra-group
  correlation.

This yields the right qualitative behavior — when the market ticks up, most names rise, with
tech amplified — without a full covariance matrix. Sector assignment for unknown tickers comes
from the symbol hash, so grouping is deterministic too.

```python
# Per-step, conceptually:
z_market = rng.gauss(0, 1)
z_tech   = rng.gauss(0, 1)   # sector sub-factor
for sym in tickers:
    p = params[sym]
    z_sector = z_tech if p.sector == "tech" else rng.gauss(0, 1)
    z_idio   = rng.gauss(0, 1)
    z = (p.beta * z_market
         + p.sector_beta * z_sector
         + p.resid * z_idio)   # weights chosen so var(z) ≈ 1
    apply_gbm_step(sym, z)
```

## 5. Drama — Random Events

Occasionally inject a sudden **2–5% move** on a single ticker (PLAN §6) so the screen has
life. Each step, with small probability, pick a tracked ticker and add a one-off multiplicative
jump on top of its GBM step:

```python
EVENT_PROB_PER_STEP = 0.01      # ~1% chance per step that *an* event fires
EVENT_MIN, EVENT_MAX = 0.02, 0.05

if rng.random() < EVENT_PROB_PER_STEP:
    sym = rng.choice(list(tickers))
    magnitude = rng.uniform(EVENT_MIN, EVENT_MAX)
    direction = rng.choice((-1, 1))
    price[sym] *= (1 + direction * magnitude)
```

Events are intentionally rare and bounded so they read as "news" rather than chaos.

## 6. Stepping Cadence

- The simulator does **not** own a timer. The shared `MarketPoller`
  (MARKET_INTERFACE.md §5) calls `step()` every `~0.5s`; each call advances the walk one `dt`.
- `dt` is tuned for *visual* pacing: roughly 1–2% typical daily-equivalent motion should be
  visible over a minute or two of watching, so flashes happen often enough to feel live but
  prices don't run away. Concretely, pick a per-step `σ·√dt` on the order of 0.05–0.15% so
  individual ticks are small and frequent, with events providing the occasional larger move.
- Because seeding is deterministic but the *walk* uses a fresh RNG each session, charts differ
  run-to-run while **starting** prices are stable (satisfies PLAN §6).

## 7. Code Structure

```
backend/market/
├── base.py          # MarketDataProvider ABC          (MARKET_INTERFACE.md §3)
├── types.py         # Quote dataclass                  (MARKET_INTERFACE.md §2)
├── cache.py         # PriceCache (prev/open/direction) (MARKET_INTERFACE.md §4)
├── poller.py        # MarketPoller background loop      (MARKET_INTERFACE.md §5)
├── factory.py       # env-based provider selection      (MARKET_INTERFACE.md §6)
├── seeds.py         # SEED_PRICES table + seed_price()  (§3 here)
├── sim_engine.py    # SimEngine: GBM walk + events      (§8 here)
└── simulator.py     # SimulatorMarketData adapter       (MARKET_INTERFACE.md §8)
```

The **engine** (`sim_engine.py`) holds all the math and mutable state; the **adapter**
(`simulator.py`) is a thin `MarketDataProvider` wrapper. This keeps the GBM logic independently
unit-testable without the provider interface in the way.

## 8. The Engine

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
    beta: float         # market factor loading
    sector: str
    sector_beta: float
    resid: float        # idiosyncratic weight (so total variance ≈ 1)


class SimEngine:
    """In-process GBM price simulator with correlation and random events.

    Seeding is deterministic (pure function of symbol); the walk uses a per-session
    RNG so paths differ run-to-run while starting prices stay stable.
    """

    # dt tuned for visual pacing, not literal calendar time (see §6).
    DT = 0.5 / (252 * 6.5 * 3600)

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()       # session walk randomness
        self._price: dict[str, float] = {}
        self._params: dict[str, TickerParams] = {}

    # ---- seeding (deterministic, synchronous) ----------------------------
    def ensure_seeded(self, ticker: str) -> float:
        """Assign a starting price + params the moment a ticker is tracked.
        Idempotent; returns the current (or freshly seeded) price."""
        if ticker not in self._price:
            self._price[ticker] = seed_price(ticker)
            self._params[ticker] = self._derive_params(ticker)
        return self._price[ticker]

    def _derive_params(self, ticker: str) -> TickerParams:
        # Deterministic per-symbol params from the symbol hash.
        h = hashlib.sha256(ticker.encode()).digest()
        def unit(i: int) -> float:                # stable [0,1) from byte i
            return h[i] / 255.0
        sector = "tech" if unit(7) > 0.5 else "other"
        beta = 0.6 + 0.6 * unit(8)                # 0.6–1.2
        sector_beta = 0.3 if sector == "tech" else 0.15
        vol = 0.20 + 0.40 * unit(9)               # 20%–60% annualized
        drift = 0.00 + 0.10 * (unit(10) - 0.5)    # mild ±5% annualized
        # Residual weight so var(z) ≈ 1: resid² = 1 − beta²·(market var share) − ...
        resid = max(0.2, math.sqrt(max(0.0, 1 - 0.25 * beta**2 - sector_beta**2)))
        return TickerParams(drift, vol, beta, sector, sector_beta, resid)

    # ---- stepping --------------------------------------------------------
    def step(self, tickers: set[str]) -> dict[str, float]:
        """Advance one step for the given tracked set; return latest prices."""
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

## 9. How It Satisfies the Contract (MARKET_INTERFACE.md §9)

| Requirement | How the simulator meets it |
|---|---|
| `seed_price` synchronous, never None | `ensure_seeded` assigns from `seed_price()` immediately |
| Deterministic across restarts | Starting price + params are pure functions of the symbol hash |
| `validate_ticker` accepts any well-formed symbol | Adapter checks `isalpha()` and length 1–6 |
| Update cadence ~0.5s | Poller calls `step()` every 0.5s; no internal timer |
| Prices stay positive, look real | GBM multiplicative model |
| Correlation | Shared market + sector factors per step |
| Drama | Bounded 2–5% random events |

## 10. Testing (PLAN §12)

- **Determinism:** `seed_price("PYPL")` returns the same value across processes; in
  `SEED_PRICES` band for known tickers, `$50–$300` for unknown.
- **GBM validity:** over many steps with a seeded RNG, prices stay > 0; log-returns have
  ~zero mean and the configured volatility (statistical assertion with tolerance).
- **Correlation:** with a fixed RNG, two same-sector tickers show positive return correlation
  over a window; cross-sector lower.
- **Events:** with `EVENT_PROB_PER_STEP` forced to 1.0, a single step produces a 2–5% move on
  exactly one ticker.
- **Synchronous seeding:** `ensure_seeded` on a brand-new symbol returns a price and is
  idempotent (second call doesn't reset it).
- **Interface conformance:** `SimulatorMarketData` passes the shared `MarketDataProvider`
  contract suite (MARKET_INTERFACE.md §10).
