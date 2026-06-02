import sqlite3


def get_tracked_symbols(db: sqlite3.Connection, user_id: str = "default") -> set[str]:
    """Return the union of watchlist tickers and held-position tickers.

    This is the set the poller tracks — held-but-unwatched tickers keep
    streaming so portfolio math and the header total stay current.
    """
    rows = db.execute(
        """
        SELECT ticker FROM watchlist WHERE user_id = ?
        UNION
        SELECT ticker FROM positions WHERE user_id = ?
        """,
        (user_id, user_id),
    ).fetchall()
    return {r[0] for r in rows}
