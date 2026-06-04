import logging
from collections.abc import Iterable

from .base import MarketDataProvider

log = logging.getLogger("finally.market")


class FallbackMarketData(MarketDataProvider):
    """Use a primary provider when possible, with a simulator fallback.

    External market APIs can fail because of auth, quota, network, or plan
    limits. The workstation should still remain usable in those cases.
    """

    def __init__(self, primary: MarketDataProvider, fallback: MarketDataProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self._primary_failed = False

    @property
    def primary_failed(self) -> bool:
        return self._primary_failed

    async def start(self) -> None:
        await self.primary.start()
        await self.fallback.start()

    async def aclose(self) -> None:
        await self.primary.aclose()
        await self.fallback.aclose()

    async def get_prices(self, tickers: Iterable[str]) -> dict[str, tuple[float, float]]:
        requested = set(tickers)
        if not requested:
            return {}
        if self._primary_failed:
            return await self.fallback.get_prices(requested)
        try:
            prices = await self.primary.get_prices(requested)
        except Exception:
            self._primary_failed = True
            log.warning("primary market provider failed; using simulator fallback", exc_info=True)
            return await self.fallback.get_prices(requested)

        missing = requested.difference(prices)
        if missing:
            prices.update(await self.fallback.get_prices(missing))
        return prices

    def seed_price(self, ticker: str) -> float | None:
        primary_seed = self.primary.seed_price(ticker)
        if primary_seed is not None:
            return primary_seed
        if getattr(self.primary, "allow_fallback_seed", True) is False:
            return None
        return self.fallback.seed_price(ticker)

    async def validate_ticker(self, ticker: str) -> bool:
        if self._primary_failed:
            return await self.fallback.validate_ticker(ticker)
        try:
            if await self.primary.validate_ticker(ticker):
                return True
        except Exception:
            self._primary_failed = True
            log.warning("primary ticker validation failed; using simulator fallback", exc_info=True)
        return await self.fallback.validate_ticker(ticker)
