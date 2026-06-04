import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db import get_connection, init_db
from market.cache import PriceCache
from market.factory import make_provider
from market.poller import MarketPoller
from market.tracked import get_tracked_symbols
from routes.chat import router as chat_router
from routes.health import router as health_router
from routes.portfolio import router as portfolio_router
from routes.stream import router as stream_router
from routes.watchlist import router as watchlist_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_connection()
    init_db(db)

    cache = PriceCache()
    provider, interval = make_provider()
    tracked = lambda: get_tracked_symbols(db)

    # Synchronously seed the current tracked set so prices exist before the
    # first poll fires (simulator mode only — Massive returns None here).
    for ticker in tracked():
        seed = provider.seed_price(ticker)
        if seed is not None:
            cache.seed(ticker, seed)

    poller = MarketPoller(provider, cache, tracked_set=tracked, interval=interval)
    app.state.price_cache = cache
    app.state.market_provider = provider
    app.state.db = db

    await poller.start()
    try:
        yield
    finally:
        await poller.stop()
        db.close()


app = FastAPI(title="FinAlly — AI Trading Workstation", lifespan=lifespan)

app.include_router(chat_router)
app.include_router(health_router)
app.include_router(stream_router)
app.include_router(watchlist_router)
app.include_router(portfolio_router)

# Serve the Next.js static export (built in the Docker multi-stage build).
_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")
