import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db import get_connection, init_db, record_snapshot
from market.cache import PriceCache
from market.factory import make_provider, _MassiveSeededSimulator
from market.poller import MarketPoller
from market.tracked import get_tracked_symbols
from routes.health import router as health_router
from routes.stream import router as stream_router
from routes.portfolio import router as portfolio_router
from routes.watchlist import router as watchlist_router
from routes.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_connection()
    init_db(db)

    cache = PriceCache()
    provider, interval = make_provider()
    tracked = lambda: get_tracked_symbols(db)

    # Seed simulator prices — use real Massive prev-close if available
    initial_tickers = list(tracked())
    if isinstance(provider, _MassiveSeededSimulator):
        try:
            await provider.seed_from_massive(initial_tickers)
        except Exception:
            pass  # fall back to hash-derived seeds

    for ticker in initial_tickers:
        seed = provider.seed_price(ticker)
        if seed is not None:
            cache.seed(ticker, seed)

    poller = MarketPoller(provider, cache, tracked_set=tracked, interval=interval)
    app.state.price_cache = cache
    app.state.market_provider = provider
    app.state.db = db

    async def _snapshot_loop():
        while True:
            await asyncio.sleep(30)
            try:
                profile = db.execute(
                    "SELECT cash_balance FROM users_profile WHERE id='default'"
                ).fetchone()
                if profile:
                    cash = profile["cash_balance"]
                    positions = db.execute(
                        "SELECT ticker, quantity FROM positions WHERE user_id='default'"
                    ).fetchall()
                    total = cash
                    for pos in positions:
                        q = cache.get(pos["ticker"])
                        if q:
                            total += q.price * pos["quantity"]
                    record_snapshot(db, total)
            except Exception:
                pass

    await poller.start()
    snapshot_task = asyncio.create_task(_snapshot_loop())
    try:
        yield
    finally:
        snapshot_task.cancel()
        await poller.stop()
        db.close()


app = FastAPI(title="FinAlly — AI Trading Workstation", lifespan=lifespan)

app.include_router(health_router)
app.include_router(stream_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(chat_router)

_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")
