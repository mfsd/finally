import json
import pytest
import httpx
import respx
from market.massive import (
    BASE_URL,
    GROUPED_DAILY_PATH_TEMPLATE,
    SNAPSHOT_PATH,
    TICKER_OVERVIEW_PATH_TEMPLATE,
    MassiveEodSimulatorMarketData,
    MassiveMarketData,
    _parse_grouped_daily,
    _resolve_price,
    _resolve_ts,
)
from market.base import MarketDataProvider


def make_snapshot_response(tickers_data: list[dict]) -> dict:
    return {
        "status": "OK",
        "count": len(tickers_data),
        "tickers": tickers_data,
    }


def make_grouped_response(rows: list[dict]) -> dict:
    return {
        "status": "OK",
        "resultsCount": len(rows),
        "results": rows,
    }


AAPL_ROW_FULL = {
    "ticker": "AAPL",
    "lastTrade": {"p": 183.12, "t": 1605192894600000000},
    "min": {"c": 183.10, "t": 1605192894000},
    "day": {"c": 183.0},
    "prevDay": {"c": 181.7},
}

TSLA_ROW_NO_LAST_TRADE = {
    "ticker": "TSLA",
    "min": {"c": 242.55, "t": 1605192894000},
    "day": {"c": 242.0},
}

GOOGL_ROW_DAY_ONLY = {
    "ticker": "GOOGL",
    "day": {"c": 175.31},
}

EMPTY_ROW = {
    "ticker": "UNKNOWN",
}

GROUPED_ROWS = [
    {"T": "AAPL", "c": 310.26, "t": 1780516800000},
    {"T": "MSFT", "c": 468.11, "t": 1780516800000},
    {"T": "BAD", "c": 0, "t": 1780516800000},
]


# ---- _resolve_price unit tests ---------------------------------------------

class TestResolvePrice:
    def test_prefers_last_trade_price(self):
        assert _resolve_price(AAPL_ROW_FULL) == 183.12

    def test_falls_back_to_min_close(self):
        assert _resolve_price(TSLA_ROW_NO_LAST_TRADE) == 242.55

    def test_falls_back_to_day_close(self):
        assert _resolve_price(GOOGL_ROW_DAY_ONLY) == 175.31

    def test_returns_none_when_no_price(self):
        assert _resolve_price(EMPTY_ROW) is None

    def test_returns_none_for_empty_row(self):
        assert _resolve_price({}) is None

    def test_ignores_zero_or_negative_prices(self):
        row = {"lastTrade": {"p": 0}, "min": {"c": -1}, "day": {"c": 100.0}}
        assert _resolve_price(row) == 100.0

    def test_handles_null_nested_objects(self):
        row = {"lastTrade": None, "min": None, "day": {"c": 50.0}}
        assert _resolve_price(row) == 50.0

    def test_handles_missing_nested_keys(self):
        row = {"lastTrade": {"s": 100}, "min": {"v": 12345}, "day": {"c": 99.99}}
        assert _resolve_price(row) == 99.99


# ---- _resolve_ts unit tests -------------------------------------------------

class TestResolveTs:
    def test_uses_last_trade_nanoseconds(self):
        row = {"lastTrade": {"p": 183.12, "t": 1605192894600000000}}
        ts = _resolve_ts(row)
        assert abs(ts - 1605192894.6) < 1.0

    def test_falls_back_to_min_milliseconds(self):
        row = {"min": {"c": 183.0, "t": 1605192894000}}
        ts = _resolve_ts(row)
        assert abs(ts - 1605192894.0) < 1.0

    def test_returns_zero_when_no_timestamp(self):
        assert _resolve_ts({}) == 0.0

    def test_handles_null_last_trade(self):
        row = {"lastTrade": None, "min": {"c": 183.0, "t": 1605192894000}}
        ts = _resolve_ts(row)
        assert ts > 0


class TestGroupedDailyParsing:
    def test_parse_grouped_daily_uses_close_and_millisecond_timestamp(self):
        parsed = _parse_grouped_daily(GROUPED_ROWS)

        assert parsed["AAPL"] == (310.26, 1780516800.0)
        assert parsed["MSFT"] == (468.11, 1780516800.0)
        assert "BAD" not in parsed


# ---- MassiveMarketData integration tests -----------------------------------

@pytest.fixture
def provider():
    return MassiveMarketData(api_key="test-key")


def test_massive_is_market_data_provider(provider):
    assert isinstance(provider, MarketDataProvider)


def test_seed_price_always_none(provider):
    assert provider.seed_price("AAPL") is None
    assert provider.seed_price("ANYTHING") is None


@pytest.mark.asyncio
async def test_get_prices_returns_all_present_tickers(provider):
    response_data = make_snapshot_response([AAPL_ROW_FULL, TSLA_ROW_NO_LAST_TRADE])
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(SNAPSHOT_PATH).mock(
            return_value=httpx.Response(200, json=response_data)
        )
        await provider.start()
        prices = await provider.get_prices(["AAPL", "TSLA"])
        await provider.aclose()

    assert "AAPL" in prices
    price_aapl, ts_aapl = prices["AAPL"]
    assert price_aapl == 183.12
    assert ts_aapl > 0   # resolved from lastTrade.t nanoseconds
    assert "TSLA" in prices
    price_tsla, ts_tsla = prices["TSLA"]
    assert price_tsla == 242.55
    assert ts_tsla > 0   # resolved from min.t milliseconds


