import sqlite3
import pytest
from market.tracked import get_tracked_symbols


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE watchlist (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            ticker TEXT NOT NULL
        );
        CREATE TABLE positions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            ticker TEXT NOT NULL,
            quantity REAL NOT NULL
        );
    """)
    return conn


def test_returns_empty_set_when_no_data(db):
    result = get_tracked_symbols(db)
    assert result == set()


def test_returns_watchlist_tickers(db):
    db.execute("INSERT INTO watchlist VALUES ('1', 'default', 'AAPL')")
    db.execute("INSERT INTO watchlist VALUES ('2', 'default', 'GOOGL')")
    result = get_tracked_symbols(db)
    assert result == {"AAPL", "GOOGL"}


def test_returns_position_tickers(db):
    db.execute("INSERT INTO positions VALUES ('1', 'default', 'TSLA', 10.0)")
    result = get_tracked_symbols(db)
    assert result == {"TSLA"}


def test_returns_union_of_watchlist_and_positions(db):
    db.execute("INSERT INTO watchlist VALUES ('1', 'default', 'AAPL')")
    db.execute("INSERT INTO positions VALUES ('1', 'default', 'TSLA', 5.0)")
    result = get_tracked_symbols(db)
    assert result == {"AAPL", "TSLA"}


def test_deduplicates_tickers_in_both_tables(db):
    db.execute("INSERT INTO watchlist VALUES ('1', 'default', 'AAPL')")
    db.execute("INSERT INTO positions VALUES ('1', 'default', 'AAPL', 3.0)")
    result = get_tracked_symbols(db)
    assert result == {"AAPL"}
    assert len(result) == 1


def test_filters_by_user_id(db):
    db.execute("INSERT INTO watchlist VALUES ('1', 'default', 'AAPL')")
    db.execute("INSERT INTO watchlist VALUES ('2', 'user2', 'GOOGL')")
    result = get_tracked_symbols(db, user_id="default")
    assert result == {"AAPL"}
    assert "GOOGL" not in result


def test_custom_user_id(db):
    db.execute("INSERT INTO watchlist VALUES ('1', 'alice', 'NVDA')")
    result = get_tracked_symbols(db, user_id="alice")
    assert result == {"NVDA"}


def test_held_but_unwatched_ticker_is_included(db):
    """A position ticker not on the watchlist still streams — this is the key invariant."""
    db.execute("INSERT INTO watchlist VALUES ('1', 'default', 'AAPL')")
    db.execute("INSERT INTO positions VALUES ('1', 'default', 'TSLA', 10.0)")
    # TSLA is held but NOT on watchlist
    result = get_tracked_symbols(db)
    assert "TSLA" in result
    assert "AAPL" in result
