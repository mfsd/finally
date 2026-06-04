import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from market.cache import PriceCache
from market.base import MarketDataProvider
from market.types import Quote

DEFAULT_USER_ID = "default"
POSITION_EPSILON = 1e-6


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_ticker(ticker: str) -> str:
    symbol = ticker.strip().upper()
    if not symbol.isalpha() or not 1 <= len(symbol) <= 6:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_ticker", "message": "Ticker must be 1-6 letters."},
        )
    return symbol


def validate_quantity(quantity: float) -> float:
    if quantity <= 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_quantity", "message": "Quantity must be greater than zero."},
        )
    return quantity


def quote_to_json(quote: Quote | None) -> dict | None:
    return quote.to_event() if quote else None


async def ensure_tradeable_ticker(
    conn: sqlite3.Connection,
    cache: PriceCache,
    provider: MarketDataProvider,
    ticker: str,
    *,
    user_id: str = DEFAULT_USER_ID,
    add_to_watchlist: bool = True,
) -> Quote | None:
    """Validate ticker and seed simulator prices; optionally ensure watchlist row exists."""
    ticker = normalize_ticker(ticker)
    if not await provider.validate_ticker(ticker):
        raise HTTPException(
            status_code=400,
            detail={"code": "unknown_ticker", "message": f"Ticker {ticker} is not available."},
        )

    if add_to_watchlist:
        add_watchlist_ticker(conn, ticker, user_id=user_id)
    quote = cache.get(ticker)
    if quote is None:
        seed = provider.seed_price(ticker)
        if seed is not None:
            quote = cache.seed(ticker, seed)
    return quote


def add_watchlist_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> sqlite3.Row:
    ticker = normalize_ticker(ticker)
    row = _ensure_watchlist_ticker_no_commit(conn, ticker, user_id=user_id)
    conn.commit()
    return row


