import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import os

DEFAULT_USER_ID = "default"
STARTING_CASH = 10000.0
ZERO_POSITION_EPSILON = 1e-6


def _default_db_path() -> str:
    """Resolve db/finally.db from both project-root and backend/container cwd."""
    env_path = os.environ.get("DB_PATH")
    if env_path:
        return env_path
    project_root = Path(__file__).resolve().parent.parent
    return str(project_root / "db" / "finally.db")


DB_PATH = _default_db_path()

DEFAULT_WATCHLIST = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users_profile (
    id           TEXT PRIMARY KEY,
    cash_balance REAL NOT NULL DEFAULT 10000.0 CHECK(cash_balance >= 0),
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id       TEXT PRIMARY KEY,
    user_id  TEXT NOT NULL DEFAULT 'default',
    ticker   TEXT NOT NULL,
    added_at TEXT NOT NULL,
    CHECK(length(ticker) BETWEEN 1 AND 10),
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL DEFAULT 'default',
    ticker     TEXT NOT NULL,
    quantity   REAL NOT NULL CHECK(quantity > 0),
    avg_cost   REAL NOT NULL CHECK(avg_cost >= 0),
    updated_at TEXT NOT NULL,
    CHECK(length(ticker) BETWEEN 1 AND 10),
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'default',
    ticker      TEXT NOT NULL,
    side        TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    quantity    REAL NOT NULL CHECK(quantity > 0),
    price       REAL NOT NULL CHECK(price >= 0),
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'default',
    total_value REAL NOT NULL CHECK(total_value >= 0),
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL DEFAULT 'default',
    role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    actions    TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_watchlist_user_ticker ON watchlist(user_id, ticker);
CREATE INDEX IF NOT EXISTS idx_positions_user_ticker ON positions(user_id, ticker);
CREATE INDEX IF NOT EXISTS idx_trades_user_executed_at ON trades(user_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_user_recorded_at ON portfolio_snapshots(user_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_chat_user_created_at ON chat_messages(user_id, created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _normalize_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized or len(normalized) > 10 or not normalized.isalpha():
        raise ValueError("ticker must be 1-10 alphabetic characters")
    return normalized


def _validate_positive(value: float, name: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite database at db_path."""
    db_path = db_path or _default_db_path()
    if db_path != ":memory:":
        Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create schema and seed default data if the database is empty."""
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _seed(conn)
    conn.commit()


def _seed(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?,?,?)",
        (DEFAULT_USER_ID, STARTING_CASH, _now()),
    )
    now = _now()
    for ticker in DEFAULT_WATCHLIST:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
        )


def get_user_profile(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM users_profile WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        now = _now()
        conn.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            (user_id, STARTING_CASH, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users_profile WHERE id = ?", (user_id,)).fetchone()
    return dict(row)


def update_cash_balance(
    conn: sqlite3.Connection,
    cash_balance: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    balance = float(cash_balance)
    if balance < 0:
        raise ValueError("cash_balance cannot be negative")
    get_user_profile(conn, user_id)
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (balance, user_id),
    )
    conn.commit()
    return get_user_profile(conn, user_id)


def list_watchlist(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_watchlist_tickers(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[str]:
    return [row["ticker"] for row in list_watchlist(conn, user_id)]


def add_watchlist_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    normalized = _normalize_ticker(ticker)
    now = _now()
    conn.execute(
        """
        INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), user_id, normalized, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, normalized),
    ).fetchone()
    return dict(row)


def remove_watchlist_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
) -> bool:
    normalized = _normalize_ticker(ticker)
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, normalized),
    )
    conn.commit()
    return cur.rowcount > 0


def get_position(
    conn: sqlite3.Connection,
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any] | None:
    normalized = _normalize_ticker(ticker)
    row = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, normalized),
    ).fetchone()
    return _row_to_dict(row)


def list_positions(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? ORDER BY ticker",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_position_for_trade(
    conn: sqlite3.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any] | None:
    normalized = _normalize_ticker(ticker)
    side = side.strip().lower()
    if side not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'")
    qty = _validate_positive(quantity, "quantity")
    fill_price = float(price)
    if fill_price < 0:
        raise ValueError("price cannot be negative")

    current = get_position(conn, normalized, user_id)
    now = _now()
    if side == "buy":
        if current is None:
            conn.execute(
                """
                INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), user_id, normalized, qty, fill_price, now),
            )
        else:
            old_qty = float(current["quantity"])
            old_cost = float(current["avg_cost"])
            new_qty = old_qty + qty
            new_avg = ((old_qty * old_cost) + (qty * fill_price)) / new_qty
            conn.execute(
                """
                UPDATE positions
                SET quantity = ?, avg_cost = ?, updated_at = ?
                WHERE user_id = ? AND ticker = ?
                """,
                (new_qty, new_avg, now, user_id, normalized),
            )
    else:
        if current is None:
            raise ValueError(f"no position exists for {normalized}")
        old_qty = float(current["quantity"])
        if qty - old_qty > ZERO_POSITION_EPSILON:
            raise ValueError(f"cannot sell {qty:g} shares of {normalized}; only {old_qty:g} available")
        new_qty = old_qty - qty
        if new_qty < ZERO_POSITION_EPSILON:
            conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, normalized),
            )
        else:
            conn.execute(
                """
                UPDATE positions SET quantity = ?, updated_at = ?
                WHERE user_id = ? AND ticker = ?
                """,
                (new_qty, now, user_id, normalized),
            )
    conn.commit()
    return get_position(conn, normalized, user_id)


def insert_trade(
    conn: sqlite3.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    normalized = _normalize_ticker(ticker)
    side = side.strip().lower()
    if side not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'")
    qty = _validate_positive(quantity, "quantity")
    fill_price = float(price)
    if fill_price < 0:
        raise ValueError("price cannot be negative")
    trade_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (trade_id, user_id, normalized, side, qty, fill_price, _now()),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone())


def list_trades(
    conn: sqlite3.Connection,
    user_id: str = DEFAULT_USER_ID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM trades
        WHERE user_id = ?
        ORDER BY executed_at DESC
        LIMIT ?
        """,
        (user_id, int(limit)),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_portfolio_snapshot(
    conn: sqlite3.Connection,
    total_value: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    value = float(total_value)
    if value < 0:
        raise ValueError("total_value cannot be negative")
    snapshot_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
        VALUES (?, ?, ?, ?)
        """,
        (snapshot_id, user_id, value, _now()),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM portfolio_snapshots WHERE id = ?", (snapshot_id,)).fetchone())


def list_portfolio_snapshots(
    conn: sqlite3.Connection,
    user_id: str = DEFAULT_USER_ID,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT * FROM portfolio_snapshots
            WHERE user_id = ?
            ORDER BY recorded_at DESC
            LIMIT ?
        ) ORDER BY recorded_at ASC
        """,
        (user_id, int(limit)),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_chat_message(
    conn: sqlite3.Connection,
    role: str,
    content: str,
    actions: Any | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    role = role.strip().lower()
    if role not in {"user", "assistant"}:
        raise ValueError("role must be 'user' or 'assistant'")
    actions_json = None if actions is None else json.dumps(actions, separators=(",", ":"))
    message_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (message_id, user_id, role, content, actions_json, _now()),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM chat_messages WHERE id = ?", (message_id,)).fetchone())


def list_chat_messages(
    conn: sqlite3.Connection,
    user_id: str = DEFAULT_USER_ID,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT * FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ) ORDER BY created_at ASC
        """,
        (user_id, int(limit)),
    ).fetchall()
    return [dict(row) for row in rows]


def get_tracked_symbols(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> set[str]:
    rows = conn.execute(
        """
        SELECT ticker FROM watchlist WHERE user_id = ?
        UNION
        SELECT ticker FROM positions WHERE user_id = ?
        """,
        (user_id, user_id),
    ).fetchall()
    return {row["ticker"] if isinstance(row, sqlite3.Row) else row[0] for row in rows}
