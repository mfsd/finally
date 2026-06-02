import asyncio
import json
from collections.abc import AsyncIterator

from .cache import PriceCache

PUSH_INTERVAL = 0.5
HEARTBEAT_INTERVAL = 15


async def price_event_stream(
    cache: PriceCache,
    push_interval: float = PUSH_INTERVAL,
    heartbeat_interval: float = HEARTBEAT_INTERVAL,
) -> AsyncIterator[str]:
    """Yield SSE-formatted frames: periodic price snapshots + keepalive comments.

    Emits a 'prices' event every push_interval seconds containing all cached quotes.
    Emits a ': keepalive' comment every heartbeat_interval seconds so the client can
    detect a silently dropped connection.
    """
    loop = asyncio.get_event_loop()
    last_heartbeat = loop.time()
    while True:
        snap = cache.snapshot()
        if snap:
            payload = [q.to_event() for q in snap.values()]
            yield f"event: prices\ndata: {json.dumps(payload)}\n\n"

        now = loop.time()
        if now - last_heartbeat >= heartbeat_interval:
            yield ": keepalive\n\n"
            last_heartbeat = now

        await asyncio.sleep(push_interval)
