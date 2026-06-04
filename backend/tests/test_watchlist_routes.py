import sqlite3

from fastapi import FastAPI
from starlette.testclient import TestClient

from db import init_db
from market.cache import PriceCache
from routes.watchlist import router as watchlist_router


class FakeProvider:
    def __init__(self, valid=True):
        self.valid = valid

    def seed_price(self, ticker):
        return 123.45

    async def validate_ticker(self, ticker):
        return self.valid


def make_client(provider=None):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    cache = PriceCache()
    cache.seed("AAPL", 190.0)
    app = FastAPI()
    app.state.db = conn
    app.state.price_cache = cache
    app.state.market_provider = provider or FakeProvider()
    app.include_router(watchlist_router)
    return TestClient(app), conn, cache


def test_get_watchlist_returns_seeded_tickers_with_quotes():
    client, _conn, _cache = make_client()

    resp = client.get("/api/watchlist")

    assert resp.status_code == 200
    body = resp.json()
    tickers = {item["ticker"] for item in body["watchlist"]}
    assert "AAPL" in tickers
    aapl = next(item for item in body["watchlist"] if item["ticker"] == "AAPL")
    assert aapl["quote"]["price"] == 190.0


def test_post_watchlist_adds_uppercase_ticker_and_seeds_price():
    client, conn, cache = make_client()

    resp = client.post("/api/watchlist", json={"ticker": "pypl"})

    assert resp.status_code == 201
    assert resp.json()["item"]["ticker"] == "PYPL"
    assert resp.json()["item"]["quote"]["price"] == 123.45
    assert cache.get("PYPL").price == 123.45
    row = conn.execute("SELECT ticker FROM watchlist WHERE ticker = 'PYPL'").fetchone()
    assert row is not None


def test_post_watchlist_rejects_unknown_ticker():
    client, conn, _cache = make_client(provider=FakeProvider(valid=False))

    resp = client.post("/api/watchlist", json={"ticker": "ZZZZ"})

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "unknown_ticker"
    row = conn.execute("SELECT ticker FROM watchlist WHERE ticker = 'ZZZZ'").fetchone()
    assert row is None


def test_delete_watchlist_removes_ticker():
    client, conn, _cache = make_client()

    resp = client.delete("/api/watchlist/AAPL")

    assert resp.status_code == 200
    assert resp.json() == {"removed": "AAPL"}
    row = conn.execute("SELECT ticker FROM watchlist WHERE ticker = 'AAPL'").fetchone()
    assert row is None


def test_delete_watchlist_missing_returns_404():
    client, _conn, _cache = make_client()

    resp = client.delete("/api/watchlist/IBM")

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "watchlist_not_found"
