from datetime import date, timedelta
from collections.abc import Iterable

import httpx

from .base import MarketDataProvider
from .sim_engine import SimEngine

BASE_URL = "https://api.massive.com"
SNAPSHOT_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"
GROUPED_DAILY_PATH_TEMPLATE = "/v2/aggs/grouped/locale/us/market/stocks/{date}"
TICKER_OVERVIEW_PATH_TEMPLATE = "/v3/reference/tickers/{ticker}"


class MassiveEodSimulatorMarketData(MarketDataProvider):
    """Free-plan Massive provider: real EOD closes + simulated live movement.

    Massive Stocks Basic includes grouped daily OHLC and ticker reference data,
    but not stock snapshots or WebSockets. This provider uses one daily grouped
    request to seed all tracked symbols from real closes, then advances them
    locally with the same simulator used by the default mock market.
    """

    allow_fallback_seed = False

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._engine = SimEngine()
        self._eod_prices: dict[str, tuple[float, float]] = {}
        self._loaded_for: str | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=15.0,
        )

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_prices(self, tickers: Iterable[str]) -> dict[str, tuple[float, float]]:
        requested = {ticker.upper() for ticker in tickers}
        if not requested:
            return {}
        await self._ensure_eod_prices()
        seeded = set()
        for ticker in requested:
            baseline = self._eod_prices.get(ticker)
            if baseline:
                price, _ts = baseline
                self._engine.seed_at(ticker, price)
                seeded.add(ticker)
        stepped = self._engine.step(seeded)
        out: dict[str, tuple[float, float]] = {}
        for ticker, price in stepped.items():
            _baseline_price, ts = self._eod_prices[ticker]
            out[ticker] = (price, ts)
        return out

    def seed_price(self, ticker: str) -> float | None:
        baseline = self._eod_prices.get(ticker.upper())
        if not baseline:
            return None
        price, _ts = baseline
        return self._engine.seed_at(ticker.upper(), price)

    async def validate_ticker(self, ticker: str) -> bool:
        assert self._client is not None, "call start() before validate_ticker()"
        resp = await self._client.get(TICKER_OVERVIEW_PATH_TEMPLATE.format(ticker=ticker.upper()))
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        result = resp.json().get("results") or {}
        return result.get("ticker") == ticker.upper() and result.get("active", True) is True

    async def _ensure_eod_prices(self) -> None:
        today = date.today().isoformat()
        if self._loaded_for == today and self._eod_prices:
            return
        assert self._client is not None, "call start() before get_prices()"
        last_error: Exception | None = None
        for target in _candidate_market_dates(date.today()):
            resp = await self._client.get(
                GROUPED_DAILY_PATH_TEMPLATE.format(date=target.isoformat()),
                params={"adjusted": "true"},
            )
            if resp.status_code == 404:
                continue
            try:
                resp.raise_for_status()
            except Exception as exc:
                last_error = exc
                continue
            data = resp.json()
            rows = data.get("results") or []
            if not rows:
                continue
            self._eod_prices = _parse_grouped_daily(rows)
            self._loaded_for = today
            return
        if last_error:
            raise last_error
        raise RuntimeError("Massive grouped daily prices are not available for recent market dates")


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


def _candidate_market_dates(today: date) -> list[date]:
    """Recent weekdays, newest first. Handles weekends and most stale-data gaps."""
    out: list[date] = []
    current = today - timedelta(days=1)
    while len(out) < 7:
        if current.weekday() < 5:
            out.append(current)
        current -= timedelta(days=1)
    return out


def _parse_grouped_daily(rows: list[dict]) -> dict[str, tuple[float, float]]:
    prices: dict[str, tuple[float, float]] = {}
    for row in rows:
        ticker = row.get("T")
        close = row.get("c")
        ts = row.get("t")
        if isinstance(ticker, str) and isinstance(close, (int, float)) and close > 0:
            prices[ticker.upper()] = (float(close), (float(ts) / 1e3) if isinstance(ts, (int, float)) else 0.0)
    return prices


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
