from fastapi import APIRouter, Request, status
from pydantic import BaseModel

from services.portfolio import (
    add_watchlist_ticker,
    ensure_tradeable_ticker,
    list_watchlist,
    normalize_ticker,
    quote_to_json,
    remove_watchlist_ticker,
)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    ticker: str


@router.get("")
async def get_watchlist(request: Request) -> dict:
    return {"watchlist": list_watchlist(request.app.state.db, request.app.state.price_cache)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def post_watchlist(payload: WatchlistAddRequest, request: Request) -> dict:
    ticker = normalize_ticker(payload.ticker)
    quote = await ensure_tradeable_ticker(
        request.app.state.db,
        request.app.state.price_cache,
        request.app.state.market_provider,
        ticker,
    )
    row = add_watchlist_ticker(request.app.state.db, ticker)
    return {
        "item": {
            "id": row["id"],
            "ticker": row["ticker"],
            "added_at": row["added_at"],
            "quote": quote_to_json(quote),
        }
    }


@router.delete("/{ticker}")
async def delete_watchlist(ticker: str, request: Request) -> dict:
    symbol = normalize_ticker(ticker)
    remove_watchlist_ticker(request.app.state.db, symbol)
    return {"removed": symbol}
