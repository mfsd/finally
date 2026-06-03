import time
from collections.abc import Iterable

from .base import MarketDataProvider
from .sim_engine import SimEngine


class SimulatorMarketData(MarketDataProvider):
    """MarketDataProvider backed by the in-process GBM simulator.

    Any well-formed ticker symbol is accepted and immediately gets a
    deterministic seed price — no external dependencies required.
    """

    def __init__(self) -> None:
        self._engine = SimEngine()

    async def get_prices(self, tickers: Iterable[str]) -> dict[str, tuple[float, float]]:
        ts = time.time()
        return {ticker: (price, ts) for ticker, price in self._engine.step(set(tickers)).items()}

    def seed_price(self, ticker: str) -> float | None:
        return self._engine.ensure_seeded(ticker)

    def override_price(self, ticker: str, price: float) -> None:
        """Seed the simulator with a real market price, replacing the hash-derived default."""
        self._engine.ensure_seeded(ticker)
        self._engine._price[ticker] = price

    async def validate_ticker(self, ticker: str) -> bool:
        return ticker.isalpha() and 1 <= len(ticker) <= 6
