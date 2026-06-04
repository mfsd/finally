import sqlite3
from typing import Any

from fastapi import HTTPException
from services.portfolio import (
    add_watchlist_ticker,
    ensure_tradeable_ticker,
    execute_trade as execute_portfolio_trade,
    normalize_ticker,
    remove_watchlist_ticker,
)


async def execute_actions(
    conn: sqlite3.Connection,
    price_cache: Any,
    provider: Any,
    trades: list[dict[str, Any]],
    watchlist_changes: list[dict[str, Any]],
    user_id: str = "default",
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for change in watchlist_changes:
        try:
            results.append(await apply_watchlist_change(conn, price_cache, provider, change, user_id))
        except HTTPException as exc:
            errors.append({"action": "watchlist", "request": change, "error": _http_error(exc)})

    for trade in trades:
        try:
            result = await execute_portfolio_trade(
                conn,
                price_cache,
                provider,
                ticker=trade["ticker"],
                side=trade["side"],
                quantity=trade["quantity"],
                user_id=user_id,
            )
            results.append({"type": "trade", "status": "executed", **result})
        except HTTPException as exc:
            errors.append({"action": "trade", "request": trade, "error": _http_error(exc)})

    return {"results": results, "errors": errors}


async def apply_watchlist_change(
    conn: sqlite3.Connection,
    price_cache: Any,
    provider: Any,
    change: dict[str, Any],
    user_id: str = "default",
) -> dict[str, Any]:
    ticker = normalize_ticker(change["ticker"])
    action = change["action"]
    if action == "add":
        await ensure_tradeable_ticker(conn, price_cache, provider, ticker, user_id=user_id)
        add_watchlist_ticker(conn, ticker, user_id=user_id)
        return {"type": "watchlist", "action": "add", "ticker": ticker, "status": "ok"}
    if action == "remove":
        remove_watchlist_ticker(conn, ticker, user_id=user_id)
        return {
            "type": "watchlist",
            "action": "remove",
            "ticker": ticker,
            "status": "ok",
        }
    raise HTTPException(status_code=422, detail={"code": "invalid_action", "message": "Unsupported watchlist action."})


def _http_error(exc: HTTPException) -> Any:
    return exc.detail
