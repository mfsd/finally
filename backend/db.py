import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

_db_lock = threading.Lock()

DB_PATH = os.environ.get("DB_PATH", "db/finally.db")

DEFAULT_WATCHLIST = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users_profile (
    id           TEXT PRIMARY KEY,
    cash_balance REAL NOT NULL DEFAULT 10000.0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id       TEXT PRIMARY KEY,
    user_id  TEXT NOT NULL DEFAULT 'default',
    ticker   TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL DEFAULT 'default',
    ticker     TEXT NOT NULL,
    quantity   REAL NOT NULL,
    avg_cost   REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'default',
    ticker      TEXT NOT NULL,
    side        TEXT NOT NULL,
    quantity    REAL NOT NULL,
    price       REAL NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'default',
    total_value REAL NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL DEFAULT 'default',
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    actions    TEXT,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open (or create) the SQLite database at db_path."""
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL mode allows concurrent reads while a write is in progress
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create schema and seed default data if the database is empty."""
    conn.executescript(_SCHEMA)
    _seed(conn)
    conn.commit()


def _seed(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?,?,?)",
        ("default", 10000.0, _now()),
    )
    existing = conn.execute(
        "SELECT COUNT(*) FROM watchlist WHERE user_id = 'default'"
    ).fetchone()[0]
    if existing == 0:
        now = _now()
        for ticker in DEFAULT_WATCHLIST:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?,?,?,?)",
                (str(uuid.uuid4()), "default", ticker, now),
            )


# ─── User profile ────────────────────────────────────────────────────────────

def get_profile(conn: sqlite3.Connection) -> sqlite3.Row:
    return conn.execute(
        "SELECT * FROM users_profile WHERE id = 'default'"
    ).fetchone()


def update_cash(conn: sqlite3.Connection, new_balance: float) -> None:
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = 'default'",
        (new_balance,)
    )
    conn.commit()


# ─── Watchlist ────────────────────────────────────────────────────────────────

def get_watchlist(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT * FROM watchlist WHERE user_id = 'default' ORDER BY added_at"
    ).fetchall()


def add_to_watchlist(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row:
    row_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', ?, ?)",
        (row_id, ticker, _now()),
    )
    conn.commit()
    return conn.execute("SELECT * FROM watchlist WHERE id = ?", (row_id,)).fetchone()


def remove_from_watchlist(conn: sqlite3.Connection, ticker: str) -> bool:
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = 'default' AND ticker = ?", (ticker,)
    )
    conn.commit()
    return cur.rowcount > 0


def ticker_in_watchlist(conn: sqlite3.Connection, ticker: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM watchlist WHERE user_id = 'default' AND ticker = ?", (ticker,)
    ).fetchone()
    return row is not None


# ─── Positions ────────────────────────────────────────────────────────────────

def get_positions(conn: sqlite3.Connection) -> list:
    return conn.execute(
        "SELECT * FROM positions WHERE user_id = 'default'"
    ).fetchall()


def get_position(conn: sqlite3.Connection, ticker: str):
    return conn.execute(
        "SELECT * FROM positions WHERE user_id = 'default' AND ticker = ?", (ticker,)
    ).fetchone()


def upsert_position(conn: sqlite3.Connection, ticker: str, quantity: float, avg_cost: float) -> None:
    existing = get_position(conn, ticker)
    if existing:
        conn.execute(
            "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
            "WHERE user_id = 'default' AND ticker = ?",
            (quantity, avg_cost, _now(), ticker),
        )
    else:
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, 'default', ?, ?, ?, ?)",
            (str(uuid.uuid4()), ticker, quantity, avg_cost, _now()),
        )
    conn.commit()


def delete_position(conn: sqlite3.Connection, ticker: str) -> None:
    conn.execute(
        "DELETE FROM positions WHERE user_id = 'default' AND ticker = ?", (ticker,)
    )
    conn.commit()


# ─── Trades ───────────────────────────────────────────────────────────────────

def record_trade(
    conn: sqlite3.Connection, ticker: str, side: str, quantity: float, price: float
) -> str:
    trade_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, 'default', ?, ?, ?, ?, ?)",
        (trade_id, ticker, side, quantity, price, _now()),
    )
    conn.commit()
    return trade_id


# ─── Portfolio snapshots ──────────────────────────────────────────────────────

def record_snapshot(conn: sqlite3.Connection, total_value: float) -> None:
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, 'default', ?, ?)",
        (str(uuid.uuid4()), total_value, _now()),
    )
    conn.commit()


def get_portfolio_history(
    conn: sqlite3.Connection, hours: int = 24, max_points: int = 1000
) -> list:
    return conn.execute(
        """
        SELECT total_value, recorded_at FROM portfolio_snapshots
        WHERE user_id = 'default'
          AND recorded_at >= datetime('now', ?)
        ORDER BY recorded_at DESC
        LIMIT ?
        """,
        (f"-{hours} hours", max_points),
    ).fetchall()


# ─── Chat messages ────────────────────────────────────────────────────────────

def save_message(
    conn: sqlite3.Connection, role: str, content: str, actions: str | None = None
) -> None:
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, 'default', ?, ?, ?, ?)",
        (str(uuid.uuid4()), role, content, actions, _now()),
    )
    conn.commit()


def get_recent_messages(conn: sqlite3.Connection, limit: int = 20) -> list:
    rows = conn.execute(
        "SELECT role, content FROM chat_messages "
        "WHERE user_id = 'default' ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return list(reversed(rows))
