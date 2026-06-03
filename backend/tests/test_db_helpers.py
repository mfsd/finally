import pytest
import sqlite3
from db import get_connection, init_db, get_profile, update_cash, get_watchlist, \
    add_to_watchlist, remove_from_watchlist, ticker_in_watchlist, get_positions, \
    get_position, upsert_position, delete_position, record_trade, record_snapshot, \
    get_portfolio_history, save_message, get_recent_messages


@pytest.fixture
def db():
    conn = get_connection(":memory:")
    init_db(conn)
    return conn


def test_get_profile(db):
    p = get_profile(db)
    assert p["cash_balance"] == 10000.0
    assert p["id"] == "default"


def test_update_cash(db):
    update_cash(db, 9500.0)
    p = get_profile(db)
    assert p["cash_balance"] == 9500.0


def test_get_watchlist_seeded(db):
    wl = get_watchlist(db)
    tickers = [w["ticker"] for w in wl]
    assert "AAPL" in tickers
    assert len(tickers) == 10


def test_add_remove_watchlist(db):
    add_to_watchlist(db, "PYPL")
    assert ticker_in_watchlist(db, "PYPL")
    removed = remove_from_watchlist(db, "PYPL")
    assert removed
    assert not ticker_in_watchlist(db, "PYPL")


def test_add_duplicate_watchlist_raises(db):
    with pytest.raises(sqlite3.IntegrityError):
        add_to_watchlist(db, "AAPL")  # already seeded


def test_remove_nonexistent_returns_false(db):
    assert not remove_from_watchlist(db, "ZZZZ")


def test_positions_upsert_insert(db):
    upsert_position(db, "AAPL", 10.0, 190.0)
    pos = get_position(db, "AAPL")
    assert pos["quantity"] == 10.0
    assert pos["avg_cost"] == 190.0


def test_positions_upsert_update(db):
    upsert_position(db, "AAPL", 10.0, 190.0)
    upsert_position(db, "AAPL", 20.0, 195.0)
    pos = get_position(db, "AAPL")
    assert pos["quantity"] == 20.0
    assert pos["avg_cost"] == 195.0


def test_delete_position(db):
    upsert_position(db, "AAPL", 10.0, 190.0)
    delete_position(db, "AAPL")
    assert get_position(db, "AAPL") is None


def test_record_trade(db):
    trade_id = record_trade(db, "AAPL", "buy", 5.0, 190.0)
    assert trade_id is not None


def test_snapshot_and_history(db):
    record_snapshot(db, 10500.0)
    history = get_portfolio_history(db)
    assert len(history) >= 1
    assert history[0]["total_value"] == 10500.0


def test_save_and_get_messages(db):
    save_message(db, "user", "hello")
    save_message(db, "assistant", "hi there")
    msgs = get_recent_messages(db, limit=10)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
