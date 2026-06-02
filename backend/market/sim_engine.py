import math
import random
import hashlib
from dataclasses import dataclass

from .seeds import seed_price

EVENT_PROB_PER_STEP = 0.01
EVENT_MIN, EVENT_MAX = 0.02, 0.05


@dataclass
class TickerParams:
    drift: float
    vol: float
    beta: float
    sector: str
    sector_beta: float
    resid: float


class SimEngine:
    """In-process GBM price simulator with correlation and random events.

    Seeding is deterministic (pure function of symbol); the walk uses a per-session
    RNG so paths differ run-to-run while starting prices stay stable.
    """

    # dt tuned for visual pacing, not literal calendar time.
    DT = 0.5 / (252 * 6.5 * 3600)

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._price: dict[str, float] = {}
        self._params: dict[str, TickerParams] = {}

    def ensure_seeded(self, ticker: str) -> float:
        """Assign a starting price + params the moment a ticker is tracked.
        Idempotent; returns the current (or freshly seeded) price."""
        if ticker not in self._price:
            self._price[ticker] = seed_price(ticker)
            self._params[ticker] = self._derive_params(ticker)
        return self._price[ticker]

    def _derive_params(self, ticker: str) -> TickerParams:
        h = hashlib.sha256(ticker.encode()).digest()

        def unit(i: int) -> float:
            return h[i] / 255.0

        sector = "tech" if unit(7) > 0.5 else "other"
        beta = 0.6 + 0.6 * unit(8)
        sector_beta = 0.3 if sector == "tech" else 0.15
        vol = 0.20 + 0.40 * unit(9)
        drift = 0.00 + 0.10 * (unit(10) - 0.5)
        resid = max(0.2, math.sqrt(max(0.0, 1 - 0.25 * beta**2 - sector_beta**2)))
        return TickerParams(drift, vol, beta, sector, sector_beta, resid)

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
