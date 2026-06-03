import pytest
from contextlib import asynccontextmanager
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from db import get_connection, init_db, upsert_position
from routes.portfolio import router
from market.types import Quote
import time


def make_mock_cache(prices: dict):
    cache = MagicMock()
    def _get(ticker):
        if ticker in prices:
            p = prices[ticker]
            return Quote(ticker=ticker, price=p, prev_price=p, session_open=p * 0.99, ts=time.time())
        return None
    cache.get.side_effect = _get
    cache.seed = MagicMock()
    return cache


def make_mock_provider():
    provider = MagicMock()
    provider.seed_price.return_value = 100.0
    return provider


@pytest.fixture
def app_client():
    conn = get_connection(":memory:")
    init_db(conn)
    cache = make_mock_cache({"AAPL": 190.0, "TSLA": 250.0})
    provider = make_mock_provider()

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


def test_get_portfolio_empty(app_client):
    r = app_client.get("/api/portfolio")
    assert r.status_code == 200
    data = r.json()
    assert data["cash_balance"] == 10000.0
    assert data["positions"] == []
    assert data["total_value"] == 10000.0


def test_buy_success(app_client):
    r = app_client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["cash_balance"] == pytest.approx(10000.0 - 190.0 * 10)
    assert data["trade"]["price"] == 190.0


def test_buy_insufficient_cash(app_client):
    r = app_client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10000, "side": "buy"})
    assert r.status_code == 422


def test_sell_insufficient_shares(app_client):
    r = app_client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "sell"})
    assert r.status_code == 422


def test_sell_success(app_client):
    app_client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    r = app_client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "sell"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["position"]["quantity"] == 5.0


def test_trade_unknown_ticker(app_client):
    r = app_client.post("/api/portfolio/trade", json={"ticker": "ZZZZ", "quantity": 1, "side": "buy"})
    assert r.status_code == 422


def test_portfolio_history(app_client):
    r = app_client.get("/api/portfolio/history")
    assert r.status_code == 200
    assert "history" in r.json()
