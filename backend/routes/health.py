from typing import Any

from fastapi import APIRouter, Request

from market.fallback import FallbackMarketData
from market.massive import MassiveEodSimulatorMarketData, MassiveMarketData
from market.simulator import SimulatorMarketData

router = APIRouter()


@router.get("/api/health")
async def health(request: Request) -> dict:
    """Health check for Docker / deployment probes."""
    provider = getattr(request.app.state, "market_provider", None)
    return {"status": "ok", "market_data": _market_data_status(provider)}


def _market_data_status(provider: Any) -> dict[str, str]:
    if isinstance(provider, FallbackMarketData):
        if provider.primary_failed:
            return {
                "source": "simulator",
                "mode": "fallback",
                "label": "Simulator fallback",
                "description": "External market data is unavailable; prices are fully simulated.",
            }
        if isinstance(provider.primary, MassiveEodSimulatorMarketData):
            return _massive_eod_status()
        if isinstance(provider.primary, MassiveMarketData):
            return _massive_snapshot_status()
        return {
            "mode": "primary",
            "source": "unknown",
            "label": "Market data",
            "description": "Market data provider is active.",
        }
    if isinstance(provider, MassiveEodSimulatorMarketData):
        return _massive_eod_status()
    if isinstance(provider, MassiveMarketData):
        return _massive_snapshot_status()
    if isinstance(provider, SimulatorMarketData):
        return {
            "source": "simulator",
            "mode": "primary",
            "label": "Simulator",
            "description": "Prices are generated locally by the simulator.",
        }
    return {"source": "unknown", "mode": "unknown", "label": "Unknown", "description": "Market data source is not known."}


def _massive_eod_status() -> dict[str, str]:
    return {
        "source": "massive",
        "mode": "free_eod",
        "label": "Massive EOD + sim",
        "description": "End-of-day Massive closes with simulated intraday variation. Massive seed updates daily.",
    }


def _massive_snapshot_status() -> dict[str, str]:
    return {
        "source": "massive",
        "mode": "snapshot",
        "label": "Massive snapshot",
        "description": "Prices are polled from Massive stock snapshots.",
    }
