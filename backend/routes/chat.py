from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from chat.service import handle_chat


router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


@router.post("/api/chat")
async def chat(request: Request, payload: ChatRequest) -> dict:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not initialized.")
    price_cache = getattr(request.app.state, "price_cache", None)
    provider = getattr(request.app.state, "market_provider", None)
    try:
        return await handle_chat(db, price_cache, provider, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
