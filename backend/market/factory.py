import os

from .base import MarketDataProvider
from .simulator import SimulatorMarketData
from .massive import MassiveMarketData


def make_provider() -> tuple[MarketDataProvider, float]:
    """Return (provider, poll_interval_seconds).

    If MASSIVE_API_KEY is set, fetch real previous-close prices from Massive
    and use them to seed the GBM simulator, then return the simulator as the
    live provider. This gives realistic starting prices + live-moving charts.
    If no key is set, the simulator uses its own deterministic seed prices.
    """
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if key:
        return _MassiveSeededSimulator(api_key=key), 0.5
    return SimulatorMarketData(), 0.5


class _MassiveSeededSimulator(MarketDataProvider):
    """Wraps SimulatorMarketData, seeding it with real prev-close prices from Massive."""

    def __init__(self, api_key: str) -> None:
        self._massive = MassiveMarketData(api_key=api_key)
        self._sim = SimulatorMarketData()

    async def start(self) -> None:
        await self._massive.start()
        await self._sim.start()

    async def aclose(self) -> None:
        await self._massive.aclose()
        await self._sim.aclose()

    async def seed_from_massive(self, tickers: list[str]) -> None:
        """Fetch real prev-close prices and inject them into the simulator."""
        real_prices = await self._massive.fetch_seed_prices(tickers)
        for ticker, price in real_prices.items():
            self._sim.override_price(ticker, price)

    async def get_prices(self, tickers) -> dict[str, tuple[float, float]]:
        return await self._sim.get_prices(tickers)

    def seed_price(self, ticker: str) -> float | None:
        return self._sim.seed_price(ticker)

    async def validate_ticker(self, ticker: str) -> bool:
        return await self._massive.validate_ticker(ticker)
