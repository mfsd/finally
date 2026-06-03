import threading

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from db import (
    get_profile, get_positions, get_position, upsert_position, delete_position,
    record_trade, record_snapshot, get_portfolio_history, update_cash,
    ticker_in_watchlist, add_to_watchlist,
)

_trade_lock = threading.Lock()

router = APIRouter(prefix="/api")


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str


@router.get("/portfolio")
def get_portfolio(request: Request):
    db = request.app.state.db
    cache = request.app.state.price_cache

    profile = get_profile(db)
    cash = profile["cash_balance"]
    positions = get_positions(db)

    result_positions = []
    total_pos_value = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        quote = cache.get(ticker)
        if quote is None:
            continue
        price = quote.price
        session_open = quote.session_open
        unrealized_pnl = (price - pos["avg_cost"]) * pos["quantity"]
        pnl_pct = ((price - pos["avg_cost"]) / pos["avg_cost"] * 100) if pos["avg_cost"] > 0 else 0.0
        daily_change_pct = ((price - session_open) / session_open * 100) if session_open > 0 else 0.0
        total_pos_value += price * pos["quantity"]
        result_positions.append({
            "ticker": ticker,
            "quantity": pos["quantity"],
            "avg_cost": pos["avg_cost"],
            "current_price": price,
            "unrealized_pnl": unrealized_pnl,
            "pnl_pct": pnl_pct,
            "session_open": session_open,
            "daily_change_pct": daily_change_pct,
        })

    total_value = cash + total_pos_value
    total_pnl = total_value - 10000.0
    total_pnl_pct = (total_pnl / 10000.0) * 100

    return {
        "cash_balance": cash,
        "positions": result_positions,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
    }


@router.post("/portfolio/trade")
def execute_trade(trade: TradeRequest, request: Request):
    with _trade_lock:
        return _execute_trade_locked(trade, request)


def _execute_trade_locked(trade: TradeRequest, request: Request):
    db = request.app.state.db
    cache = request.app.state.price_cache
    provider = request.app.state.market_provider

    ticker = trade.ticker.upper().strip()
    quantity = trade.quantity
    side = trade.side.lower()

    if side not in ("buy", "sell"):
        raise HTTPException(status_code=422, detail="side must be 'buy' or 'sell'")
    if quantity <= 0:
        raise HTTPException(status_code=422, detail="quantity must be positive")

    quote = cache.get(ticker)
    if quote is None:
        raise HTTPException(status_code=422, detail="price not yet available for this ticker")

    price = quote.price
    profile = get_profile(db)
    cash = profile["cash_balance"]

    if side == "buy":
        cost = price * quantity
        if cash < cost:
            raise HTTPException(
                status_code=422,
                detail=f"insufficient cash: need ${cost:.2f}, have ${cash:.2f}",
            )
        existing = get_position(db, ticker)
        if existing:
            new_qty = existing["quantity"] + quantity
            new_avg = (existing["quantity"] * existing["avg_cost"] + quantity * price) / new_qty
        else:
            new_qty = quantity
            new_avg = price
        upsert_position(db, ticker, new_qty, new_avg)
        update_cash(db, cash - cost)
    else:
        existing = get_position(db, ticker)
        if existing is None or existing["quantity"] < quantity - 1e-9:
            held = existing["quantity"] if existing else 0.0
            raise HTTPException(
                status_code=422,
                detail=f"insufficient shares: need {quantity}, have {held:.4f}",
            )
        new_qty = existing["quantity"] - quantity
        if new_qty < 1e-6:
            delete_position(db, ticker)
        else:
            upsert_position(db, ticker, new_qty, existing["avg_cost"])
        update_cash(db, cash + price * quantity)

    trade_id = record_trade(db, ticker, side, quantity, price)

    if not ticker_in_watchlist(db, ticker):
        try:
            add_to_watchlist(db, ticker)
        except Exception:
            pass
        seed = provider.seed_price(ticker)
        if seed is not None:
            cache.seed(ticker, seed)

    # Snapshot after trade
    updated_profile = get_profile(db)
    new_cash = updated_profile["cash_balance"]
    all_positions = get_positions(db)
    total_val = new_cash
    for pos in all_positions:
        q = cache.get(pos["ticker"])
        if q:
            total_val += q.price * pos["quantity"]
    record_snapshot(db, total_val)

    updated_pos = get_position(db, ticker)
    position_out = None
    if updated_pos:
        position_out = {
            "ticker": ticker,
            "quantity": updated_pos["quantity"],
            "avg_cost": updated_pos["avg_cost"],
        }

    return {
        "success": True,
        "trade": {
            "id": trade_id,
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
        },
        "cash_balance": new_cash,
        "position": position_out,
    }


@router.get("/portfolio/history")
def portfolio_history(request: Request):
    db = request.app.state.db
    history = get_portfolio_history(db)
    return {
        "history": [
            {"total_value": h["total_value"], "recorded_at": h["recorded_at"]}
            for h in history
        ]
    }
