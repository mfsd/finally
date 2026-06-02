import asyncio
import json
import pytest

from market.cache import PriceCache
from market.stream import price_event_stream, PUSH_INTERVAL, HEARTBEAT_INTERVAL

# Use short intervals in all tests to keep the suite fast.
FAST_PUSH = 0.05
FAST_HEARTBEAT = 9999.0  # effectively never fires unless explicitly tested


async def collect_frames(cache: PriceCache, n: int, **kwargs) -> list[str]:
    """Collect up to n frames from the SSE stream."""
    frames = []
    async for frame in price_event_stream(cache, **kwargs):
        frames.append(frame)
        if len(frames) >= n:
            break
    return frames


@pytest.mark.asyncio
async def test_stream_emits_prices_event():
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1000.0)

    frames = await asyncio.wait_for(
        collect_frames(cache, 1, push_interval=FAST_PUSH, heartbeat_interval=FAST_HEARTBEAT),
        timeout=2.0,
    )
    assert len(frames) == 1
    assert frames[0].startswith("event: prices\n")


@pytest.mark.asyncio
async def test_prices_event_data_is_valid_json():
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1000.0)
    cache.update("GOOGL", 175.0, ts=1000.0)

    frames = await asyncio.wait_for(
        collect_frames(cache, 1, push_interval=FAST_PUSH, heartbeat_interval=FAST_HEARTBEAT),
        timeout=2.0,
    )
    data_line = [line for line in frames[0].split("\n") if line.startswith("data:")][0]
    payload = json.loads(data_line[len("data: "):])
    assert isinstance(payload, list)
    assert len(payload) == 2


@pytest.mark.asyncio
async def test_prices_event_has_correct_shape():
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1000.0)

    frames = await asyncio.wait_for(
        collect_frames(cache, 1, push_interval=FAST_PUSH, heartbeat_interval=FAST_HEARTBEAT),
        timeout=2.0,
    )
    data_line = [line for line in frames[0].split("\n") if line.startswith("data:")][0]
    payload = json.loads(data_line[len("data: "):])
    assert len(payload) == 1
    item = payload[0]

    assert item["ticker"] == "AAPL"
    assert item["price"] == 190.0
    assert item["prev_price"] == 190.0
    assert item["session_open"] == 190.0
    assert item["ts"] == 1000.0
    assert item["direction"] == "flat"


@pytest.mark.asyncio
async def test_stream_skips_empty_cache():
    """With an empty cache, the stream should wait and eventually emit
    once prices are populated."""
    cache = PriceCache()

    async def add_price_later():
        await asyncio.sleep(0.2)
        cache.update("AAPL", 190.0)

    task = asyncio.create_task(add_price_later())
    frames = await asyncio.wait_for(
        collect_frames(cache, 1, push_interval=FAST_PUSH, heartbeat_interval=FAST_HEARTBEAT),
        timeout=3.0,
    )
    task.cancel()

    assert len(frames) == 1
    assert "prices" in frames[0]


@pytest.mark.asyncio
async def test_stream_emits_heartbeat():
    """The stream emits a keepalive comment after heartbeat_interval elapses."""
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1000.0)

    short_heartbeat = 0.15
    short_push = 0.05
    heartbeat_received = False
    frames_seen = 0
    max_frames = 20  # safety cap to avoid infinite loop on failure

    async for frame in price_event_stream(
        cache, push_interval=short_push, heartbeat_interval=short_heartbeat
    ):
        frames_seen += 1
        if frame.strip() == ": keepalive":
            heartbeat_received = True
            break
        if frames_seen >= max_frames:
            break

    assert heartbeat_received, "Expected keepalive heartbeat to be emitted"


@pytest.mark.asyncio
async def test_stream_frame_format():
    """Each SSE frame must end with double newline."""
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1000.0)

    frames = await asyncio.wait_for(
        collect_frames(cache, 1, push_interval=FAST_PUSH, heartbeat_interval=FAST_HEARTBEAT),
        timeout=2.0,
    )
    assert frames[0].endswith("\n\n"), f"Frame should end with \\n\\n: {repr(frames[0])}"


@pytest.mark.asyncio
async def test_stream_includes_all_cached_tickers():
    cache = PriceCache()
    for ticker in ("AAPL", "GOOGL", "MSFT", "TSLA"):
        cache.update(ticker, 100.0, ts=1.0)

    frames = await asyncio.wait_for(
        collect_frames(cache, 1, push_interval=FAST_PUSH, heartbeat_interval=FAST_HEARTBEAT),
        timeout=2.0,
    )
    data_line = [line for line in frames[0].split("\n") if line.startswith("data:")][0]
    payload = json.loads(data_line[len("data: "):])
    tickers_in_event = {item["ticker"] for item in payload}
    assert tickers_in_event == {"AAPL", "GOOGL", "MSFT", "TSLA"}
