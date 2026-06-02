import os

from .base import MarketDataProvider
from .simulator import SimulatorMarketData
from .massive import MassiveMarketData


def make_provider() -> tuple[MarketDataProvider, float]:
    """Return (provider, poll_interval_seconds) based on environment.

    If MASSIVE_API_KEY is set and non-empty, returns a MassiveMarketData
    provider with configurable poll interval (default 15s for free tier).
    Otherwise returns the in-process GBM simulator at 0.5s.
    """
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if key:
        interval = float(os.environ.get("MASSIVE_POLL_INTERVAL", "15"))
        return MassiveMarketData(api_key=key), interval
    return SimulatorMarketData(), 0.5
