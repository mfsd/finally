import asyncio
import pytest
from collections.abc import Iterable

from market.base import MarketDataProvider
from market.cache import PriceCache
from market.poller import MarketPoller


class FakeProvider(MarketDataProvider):
    """Scripted provider that returns pre-configured price sequences."""

    def __init__(self, price_sequence: list[dict[str, float]]) -> None:
        self._sequence = price_sequence
        self._call_count = 0
        self.started = False
        self.closed = False

    async def start(self) -> None:
        self.started = True

    async def aclose(self) -> None:
        self.closed = True

    async def get_prices(self, tickers: Iterable[str]) -> dict[str, tuple[float, float]]:
        idx = min(self._call_count, len(self._sequence) - 1)
        self._call_count += 1
        return {k: (v, 0.0) for k, v in self._sequence[idx].items() if k in set(tickers)}

    def seed_price(self, ticker: str) -> float | None:
        return None

    async def validate_ticker(self, ticker: str) -> bool:
        return True


class ErrorProvider(MarketDataProvider):
    """Provider that always raises an exception."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def get_prices(self, tickers: Iterable[str]) -> dict[str, tuple[float, float]]:
        raise self._error

    def seed_price(self, ticker: str) -> float | None:
        return None

    async def validate_ticker(self, ticker: str) -> bool:
        return True


@pytest.mark.asyncio
async def test_poller_writes_prices_to_cache():
    prices = [{"AAPL": 190.0, "GOOGL": 175.0}]
    provider = FakeProvider(prices)
    cache = PriceCache()
    poller = MarketPoller(provider, cache, tracked_set=lambda: {"AAPL", "GOOGL"}, interval=0.01)

    await poller.start()
    await asyncio.sleep(0.05)
    await poller.stop()

    assert cache.get("AAPL") is not None
    assert cache.get("GOOGL") is not None


@pytest.mark.asyncio
async def test_poller_updates_prev_price_correctly():
    """After the first poll (190.0) the cache is seeded; session_open stays at 190.0
    regardless of how many subsequent polls happen."""
    prices = [{"AAPL": 190.0}, {"AAPL": 195.0}]
    provider = FakeProvider(prices)
    cache = PriceCache()
    poller = MarketPoller(provider, cache, tracked_set=lambda: {"AAPL"}, interval=0.02)

    await poller.start()
    await asyncio.sleep(0.1)
    await poller.stop()

    quote = cache.get("AAPL")
    assert quote is not None
    assert quote.session_open == 190.0
    assert quote.price > 0


@pytest.mark.asyncio
async def test_poller_preserves_session_open():
    prices = [{"AAPL": 190.0}, {"AAPL": 195.0}, {"AAPL": 185.0}]
    provider = FakeProvider(prices)
    cache = PriceCache()
    poller = MarketPoller(provider, cache, tracked_set=lambda: {"AAPL"}, interval=0.01)

    await poller.start()
    await asyncio.sleep(0.08)
    await poller.stop()

    quote = cache.get("AAPL")
    assert quote is not None
    assert quote.session_open == 190.0


@pytest.mark.asyncio
async def test_poller_calls_provider_start():
    provider = FakeProvider([{"AAPL": 100.0}])
    cache = PriceCache()
    poller = MarketPoller(provider, cache, tracked_set=lambda: {"AAPL"}, interval=0.1)
    await poller.start()
    await poller.stop()
    assert provider.started


@pytest.mark.asyncio
async def test_poller_calls_provider_aclose():
    provider = FakeProvider([{"AAPL": 100.0}])
    cache = PriceCache()
    poller = MarketPoller(provider, cache, tracked_set=lambda: {"AAPL"}, interval=0.1)
    await poller.start()
    await poller.stop()
    assert provider.closed


@pytest.mark.asyncio
async def test_poller_survives_provider_exception():
    """A transient provider error must not kill the polling loop."""
    call_count = 0

    class FlickeringProvider(MarketDataProvider):
        async def get_prices(self, tickers):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient network error")
            return {"AAPL": (190.0, 0.0)}

        def seed_price(self, ticker):
            return None

        async def validate_ticker(self, ticker):
            return True

    provider = FlickeringProvider()
    cache = PriceCache()
    poller = MarketPoller(provider, cache, tracked_set=lambda: {"AAPL"}, interval=0.01)

    await poller.start()
    await asyncio.sleep(0.1)
    await poller.stop()

    assert call_count >= 2, "Poller should have continued after the error"
    assert cache.get("AAPL") is not None, "Cache should have prices from second poll"


@pytest.mark.asyncio
async def test_poller_skips_poll_when_tracked_set_empty():
    provider = FakeProvider([])
    cache = PriceCache()
    poller = MarketPoller(provider, cache, tracked_set=lambda: set(), interval=0.01)

    await poller.start()
    await asyncio.sleep(0.05)
    await poller.stop()

    assert provider._call_count == 0, "Provider should not be called when tracked set is empty"


@pytest.mark.asyncio
async def test_poller_uses_dynamic_tracked_set():
    """tracked_set is called each poll, so additions take effect without restart."""
    tickers = {"AAPL"}
    prices = [{"AAPL": 190.0, "GOOGL": 175.0}]
    provider = FakeProvider(prices)
    cache = PriceCache()
    poller = MarketPoller(provider, cache, tracked_set=lambda: tickers, interval=0.02)

    await poller.start()
    await asyncio.sleep(0.05)
    tickers.add("GOOGL")
    await asyncio.sleep(0.05)
    await poller.stop()

    assert cache.get("GOOGL") is not None


@pytest.mark.asyncio
async def test_poller_stop_cancels_task():
    provider = FakeProvider([{"AAPL": 100.0}])
    cache = PriceCache()
    poller = MarketPoller(provider, cache, tracked_set=lambda: {"AAPL"}, interval=10.0)
    await poller.start()
    assert poller._task is not None
    assert not poller._task.done()
    await poller.stop()
    assert poller._task.done()