def _ensure_watchlist_ticker_no_commit(
    conn: sqlite3.Connection,
    ticker: str,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> sqlite3.Row:
    existing = conn.execute(
        "SELECT id, user_id, ticker, added_at FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    if existing:
        return existing

    conn.execute(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, ticker, now_iso()),
    )
    return conn.execute(
        "SELECT id, user_id, ticker, added_at FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()


def remove_watchlist_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    ticker = normalize_ticker(ticker)
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail={"code": "watchlist_not_found", "message": f"Ticker {ticker} is not in the watchlist."},
        )


def list_watchlist(conn: sqlite3.Connection, cache: PriceCache, *, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, ticker, added_at
        FROM watchlist
        WHERE user_id = ?
        ORDER BY added_at ASC, ticker ASC
        """,
        (user_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "ticker": row["ticker"],
            "added_at": row["added_at"],
            "quote": quote_to_json(cache.get(row["ticker"])),
        }
        for row in rows
    ]


def get_cash_balance(conn: sqlite3.Connection, *, user_id: str = DEFAULT_USER_ID) -> float:
    row = conn.execute("SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(
            status_code=500,
            detail={"code": "profile_missing", "message": "Default user profile is missing."},
        )
    return float(row["cash_balance"])


def list_positions(conn: sqlite3.Connection, cache: PriceCache, *, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, ticker, quantity, avg_cost, updated_at
        FROM positions
        WHERE user_id = ?
        ORDER BY ticker ASC
        """,
        (user_id,),
    ).fetchall()
    positions = []
    for row in rows:
        quote = cache.get(row["ticker"])
        current_price = quote.price if quote else None
        valuation_price = current_price if current_price is not None else float(row["avg_cost"])
        quantity = float(row["quantity"])
        avg_cost = float(row["avg_cost"])
        market_value = quantity * valuation_price
        cost_basis = quantity * avg_cost
        unrealized_pl = market_value - cost_basis
        unrealized_pl_pct = (unrealized_pl / cost_basis) if cost_basis else 0.0
        positions.append(
            {
                "id": row["id"],
                "ticker": row["ticker"],
                "quantity": quantity,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "market_value": market_value,
                "cost_basis": cost_basis,
                "unrealized_pl": unrealized_pl,
                "unrealized_pl_pct": unrealized_pl_pct,
                "updated_at": row["updated_at"],
                "quote": quote_to_json(quote),
            }
        )
    return positions


def get_portfolio(conn: sqlite3.Connection, cache: PriceCache, *, user_id: str = DEFAULT_USER_ID) -> dict:
    cash = get_cash_balance(conn, user_id=user_id)
    positions = list_positions(conn, cache, user_id=user_id)
    positions_value = sum(p["market_value"] for p in positions)
    cost_basis = sum(p["cost_basis"] for p in positions)
    unrealized_pl = sum(p["unrealized_pl"] for p in positions)
    return {
        "cash_balance": cash,
        "positions_value": positions_value,
        "total_value": cash + positions_value,
        "unrealized_pl": unrealized_pl,
        "unrealized_pl_pct": (unrealized_pl / cost_basis) if cost_basis else 0.0,
        "positions": positions,
    }


async def execute_trade(
    conn: sqlite3.Connection,
    cache: PriceCache,
    provider: MarketDataProvider,
    *,
    ticker: str,
    side: str,
    quantity: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    ticker = normalize_ticker(ticker)
    side = side.strip().lower()
    if side not in {"buy", "sell"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_side", "message": "Side must be 'buy' or 'sell'."},
        )
    quantity = validate_quantity(float(quantity))

    quote = await ensure_tradeable_ticker(
        conn,
        cache,
        provider,
        ticker,
        user_id=user_id,
        add_to_watchlist=False,
    )
    if quote is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "price_not_available", "message": f"Price for {ticker} is not yet available."},
        )

    price = float(quote.price)
    now = now_iso()
    cash = get_cash_balance(conn, user_id=user_id)
    existing = conn.execute(
        "SELECT id, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    held_quantity = float(existing["quantity"]) if existing else 0.0
    avg_cost = float(existing["avg_cost"]) if existing else 0.0
    gross_amount = quantity * price

    if side == "buy":
        if gross_amount > cash + 1e-9:
            raise HTTPException(
                status_code=400,
                detail={"code": "insufficient_cash", "message": "Insufficient cash for buy order."},
            )
        new_quantity = held_quantity + quantity
        new_avg_cost = ((held_quantity * avg_cost) + gross_amount) / new_quantity
        new_cash = cash - gross_amount
    else:
        if quantity > held_quantity + POSITION_EPSILON:
            raise HTTPException(
                status_code=400,
                detail={"code": "insufficient_shares", "message": "Insufficient shares for sell order."},
            )
        new_quantity = held_quantity - quantity
        new_avg_cost = avg_cost
        new_cash = cash + gross_amount

    try:
        conn.execute("BEGIN")
        _ensure_watchlist_ticker_no_commit(conn, ticker, user_id=user_id)
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (new_cash, user_id),
        )
        if side == "buy":
            conn.execute(
                """
                INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, ticker)
                DO UPDATE SET quantity = excluded.quantity, avg_cost = excluded.avg_cost, updated_at = excluded.updated_at
                """,
                (str(uuid.uuid4()), user_id, ticker, new_quantity, new_avg_cost, now),
            )
        elif new_quantity < POSITION_EPSILON:
            conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
            new_quantity = 0.0
        else:
            conn.execute(
                "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE user_id = ? AND ticker = ?",
                (new_quantity, new_avg_cost, now, user_id, ticker),
            )
        trade_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade_id, user_id, ticker, side, quantity, price, now),
        )
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, _portfolio_total_in_transaction(conn, cache, user_id=user_id), now),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "trade": {
            "id": trade_id,
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "gross_amount": gross_amount,
            "executed_at": now,
        },
        "cash_balance": new_cash,
        "position": get_position(conn, cache, ticker, user_id=user_id),
        "portfolio": get_portfolio(conn, cache, user_id=user_id),
    }


def get_position(
    conn: sqlite3.Connection,
    cache: PriceCache,
    ticker: str,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> dict | None:
    ticker = normalize_ticker(ticker)
    row = conn.execute(
        "SELECT id, ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    if row is None:
        return None
    return next(p for p in list_positions(conn, cache, user_id=user_id) if p["ticker"] == ticker)


def _portfolio_total_in_transaction(
    conn: sqlite3.Connection,
    cache: PriceCache,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> float:
    cash = get_cash_balance(conn, user_id=user_id)
    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    total = cash
    for row in rows:
        quote = cache.get(row["ticker"])
        price = quote.price if quote else float(row["avg_cost"])
        total += float(row["quantity"]) * price
    return total


def get_portfolio_history(
    conn: sqlite3.Connection,
    *,
    user_id: str = DEFAULT_USER_ID,
    limit: int = 1000,
) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    rows = conn.execute(
        """
        SELECT id, total_value, recorded_at
        FROM portfolio_snapshots
        WHERE user_id = ? AND recorded_at >= ?
        ORDER BY recorded_at DESC
        LIMIT ?
        """,
        (user_id, since, limit),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "total_value": float(row["total_value"]),
            "recorded_at": row["recorded_at"],
        }
        for row in reversed(rows)
    ]
