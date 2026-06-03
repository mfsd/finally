import asyncio
from collections.abc import Iterable

import httpx

from .base import MarketDataProvider

BASE_URL = "https://api.massive.com"


class MassiveMarketData(MarketDataProvider):
    """Fetches previous-close prices from the Massive REST API.

    Used to seed realistic starting prices for the GBM simulator when a
    MASSIVE_API_KEY is present. The full snapshot / intraday endpoints
    require a higher plan tier, so this provider fetches prev-close only.
    """

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
            self._client = None

    async def get_prices(self, tickers: Iterable[str]) -> dict[str, tuple[float, float]]:
        """Fetch previous-close prices for all tickers concurrently."""
        symbols = list(set(tickers))
        if not symbols:
            return {}
        assert self._client is not None, "call start() before get_prices()"
        results = await asyncio.gather(
            *[self._fetch_prev(sym) for sym in symbols],
            return_exceptions=True,
        )
        out: dict[str, tuple[float, float]] = {}
        for sym, result in zip(symbols, results):
            if isinstance(result, tuple):
                out[sym] = result
        return out

    async def _fetch_prev(self, ticker: str) -> tuple[float, float] | None:
        resp = await self._client.get(f"/v2/aggs/ticker/{ticker}/prev")
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        bar = results[0]
        price = bar.get("c")
        ts = bar.get("t", 0) / 1e3  # ms → seconds
        if price and price > 0:
            return (float(price), float(ts))
        return None

    def seed_price(self, ticker: str) -> float | None:
        return None  # async-only; seeding handled in factory

    async def validate_ticker(self, ticker: str) -> bool:
        assert self._client is not None
        resp = await self._client.get(f"/v2/aggs/ticker/{ticker}/prev")
        if resp.status_code != 200:
            return False
        data = resp.json()
        return bool((data.get("results") or []) and data.get("status") == "OK")

    async def fetch_seed_prices(self, tickers: list[str]) -> dict[str, float]:
        """Fetch prev-close prices for seeding the simulator. Returns {ticker: price}."""
        prices = await self.get_prices(tickers)
        return {ticker: price for ticker, (price, _) in prices.items()}
