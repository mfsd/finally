import json
import sqlite3
from datetime import datetime

import pytest

from db import (
    DEFAULT_WATCHLIST,
    STARTING_CASH,
    add_watchlist_ticker,
    get_connection,
    get_tracked_symbols,
    get_user_profile,
    init_db,
    insert_chat_message,
    insert_portfolio_snapshot,
    insert_trade,
    list_chat_messages,
    list_portfolio_snapshots,
    list_positions,
    list_watchlist,
    remove_watchlist_ticker,
    update_cash_balance,
    update_position_for_trade,
)


@pytest.fixture
def conn():
    db = get_connection(":memory:")
    init_db(db)
    return db


def assert_iso_utc(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_init_db_is_idempotent_and_seeds_exact_defaults(conn):
    init_db(conn)
    init_db(conn)

    profile = get_user_profile(conn)
    assert profile["id"] == "default"
    assert profile["cash_balance"] == STARTING_CASH
    assert_iso_utc(profile["created_at"])

    tickers = [row["ticker"] for row in list_watchlist(conn)]
    assert tickers == DEFAULT_WATCHLIST


def test_schema_constraints_reject_invalid_side_and_role(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
            VALUES ('bad-trade', 'default', 'AAPL', 'hold', 1, 100, '2026-01-01T00:00:00+00:00')
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO chat_messages (id, user_id, role, content, created_at)
            VALUES ('bad-chat', 'default', 'system', 'nope', '2026-01-01T00:00:00+00:00')
            """
        )


def test_watchlist_crud_normalizes_and_is_duplicate_safe(conn):
    row = add_watchlist_ticker(conn, " pypl ")
    duplicate = add_watchlist_ticker(conn, "PYPL")

    assert row["ticker"] == "PYPL"
    assert duplicate["id"] == row["id"]
    assert [r["ticker"] for r in list_watchlist(conn)].count("PYPL") == 1
    assert remove_watchlist_ticker(conn, "pypl") is True
    assert remove_watchlist_ticker(conn, "pypl") is False


def test_watchlist_rejects_malformed_ticker(conn):
    with pytest.raises(ValueError):
        add_watchlist_ticker(conn, "AAPL1")


def test_buy_updates_weighted_average_and_sell_deletes_near_zero_position(conn):
    first = update_position_for_trade(conn, "aapl", "buy", 2, 100)
    second = update_position_for_trade(conn, "AAPL", "buy", 1, 130)

    assert first["quantity"] == 2
    assert second["quantity"] == 3
    assert second["avg_cost"] == pytest.approx(110)

    remaining = update_position_for_trade(conn, "AAPL", "sell", 1.5, 99)
    assert remaining["quantity"] == pytest.approx(1.5)
    assert remaining["avg_cost"] == pytest.approx(110)

    closed = update_position_for_trade(conn, "AAPL", "sell", 1.5 - 1e-7, 101)
    assert closed is None
    assert list_positions(conn) == []


def test_position_sell_validation(conn):
    with pytest.raises(ValueError, match="no position"):
        update_position_for_trade(conn, "MSFT", "sell", 1, 100)

    update_position_for_trade(conn, "MSFT", "buy", 1, 100)
    with pytest.raises(ValueError, match="only 1"):
        update_position_for_trade(conn, "MSFT", "sell", 2, 100)


def test_trade_insert_and_cash_update(conn):
    trade = insert_trade(conn, "nvda", "BUY", 0.5, 1180)
    profile = update_cash_balance(conn, 9410)

    assert trade["ticker"] == "NVDA"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 0.5
    assert_iso_utc(trade["executed_at"])
    assert profile["cash_balance"] == 9410

    with pytest.raises(ValueError):
        update_cash_balance(conn, -1)


def test_snapshots_return_oldest_to_newest_with_limit(conn):
    insert_portfolio_snapshot(conn, 10000)
    insert_portfolio_snapshot(conn, 10010)
    insert_portfolio_snapshot(conn, 10020)

    rows = list_portfolio_snapshots(conn, limit=2)
    assert [row["total_value"] for row in rows] == [10010, 10020]
    assert all(row["user_id"] == "default" for row in rows)
    assert_iso_utc(rows[-1]["recorded_at"])


def test_chat_messages_persist_actions_and_cap_recent_history(conn):
    for i in range(25):
        insert_chat_message(conn, "user", f"message {i}")
    assistant = insert_chat_message(
        conn,
        "assistant",
        "Bought AAPL",
        actions={"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}]},
    )

    rows = list_chat_messages(conn, limit=20)
    assert len(rows) == 20
    assert rows[-1]["id"] == assistant["id"]
    assert json.loads(rows[-1]["actions"])["trades"][0]["ticker"] == "AAPL"
    assert rows[0]["content"] == "message 6"


def test_tracked_symbols_include_watchlist_and_held_positions(conn):
    remove_watchlist_ticker(conn, "TSLA")
    update_position_for_trade(conn, "TSLA", "buy", 2, 240)
    add_watchlist_ticker(conn, "PYPL")

    tracked = get_tracked_symbols(conn)
    assert "TSLA" in tracked
    assert "PYPL" in tracked
    assert set(DEFAULT_WATCHLIST) - {"TSLA"} < tracked
