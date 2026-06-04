import os

from .base import MarketDataProvider
from .fallback import FallbackMarketData
from .simulator import SimulatorMarketData
from .massive import MassiveEodSimulatorMarketData, MassiveMarketData


def make_provider() -> tuple[MarketDataProvider, float]:
    """Return (provider, poll_interval_seconds) based on environment.

    If MASSIVE_API_KEY is set and non-empty, returns a Massive-backed provider.
    The default mode is free-plan friendly: real end-of-day Massive closes plus
    simulated intraday variation. Set MASSIVE_MODE=snapshot for paid snapshot
    access.
    Otherwise returns the in-process GBM simulator at 0.5s.
    """
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if key:
        mode = os.environ.get("MASSIVE_MODE", "free_eod").strip().lower()
        interval = float(os.environ.get("MASSIVE_POLL_INTERVAL", "0.5" if mode == "free_eod" else "15"))
        primary: MarketDataProvider
        if mode == "snapshot":
            primary = MassiveMarketData(api_key=key)
        else:
            primary = MassiveEodSimulatorMarketData(api_key=key)
        return FallbackMarketData(primary, SimulatorMarketData()), interval
    return SimulatorMarketData(), 0.5
