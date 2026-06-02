import time
import pytest
from market.cache import PriceCache


def test_first_insert_sets_session_open_and_prev_equal_to_price():
    cache = PriceCache()
    q = cache.update("AAPL", 190.0, ts=1000.0)
    assert q.price == 190.0
    assert q.prev_price == 190.0
    assert q.session_open == 190.0
    assert q.ts == 1000.0


def test_subsequent_update_rolls_prev_price():
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1000.0)
    q = cache.update("AAPL", 192.0, ts=1001.0)
    assert q.price == 192.0
    assert q.prev_price == 190.0
    assert q.session_open == 190.0


def test_session_open_is_preserved_across_many_updates():
    cache = PriceCache()
    cache.update("AAPL", 100.0, ts=1.0)
    cache.update("AAPL", 105.0, ts=2.0)
    cache.update("AAPL", 95.0, ts=3.0)
    q = cache.update("AAPL", 110.0, ts=4.0)
    assert q.session_open == 100.0
    assert q.prev_price == 95.0
    assert q.price == 110.0


def test_direction_correctly_computed():
    cache = PriceCache()
    cache.update("AAPL", 100.0, ts=1.0)
    up = cache.update("AAPL", 101.0, ts=2.0)
    assert up.direction == "up"
    down = cache.update("AAPL", 99.0, ts=3.0)
    assert down.direction == "down"
    flat = cache.update("AAPL", 99.0, ts=4.0)
    assert flat.direction == "flat"


def test_get_returns_none_for_unknown_ticker():
    cache = PriceCache()
    assert cache.get("UNKNOWN") is None


def test_get_returns_latest_quote():
    cache = PriceCache()
    cache.update("TSLA", 240.0, ts=1.0)
    cache.update("TSLA", 245.0, ts=2.0)
    q = cache.get("TSLA")
    assert q is not None
    assert q.price == 245.0


def test_snapshot_returns_copy():
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1.0)
    snap = cache.snapshot()
    assert "AAPL" in snap
    cache.update("AAPL", 200.0, ts=2.0)
    assert snap["AAPL"].price == 190.0


def test_snapshot_contains_all_tickers():
    cache = PriceCache()
    for ticker in ("AAPL", "GOOGL", "MSFT"):
        cache.update(ticker, 100.0, ts=1.0)
    snap = cache.snapshot()
    assert set(snap.keys()) == {"AAPL", "GOOGL", "MSFT"}


def test_seed_inserts_new_ticker():
    cache = PriceCache()
    q = cache.seed("PYPL", 75.0)
    assert q.price == 75.0
    assert q.session_open == 75.0
    assert q.prev_price == 75.0


def test_seed_is_noop_when_ticker_already_present():
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1.0)
    cache.update("AAPL", 195.0, ts=2.0)
    q = cache.seed("AAPL", 999.0)
    assert q.price == 195.0
    assert q.session_open == 190.0


def test_update_uses_current_time_when_ts_not_provided():
    cache = PriceCache()
    before = time.time()
    q = cache.update("AAPL", 190.0)
    after = time.time()
    assert before <= q.ts <= after


def test_multiple_tickers_are_independent():
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1.0)
    cache.update("GOOGL", 175.0, ts=1.0)
    cache.update("AAPL", 192.0, ts=2.0)
    aapl = cache.get("AAPL")
    googl = cache.get("GOOGL")
    assert aapl.session_open == 190.0
    assert googl.session_open == 175.0
    assert aapl.price == 192.0
    assert googl.price == 175.0