@pytest.mark.asyncio
async def test_get_prices_omits_tickers_with_no_price(provider):
    response_data = make_snapshot_response([AAPL_ROW_FULL, EMPTY_ROW])
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(SNAPSHOT_PATH).mock(
            return_value=httpx.Response(200, json=response_data)
        )
        await provider.start()
        prices = await provider.get_prices(["AAPL", "UNKNOWN"])
        await provider.aclose()

    assert "AAPL" in prices
    assert "UNKNOWN" not in prices


@pytest.mark.asyncio
async def test_get_prices_empty_tickers_returns_empty(provider):
    await provider.start()
    prices = await provider.get_prices([])
    await provider.aclose()
    assert prices == {}


@pytest.mark.asyncio
async def test_get_prices_unknown_symbol_omitted_from_response(provider):
    """When a symbol is completely absent from the API response, it is omitted."""
    response_data = make_snapshot_response([AAPL_ROW_FULL])
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(SNAPSHOT_PATH).mock(
            return_value=httpx.Response(200, json=response_data)
        )
        await provider.start()
        prices = await provider.get_prices(["AAPL", "FAKESYM"])
        await provider.aclose()

    assert "FAKESYM" not in prices
    assert "AAPL" in prices


@pytest.mark.asyncio
async def test_validate_ticker_returns_true_for_known_symbol(provider):
    response_data = make_snapshot_response([AAPL_ROW_FULL])
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(SNAPSHOT_PATH).mock(
            return_value=httpx.Response(200, json=response_data)
        )
        await provider.start()
        result = await provider.validate_ticker("AAPL")
        await provider.aclose()

    assert result is True


@pytest.mark.asyncio
async def test_validate_ticker_returns_false_for_unknown_symbol(provider):
    response_data = make_snapshot_response([])
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(SNAPSHOT_PATH).mock(
            return_value=httpx.Response(200, json=response_data)
        )
        await provider.start()
        result = await provider.validate_ticker("NOTREAL")
        await provider.aclose()

    assert result is False


@pytest.mark.asyncio
async def test_get_prices_raises_on_http_error(provider):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(SNAPSHOT_PATH).mock(return_value=httpx.Response(429))
        await provider.start()
        with pytest.raises(httpx.HTTPStatusError):
            await provider.get_prices(["AAPL"])
        await provider.aclose()


@pytest.mark.asyncio
async def test_get_prices_uses_bearer_auth(provider):
    response_data = make_snapshot_response([AAPL_ROW_FULL])
    captured_request = None

    async def capture(request, *args, **kwargs):
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=response_data)

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(SNAPSHOT_PATH).mock(side_effect=capture)
        await provider.start()
        await provider.get_prices(["AAPL"])
        await provider.aclose()

    assert captured_request is not None
    assert captured_request.headers["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_aclose_is_safe_to_call_multiple_times(provider):
    await provider.start()
    await provider.aclose()
    await provider.aclose()


@pytest.mark.asyncio
async def test_get_prices_deduplicates_ticker_list(provider):
    response_data = make_snapshot_response([AAPL_ROW_FULL])
    captured_params = None

    async def capture(request, *args, **kwargs):
        nonlocal captured_params
        captured_params = str(request.url)
        return httpx.Response(200, json=response_data)

    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(SNAPSHOT_PATH).mock(side_effect=capture)
        await provider.start()
        await provider.get_prices(["AAPL", "AAPL", "AAPL"])
        await provider.aclose()

    assert captured_params.count("AAPL") == 1


# ---- MassiveEodSimulatorMarketData tests -----------------------------------


@pytest.fixture
def eod_provider():
    return MassiveEodSimulatorMarketData(api_key="test-key")


def test_eod_provider_is_market_data_provider(eod_provider):
    assert isinstance(eod_provider, MarketDataProvider)


@pytest.mark.asyncio
async def test_eod_get_prices_uses_grouped_daily_summary(eod_provider):
    grouped_path = GROUPED_DAILY_PATH_TEMPLATE.format(date="2026-06-03")
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(grouped_path).mock(
            return_value=httpx.Response(200, json=make_grouped_response(GROUPED_ROWS))
        )
        await eod_provider.start()
        prices = await eod_provider.get_prices(["AAPL", "MSFT"])
        await eod_provider.aclose()

    assert set(prices) == {"AAPL", "MSFT"}
    assert abs(prices["AAPL"][0] - 310.26) < 2.0
    assert prices["AAPL"][1] == 1780516800.0


@pytest.mark.asyncio
async def test_eod_get_prices_caches_grouped_daily_summary(eod_provider):
    grouped_path = GROUPED_DAILY_PATH_TEMPLATE.format(date="2026-06-03")
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get(grouped_path).mock(
            return_value=httpx.Response(200, json=make_grouped_response(GROUPED_ROWS))
        )
        await eod_provider.start()
        await eod_provider.get_prices(["AAPL"])
        await eod_provider.get_prices(["MSFT"])
        await eod_provider.aclose()

    assert route.call_count == 1


@pytest.mark.asyncio
async def test_eod_validate_ticker_uses_reference_overview(eod_provider):
    path = TICKER_OVERVIEW_PATH_TEMPLATE.format(ticker="AAPL")
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(path).mock(
            return_value=httpx.Response(200, json={"status": "OK", "results": {"ticker": "AAPL", "active": True}})
        )
        await eod_provider.start()
        result = await eod_provider.validate_ticker("AAPL")
        await eod_provider.aclose()

    assert result is True


@pytest.mark.asyncio
async def test_eod_validate_ticker_returns_false_for_404(eod_provider):
    path = TICKER_OVERVIEW_PATH_TEMPLATE.format(ticker="NOPE")
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(path).mock(return_value=httpx.Response(404, json={"status": "NOT_FOUND"}))
        await eod_provider.start()
        result = await eod_provider.validate_ticker("NOPE")
        await eod_provider.aclose()

    assert result is False
