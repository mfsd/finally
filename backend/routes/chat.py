import json
import os
import re
import sqlite3
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api")

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


class _TradeAction(BaseModel):
    ticker: str
    side: str
    quantity: float


class _WatchlistChange(BaseModel):
    ticker: str
    action: str


class _ChatResponseSchema(BaseModel):
    message: str
    trades: list[_TradeAction] = []
    watchlist_changes: list[_WatchlistChange] = []


class ChatRequest(BaseModel):
    message: str


def _portfolio_context(db, cache) -> str:
    from db import get_profile, get_positions, get_watchlist
    profile = get_profile(db)
    cash = profile["cash_balance"]
    positions = get_positions(db)
    watchlist = get_watchlist(db)

    total_pos = 0.0
    pos_lines = []
    for p in positions:
        q = cache.get(p["ticker"])
        price = q.price if q else p["avg_cost"]
        pnl = (price - p["avg_cost"]) * p["quantity"]
        pnl_pct = (price - p["avg_cost"]) / p["avg_cost"] * 100 if p["avg_cost"] > 0 else 0
        total_pos += price * p["quantity"]
        pos_lines.append(
            f"  {p['ticker']}: {p['quantity']} shares, avg ${p['avg_cost']:.2f}, "
            f"price ${price:.2f}, P&L ${pnl:+.2f} ({pnl_pct:+.2f}%)"
        )

    total_value = cash + total_pos
    total_pnl = total_value - 10000.0
    wl = [w["ticker"] for w in watchlist]

    return "\n".join([
        f"Cash: ${cash:.2f}",
        f"Portfolio Value: ${total_value:.2f}",
        f"Total P&L: ${total_pnl:+.2f}",
        f"Positions ({len(positions)}):",
        *pos_lines,
        f"Watchlist: {', '.join(wl)}",
    ])


def _execute_trade_internal(db, cache, provider, ticker: str, side: str, quantity: float) -> dict:
    from db import (
        get_profile, get_position, upsert_position, delete_position,
        update_cash, record_trade, ticker_in_watchlist, add_to_watchlist,
    )
    quote = cache.get(ticker)
    if quote is None:
        return {"ticker": ticker, "side": side, "quantity": quantity, "success": False, "error": "price not available"}
    price = quote.price
    profile = get_profile(db)
    cash = profile["cash_balance"]
    try:
        if side == "buy":
            cost = price * quantity
            if cash < cost:
                return {"ticker": ticker, "side": side, "quantity": quantity, "success": False,
                        "error": f"insufficient cash (need ${cost:.2f})"}
            existing = get_position(db, ticker)
            if existing:
                new_qty = existing["quantity"] + quantity
                new_avg = (existing["quantity"] * existing["avg_cost"] + quantity * price) / new_qty
            else:
                new_qty, new_avg = quantity, price
            upsert_position(db, ticker, new_qty, new_avg)
            update_cash(db, cash - cost)
        else:
            existing = get_position(db, ticker)
            if existing is None or existing["quantity"] < quantity - 1e-9:
                return {"ticker": ticker, "side": side, "quantity": quantity, "success": False,
                        "error": "insufficient shares"}
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
                seed = provider.seed_price(ticker)
                if seed is not None:
                    cache.seed(ticker, seed)
            except sqlite3.IntegrityError:
                pass
        return {"ticker": ticker, "side": side, "quantity": quantity, "price": price, "success": True}
    except Exception as e:
        return {"ticker": ticker, "side": side, "quantity": quantity, "success": False, "error": str(e)}


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    from db import get_recent_messages, save_message, get_positions, get_profile, record_snapshot, add_to_watchlist, remove_from_watchlist
    db = request.app.state.db
    cache = request.app.state.price_cache
    provider = request.app.state.market_provider

    api_key = os.environ.get("OPENROUTER_API_KEY")
    mock_mode = os.environ.get("LLM_MOCK", "").lower() == "true"

    if not mock_mode and not api_key:
        raise HTTPException(status_code=503, detail="LLM not configured: OPENROUTER_API_KEY missing")

    context = _portfolio_context(db, cache)
    history = get_recent_messages(db, limit=20)

    system_prompt = (
        "You are FinAlly, an AI trading assistant for a simulated portfolio. "
        "The user started with $10,000 virtual capital. "
        "Analyze the portfolio, suggest and execute trades when asked, manage the watchlist. "
        "Be concise and data-driven. "
        "Always respond with valid JSON matching this exact schema: "
        '{"message": "string", "trades": [{"ticker": "string", "side": "buy|sell", "quantity": number}], '
        '"watchlist_changes": [{"ticker": "string", "action": "add|remove"}]}. '
        "trades and watchlist_changes may be empty arrays."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Current portfolio:\n{context}"},
    ]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": body.message})

    save_message(db, "user", body.message)

    if mock_mode:
        parsed = _ChatResponseSchema(
            message="Mock response: I can see your portfolio. No trades executed.",
            trades=[],
            watchlist_changes=[],
        )
    else:
        os.environ["OPENROUTER_API_KEY"] = api_key
        try:
            from litellm import completion
            response = completion(
                model=MODEL,
                messages=messages,
                response_format=_ChatResponseSchema,
                reasoning_effort="low",
                extra_body=EXTRA_BODY,
            )
            content = response.choices[0].message.content
            try:
                parsed = _ChatResponseSchema.model_validate_json(content)
            except Exception:
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    parsed = _ChatResponseSchema.model_validate_json(match.group())
                else:
                    parsed = _ChatResponseSchema(message=content, trades=[], watchlist_changes=[])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")

    ticker_upper = lambda t: t.upper().strip()

    trades_executed, trades_failed = [], []
    for t in parsed.trades:
        result = _execute_trade_internal(db, cache, provider, ticker_upper(t.ticker), t.side.lower(), t.quantity)
        (trades_executed if result["success"] else trades_failed).append(result)

    wl_results = []
    for change in parsed.watchlist_changes:
        ticker = ticker_upper(change.ticker)
        action = change.action.lower()
        try:
            if action == "add":
                try:
                    add_to_watchlist(db, ticker)
                    seed = provider.seed_price(ticker)
                    if seed is not None:
                        cache.seed(ticker, seed)
                    wl_results.append({"ticker": ticker, "action": action, "success": True})
                except sqlite3.IntegrityError:
                    wl_results.append({"ticker": ticker, "action": action, "success": True})
            elif action == "remove":
                removed = remove_from_watchlist(db, ticker)
                wl_results.append({"ticker": ticker, "action": action, "success": removed})
        except Exception as e:
            wl_results.append({"ticker": ticker, "action": action, "success": False, "error": str(e)})

    if trades_executed:
        updated = get_profile(db)
        new_cash = updated["cash_balance"]
        all_pos = get_positions(db)
        total_val = new_cash
        for pos in all_pos:
            q = cache.get(pos["ticker"])
            if q:
                total_val += q.price * pos["quantity"]
        record_snapshot(db, total_val)

    actions_json = json.dumps({
        "trades_executed": trades_executed,
        "trades_failed": trades_failed,
        "watchlist_changes": wl_results,
    })
    save_message(db, "assistant", parsed.message, actions=actions_json)

    return {
        "message": parsed.message,
        "trades_executed": trades_executed,
        "trades_failed": trades_failed,
        "watchlist_changes": wl_results,
    }
