import pytest

from market.base import MarketDataProvider
from market.fallback import FallbackMarketData
from market.simulator import SimulatorMarketData


class BrokenProvider(MarketDataProvider):
    async def get_prices(self, tickers):
        raise RuntimeError("upstream forbidden")

    def seed_price(self, ticker: str):
        return None

    async def validate_ticker(self, ticker: str):
        raise RuntimeError("upstream forbidden")


class PartialProvider(MarketDataProvider):
    async def get_prices(self, tickers):
        return {"AAPL": (100.0, 1.0)}

    def seed_price(self, ticker: str):
        return None

    async def validate_ticker(self, ticker: str):
        return ticker == "AAPL"


class AsyncSeedProvider(PartialProvider):
    allow_fallback_seed = False

    def seed_price(self, ticker: str):
        return None


@pytest.mark.asyncio
async def test_fallback_provider_uses_simulator_when_primary_fails():
    provider = FallbackMarketData(BrokenProvider(), SimulatorMarketData())

    prices = await provider.get_prices({"AAPL"})

    assert "AAPL" in prices
    assert await provider.validate_ticker("AAPL") is True


@pytest.mark.asyncio
async def test_fallback_provider_fills_missing_prices():
    provider = FallbackMarketData(PartialProvider(), SimulatorMarketData())

    prices = await provider.get_prices({"AAPL", "MSFT"})

    assert prices["AAPL"] == (100.0, 1.0)
    assert "MSFT" in prices


def test_fallback_provider_can_disable_synchronous_fallback_seed():
    provider = FallbackMarketData(AsyncSeedProvider(), SimulatorMarketData())

    assert provider.seed_price("AAPL") is None
