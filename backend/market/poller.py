import asyncio
import logging
from collections.abc import Callable

from .base import MarketDataProvider
from .cache import PriceCache

log = logging.getLogger("finally.market")


class MarketPoller:
    """Single background asyncio task that drives price updates into the cache.

    Calls provider.get_prices() on a regular cadence and writes results to the
    shared PriceCache. The tracked_set callable returns the union of watchlist
    and held positions — recomputed each poll so additions/removals take effect
    without restart.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        cache: PriceCache,
        tracked_set: Callable[[], set[str]],
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
            except Exception:
                log.exception("market poll failed")
            await asyncio.sleep(self._interval)
