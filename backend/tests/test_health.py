from routes.health import _market_data_status
from market.fallback import FallbackMarketData
from market.massive import MassiveEodSimulatorMarketData, MassiveMarketData
from market.simulator import SimulatorMarketData


def test_health_reports_massive_eod_simulator_mode():
    provider = FallbackMarketData(MassiveEodSimulatorMarketData("key"), SimulatorMarketData())

    status = _market_data_status(provider)

    assert status["source"] == "massive"
    assert status["mode"] == "free_eod"
    assert status["label"] == "Massive EOD + sim"
    assert "End-of-day Massive closes" in status["description"]


def test_health_reports_massive_snapshot_mode():
    provider = FallbackMarketData(MassiveMarketData("key"), SimulatorMarketData())

    status = _market_data_status(provider)

    assert status["source"] == "massive"
    assert status["mode"] == "snapshot"
    assert status["label"] == "Massive snapshot"


def test_health_reports_simulator_fallback_after_primary_failure():
    provider = FallbackMarketData(MassiveEodSimulatorMarketData("key"), SimulatorMarketData())
    provider._primary_failed = True

    status = _market_data_status(provider)

    assert status["source"] == "simulator"
    assert status["mode"] == "fallback"
    assert status["label"] == "Simulator fallback"
