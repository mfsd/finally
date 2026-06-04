import sqlite3

from fastapi import FastAPI
from starlette.testclient import TestClient

from db import init_db
from market.cache import PriceCache
from routes.portfolio import router as portfolio_router
from routes.watchlist import router as watchlist_router


class FakeProvider:
    def __init__(self, valid=True, seed=100.0):
        self.valid = valid
        self.seed = seed

    def seed_price(self, ticker):
        return self.seed

    async def validate_ticker(self, ticker):
        return self.valid


class NoSeedProvider(FakeProvider):
    def seed_price(self, ticker):
        return None


def make_client(provider=None):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    cache = PriceCache()
    cache.seed("AAPL", 200.0)
    cache.seed("MSFT", 50.0)
    app = FastAPI()
    app.state.db = conn
    app.state.price_cache = cache
    app.state.market_provider = provider or FakeProvider()
    app.include_router(watchlist_router)
    app.include_router(portfolio_router)
    return TestClient(app), conn, cache


def test_get_portfolio_initial_state():
    client, _conn, _cache = make_client()

    resp = client.get("/api/portfolio")

    assert resp.status_code == 200
    assert resp.json()["portfolio"]["cash_balance"] == 10000.0
    assert resp.json()["portfolio"]["positions"] == []
    assert resp.json()["portfolio"]["total_value"] == 10000.0


def test_buy_trade_fills_from_cache_and_supports_fractional_shares():
    client, conn, _cache = make_client()

    resp = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 1.5},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["trade"]["price"] == 200.0
    assert body["cash_balance"] == 9700.0
    assert body["position"]["quantity"] == 1.5
    assert body["position"]["avg_cost"] == 200.0
    trades = conn.execute("SELECT COUNT(*) FROM trades WHERE ticker = 'AAPL'").fetchone()[0]
    snapshots = conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]
    assert trades == 1
    assert snapshots == 1


def test_buy_trade_validates_cash_before_implicit_watchlist_add():
    client, conn, _cache = make_client()

    resp = client.post(
        "/api/portfolio/trade",
        json={"ticker": "IBM", "side": "buy", "quantity": 1000},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "insufficient_cash"
    watched = conn.execute("SELECT ticker FROM watchlist WHERE ticker = 'IBM'").fetchone()
    assert watched is None


def test_successful_trade_implicitly_adds_unwatched_ticker():
    client, conn, _cache = make_client()

    resp = client.post(
        "/api/portfolio/trade",
        json={"ticker": "ibm", "side": "buy", "quantity": 2},
    )

    assert resp.status_code == 200
    assert resp.json()["trade"]["ticker"] == "IBM"
    watched = conn.execute("SELECT ticker FROM watchlist WHERE ticker = 'IBM'").fetchone()
    assert watched is not None


def test_sell_trade_validates_holdings():
    client, _conn, _cache = make_client()

    resp = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "sell", "quantity": 1},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "insufficient_shares"


def test_sell_near_zero_position_deletes_row_and_snapshots():
    client, conn, _cache = make_client()
    buy = client.post(
        "/api/portfolio/trade",
        json={"ticker": "MSFT", "side": "buy", "quantity": 0.5},
    )
    assert buy.status_code == 200

    sell = client.post(
        "/api/portfolio/trade",
        json={"ticker": "MSFT", "side": "sell", "quantity": 0.4999999},
    )

    assert sell.status_code == 200
    assert sell.json()["position"] is None
    position = conn.execute("SELECT ticker FROM positions WHERE ticker = 'MSFT'").fetchone()
    snapshots = conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]
    assert position is None
    assert snapshots == 2


def test_trade_rejects_when_price_not_available():
    client, _conn, _cache = make_client(provider=NoSeedProvider())

    resp = client.post(
        "/api/portfolio/trade",
        json={"ticker": "IBM", "side": "buy", "quantity": 1},
    )

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "price_not_available"


def test_history_returns_recent_snapshots_oldest_first():
    client, _conn, _cache = make_client()
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1})
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 1})

    resp = client.get("/api/portfolio/history")

    assert resp.status_code == 200
    history = resp.json()["history"]
    assert len(history) == 2
    assert history[0]["recorded_at"] <= history[1]["recorded_at"]


def test_delete_watchlist_does_not_remove_position():
    client, conn, _cache = make_client()
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1})

    resp = client.delete("/api/watchlist/AAPL")

    assert resp.status_code == 200
    position = conn.execute("SELECT ticker FROM positions WHERE ticker = 'AAPL'").fetchone()
    assert position is not None
