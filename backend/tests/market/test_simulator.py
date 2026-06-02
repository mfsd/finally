import pytest
from market.simulator import SimulatorMarketData
from market.base import MarketDataProvider


@pytest.fixture
def sim():
    return SimulatorMarketData()


# ---- interface conformance --------------------------------------------------

def test_simulator_is_market_data_provider(sim):
    assert isinstance(sim, MarketDataProvider)


@pytest.mark.asyncio
async def test_get_prices_returns_all_tickers(sim):
    tickers = ["AAPL", "GOOGL", "MSFT"]
    prices = await sim.get_prices(tickers)
    assert set(prices.keys()) == set(tickers)


@pytest.mark.asyncio
async def test_get_prices_all_positive(sim):
    tickers = ["AAPL", "TSLA", "NVDA"]
    prices = await sim.get_prices(tickers)
    for ticker, (price, ts) in prices.items():
        assert price > 0, f"{ticker} has non-positive price: {price}"
        assert ts > 0, f"{ticker} has non-positive timestamp: {ts}"


@pytest.mark.asyncio
async def test_get_prices_empty_returns_empty(sim):
    prices = await sim.get_prices([])
    assert prices == {}


def test_seed_price_never_none(sim):
    for ticker in ("AAPL", "PYPL", "NEWCO", "Z"):
        assert sim.seed_price(ticker) is not None


def test_seed_price_deterministic(sim):
    p1 = sim.seed_price("PYPL")
    p2 = sim.seed_price("PYPL")
    assert p1 == p2


def test_seed_price_known_ticker(sim):
    assert sim.seed_price("AAPL") == 190.0


def test_seed_price_unknown_ticker_in_range(sim):
    price = sim.seed_price("XYZCO")
    assert 50.0 <= price <= 300.0


@pytest.mark.asyncio
async def test_validate_ticker_accepts_well_formed_symbols(sim):
    valid = ["AAPL", "A", "GOOGL", "TSLA", "BRK"]
    for ticker in valid:
        assert await sim.validate_ticker(ticker), f"{ticker} should be valid"


@pytest.mark.asyncio
async def test_validate_ticker_rejects_invalid_symbols(sim):
    invalid = ["", "TOOLONG", "123", "AA BB", "a1", "AAPL1"]
    for ticker in invalid:
        assert not await sim.validate_ticker(ticker), f"{ticker} should be invalid"


@pytest.mark.asyncio
async def test_start_and_aclose_are_noops(sim):
    await sim.start()
    await sim.aclose()


@pytest.mark.asyncio
async def test_prices_change_between_calls(sim):
    """Successive calls to get_prices advance the walk."""
    tickers = ["AAPL"]
    p1 = await sim.get_prices(tickers)
    p2 = await sim.get_prices(tickers)
    # Prices should differ (with overwhelming probability using non-zero vol)
    assert p1["AAPL"][0] != p2["AAPL"][0]
