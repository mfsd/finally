import re
import sqlite3
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from db import get_watchlist, add_to_watchlist, remove_from_watchlist

router = APIRouter(prefix="/api")

TICKER_RE = re.compile(r"^[A-Z0-9]{1,10}$")


class AddTickerRequest(BaseModel):
    ticker: str


@router.get("/watchlist")
def list_watchlist(request: Request):
    db = request.app.state.db
    cache = request.app.state.price_cache
    items = get_watchlist(db)
    result = []
    for item in items:
        ticker = item["ticker"]
        quote = cache.get(ticker)
        daily_chg = None
        if quote and quote.session_open and quote.session_open > 0:
            daily_chg = (quote.price - quote.session_open) / quote.session_open * 100
        result.append({
            "ticker": ticker,
            "price": quote.price if quote else None,
            "prev_price": quote.prev_price if quote else None,
            "session_open": quote.session_open if quote else None,
            "daily_change_pct": daily_chg,
        })
    return {"watchlist": result}


@router.post("/watchlist")
async def add_watchlist(body: AddTickerRequest, request: Request):
    db = request.app.state.db
    cache = request.app.state.price_cache
    provider = request.app.state.market_provider

    ticker = body.ticker.upper().strip()
    if not TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail="invalid ticker format")

    valid = await provider.validate_ticker(ticker)
    if not valid:
        raise HTTPException(status_code=400, detail=f"unknown ticker: {ticker}")

    added = False
    try:
        add_to_watchlist(db, ticker)
        added = True
        seed = provider.seed_price(ticker)
        if seed is not None:
            cache.seed(ticker, seed)
    except sqlite3.IntegrityError:
        pass  # idempotent

    return {"ticker": ticker, "added": added}


@router.delete("/watchlist/{ticker}", status_code=204)
def delete_watchlist(ticker: str, request: Request):
    db = request.app.state.db
    removed = remove_from_watchlist(db, ticker.upper().strip())
    if not removed:
        raise HTTPException(status_code=404, detail="ticker not found in watchlist")
