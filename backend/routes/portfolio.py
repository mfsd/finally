from fastapi import APIRouter, Request
from pydantic import BaseModel

from services.portfolio import execute_trade, get_portfolio, get_portfolio_history

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str
    side: str
    quantity: float


@router.get("")
async def read_portfolio(request: Request) -> dict:
    return {"portfolio": get_portfolio(request.app.state.db, request.app.state.price_cache)}


@router.post("/trade")
async def post_trade(payload: TradeRequest, request: Request) -> dict:
    return await execute_trade(
        request.app.state.db,
        request.app.state.price_cache,
        request.app.state.market_provider,
        ticker=payload.ticker,
        side=payload.side,
        quantity=payload.quantity,
    )


@router.get("/history")
async def read_portfolio_history(request: Request) -> dict:
    return {"history": get_portfolio_history(request.app.state.db)}
