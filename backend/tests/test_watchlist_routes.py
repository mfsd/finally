import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from db import get_connection, init_db
from routes.watchlist import router
from market.cache import PriceCache


@pytest.fixture
def app_client():
    conn = get_connection(":memory:")
    init_db(conn)
    cache = PriceCache()

    provider = MagicMock()
    provider.validate_ticker = AsyncMock(return_value=True)
    provider.seed_price.return_value = 100.0

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db = conn
        app.state.price_cache = cache
        app.state.market_provider = provider
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)

    with TestClient(app) as client:
        yield client


def test_get_watchlist(app_client):
    r = app_client.get("/api/watchlist")
    assert r.status_code == 200
    data = r.json()
    tickers = [w["ticker"] for w in data["watchlist"]]
    assert "AAPL" in tickers


def test_add_ticker(app_client):
    r = app_client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r.status_code == 200
    assert r.json()["added"] is True


def test_add_duplicate_idempotent(app_client):
    app_client.post("/api/watchlist", json={"ticker": "PYPL"})
    r = app_client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r.status_code == 200  # idempotent, not 409


def test_add_invalid_ticker(app_client):
    r = app_client.post("/api/watchlist", json={"ticker": "!!!INVALID!!!"})
    assert r.status_code == 400


def test_remove_ticker(app_client):
    app_client.post("/api/watchlist", json={"ticker": "PYPL"})
    r = app_client.delete("/api/watchlist/PYPL")
    assert r.status_code == 204


def test_remove_nonexistent(app_client):
    r = app_client.delete("/api/watchlist/ZZZZ")
    assert r.status_code == 404
