"""Integration tests for the FastAPI app: SSE route, health endpoint, and DB init.

SSE route tests bypass the infinite real stream by injecting a finite
price_event_stream stub, so tests run fast and never hang.
"""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from starlette.testclient import TestClient
import httpx

from market.cache import PriceCache
from routes.health import router as health_router


# ---- finite SSE helper for testing -----------------------------------------

async def _finite_stream(cache: PriceCache, frames: int = 2) -> AsyncIterator[str]:
    """Yield exactly `frames` SSE price events then stop."""
    import json as _json
    for _ in range(frames):
        snap = cache.snapshot()
        if snap:
            payload = [q.to_event() for q in snap.values()]
            yield f"event: prices\ndata: {_json.dumps(payload)}\n\n"


def make_test_app(cache: PriceCache, finite: bool = True) -> FastAPI:
    """FastAPI app with the cache baked into a closure (no lifespan needed)."""
    app = FastAPI()
    app.include_router(health_router)

    @app.get("/api/stream/prices")
    async def stream_prices(_req: Request) -> StreamingResponse:
        gen = _finite_stream(cache) if finite else None
        if gen is None:
            from market.stream import price_event_stream
            gen = price_event_stream(cache)
        return StreamingResponse(
            gen,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


@pytest.fixture
def seeded_cache() -> PriceCache:
    cache = PriceCache()
    cache.update("AAPL", 190.0, ts=1000.0)
    cache.update("TSLA", 240.0, ts=1001.0)
    return cache


@pytest.fixture
def client(seeded_cache) -> TestClient:
    return TestClient(make_test_app(seeded_cache))


# ---- health endpoint --------------------------------------------------------

def test_health_returns_200(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_health_returns_ok_status(client):
    resp = client.get("/api/health")
    assert resp.json() == {"status": "ok"}


# ---- SSE: finite stream (all assertions using GET on a finite generator) ----

def test_stream_returns_200(client):
    resp = client.get("/api/stream/prices")
    assert resp.status_code == 200


def test_stream_content_type_is_event_stream(client):
    resp = client.get("/api/stream/prices")
    assert "text/event-stream" in resp.headers["content-type"]


def test_stream_has_no_cache_header(client):
    resp = client.get("/api/stream/prices")
    assert resp.headers.get("cache-control") == "no-cache"


def _parse_first_payload(text: str) -> list:
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data: "):])
    raise AssertionError(f"No data line found:\n{text!r}")


def test_stream_emits_prices_event(client):
    resp = client.get("/api/stream/prices")
    assert "event: prices" in resp.text


def test_stream_payload_is_valid_json(client):
    resp = client.get("/api/stream/prices")
    payload = _parse_first_payload(resp.text)
    assert isinstance(payload, list)


def test_stream_payload_contains_both_tickers(client):
    resp = client.get("/api/stream/prices")
    payload = _parse_first_payload(resp.text)
    tickers = {item["ticker"] for item in payload}
    assert tickers == {"AAPL", "TSLA"}


def test_stream_payload_item_shape(client):
    resp = client.get("/api/stream/prices")
    payload = _parse_first_payload(resp.text)
    item = next(i for i in payload if i["ticker"] == "AAPL")
    assert item["price"] == 190.0
    assert item["session_open"] == 190.0
    assert item["direction"] == "flat"
    assert "ts" in item
    assert "prev_price" in item


def test_stream_frame_ends_with_double_newline(client):
    resp = client.get("/api/stream/prices")
    # Each SSE frame must terminate with \n\n
    frames = [f for f in resp.text.split("\n\n") if f.strip()]
    assert len(frames) > 0
    assert resp.text.endswith("\n\n") or "\n\n" in resp.text


def test_stream_two_frames_emitted(seeded_cache):
    """The finite stub emits exactly 2 frames; verify both arrive."""
    app = make_test_app(seeded_cache, finite=True)
    with TestClient(app) as c:
        resp = c.get("/api/stream/prices")
    frames = [f for f in resp.text.split("\n\n") if "event: prices" in f]
    assert len(frames) == 2


# ---- DB init ----------------------------------------------------------------

def test_db_init_seeds_default_watchlist():
    import sqlite3
    from db import init_db, DEFAULT_WATCHLIST

    conn = sqlite3.connect(":memory:")
    init_db(conn)

    rows = conn.execute("SELECT ticker FROM watchlist WHERE user_id='default'").fetchall()
    tickers = {r[0] for r in rows}
    assert tickers == set(DEFAULT_WATCHLIST)


def test_db_init_seeds_default_user():
    import sqlite3
    from db import init_db

    conn = sqlite3.connect(":memory:")
    init_db(conn)

    row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id='default'"
    ).fetchone()
    assert row is not None
    assert row[0] == 10000.0


def test_db_init_is_idempotent():
    import sqlite3
    from db import init_db, DEFAULT_WATCHLIST

    conn = sqlite3.connect(":memory:")
    init_db(conn)
    init_db(conn)

    count = conn.execute(
        "SELECT COUNT(*) FROM watchlist WHERE user_id='default'"
    ).fetchone()[0]
    assert count == len(DEFAULT_WATCHLIST)


def test_db_schema_creates_all_tables():
    import sqlite3
    from db import init_db

    conn = sqlite3.connect(":memory:")
    init_db(conn)

    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    expected = {"users_profile", "watchlist", "positions", "trades",
                "portfolio_snapshots", "chat_messages"}
    assert expected.issubset(tables)
