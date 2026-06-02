import httpx
from collections.abc import Iterable

from .base import MarketDataProvider

BASE_URL = "https://api.massive.com"
SNAPSHOT_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"


class MassiveMarketData(MarketDataProvider):
    """MarketDataProvider backed by the Massive (Polygon.io-compatible) REST API.

    Uses the filtered full-market snapshot endpoint to fetch all tracked
    tickers in a single request, respecting free-tier rate limits.
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
        symbols = ",".join(sorted(set(tickers)))
        if not symbols:
            return {}
        assert self._client is not None, "call start() before get_prices()"
        resp = await self._client.get(SNAPSHOT_PATH, params={"tickers": symbols})
        resp.raise_for_status()
        out: dict[str, tuple[float, float]] = {}
        for row in resp.json().get("tickers", []):
            sym = row.get("ticker")
            price = _resolve_price(row)
            if sym and price is not None:
                out[sym] = (price, _resolve_ts(row))
        return out

    def seed_price(self, ticker: str) -> float | None:
        return None

    async def validate_ticker(self, ticker: str) -> bool:
        result = await self.get_prices([ticker])
        return ticker in result


def _resolve_price(row: dict) -> float | None:
    """Extract the best available price from a snapshot row.

    Resolution order: lastTrade.p → min.c → day.c (first present wins).
    Returns None if no valid price is found.
    """
    for parent, child in (("lastTrade", "p"), ("min", "c"), ("day", "c")):
        val = (row.get(parent) or {}).get(child)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    return None


def _resolve_ts(row: dict) -> float:
    """Normalize timestamp to epoch seconds.

    lastTrade.t is Unix nanoseconds; min.t is Unix milliseconds.
    """
    lt = row.get("lastTrade") or {}
    if "t" in lt:
        return lt["t"] / 1e9
    mn = row.get("min") or {}
    if "t" in mn:
        return mn["t"] / 1e3
    return 0.0
