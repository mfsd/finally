from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from market.stream import price_event_stream

router = APIRouter()


@router.get("/api/stream/prices")
async def stream_prices(request: Request) -> StreamingResponse:
    """SSE stream of live price updates for all tracked tickers."""
    cache = request.app.state.price_cache
    return StreamingResponse(
        price_event_stream(cache),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
