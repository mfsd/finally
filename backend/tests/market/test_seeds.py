import pytest
from market.seeds import seed_price, SEED_PRICES


def test_known_tickers_return_table_values():
    for ticker, expected in SEED_PRICES.items():
        assert seed_price(ticker) == expected


def test_unknown_ticker_is_in_50_to_300_range():
    for ticker in ("PYPL", "HOOD", "COIN", "ZM", "SNAP", "UBER", "LYFT", "ABNB"):
        price = seed_price(ticker)
        assert 50.0 <= price <= 300.0, f"{ticker}: {price} out of range"


def test_seed_price_is_deterministic():
    for ticker in ("PYPL", "HOOD", "XYZABC"):
        prices = [seed_price(ticker) for _ in range(10)]
        assert len(set(prices)) == 1, f"{ticker} produced non-deterministic prices"


def test_different_tickers_get_different_prices():
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"]
    prices = [seed_price(t) for t in tickers]
    assert len(set(prices)) > len(tickers) // 2, "Too many collisions"


def test_known_tickers_not_overridden_by_hash():
    assert seed_price("AAPL") == 190.0
    assert seed_price("NVDA") == 1180.0
    assert seed_price("NFLX") == 650.0


def test_single_char_ticker():
    price = seed_price("V")
    assert price == SEED_PRICES["V"]


def test_hash_unknown_ticker_returns_float():
    price = seed_price("NEWCO")
    assert isinstance(price, float)
