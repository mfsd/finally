import json
import sqlite3
from typing import Any

from services.portfolio import get_portfolio, list_watchlist


def load_recent_messages(
    conn: sqlite3.Connection,
    user_id: str = "default",
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT role, content, actions, created_at
        FROM chat_messages
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    messages: list[dict[str, Any]] = []
    for row in reversed(rows):
        item = {
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        if row["actions"]:
            try:
                item["actions"] = json.loads(row["actions"])
            except json.JSONDecodeError:
                item["actions"] = row["actions"]
        messages.append(item)
    return messages


def load_portfolio_context(
    conn: sqlite3.Connection,
    price_cache: Any,
    user_id: str = "default",
) -> dict[str, Any]:
    portfolio = get_portfolio(conn, price_cache, user_id=user_id)
    return {
        **portfolio,
        "watchlist": list_watchlist(conn, price_cache, user_id=user_id),
    }
