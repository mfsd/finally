import os
import pytest
from unittest.mock import patch

from market.factory import make_provider
from market.fallback import FallbackMarketData
from market.simulator import SimulatorMarketData
from market.massive import MassiveEodSimulatorMarketData, MassiveMarketData


def _env_without(*keys: str) -> dict:
    return {k: v for k, v in os.environ.items() if k not in keys}


def test_make_provider_returns_simulator_when_no_key():
    with patch.dict(os.environ, _env_without("MASSIVE_API_KEY"), clear=True):
        provider, interval = make_provider()
    assert isinstance(provider, SimulatorMarketData)
    assert interval == 0.5


def test_make_provider_returns_simulator_when_key_is_empty():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}):
        provider, interval = make_provider()
    assert isinstance(provider, SimulatorMarketData)
    assert interval == 0.5


def test_make_provider_returns_simulator_when_key_is_whitespace():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}):
        provider, interval = make_provider()
    assert isinstance(provider, SimulatorMarketData)
    assert interval == 0.5


def test_make_provider_returns_massive_when_key_is_set():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key-abc"}, clear=False):
        provider, interval = make_provider()
    assert isinstance(provider, FallbackMarketData)
    assert isinstance(provider.primary, MassiveEodSimulatorMarketData)
    assert isinstance(provider.fallback, SimulatorMarketData)
    assert interval == 0.5


def test_make_provider_uses_custom_interval_for_massive():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key", "MASSIVE_POLL_INTERVAL": "5"}):
        provider, interval = make_provider()
    assert isinstance(provider, FallbackMarketData)
    assert interval == 5.0


def test_make_provider_default_interval_0_5_for_free_eod_massive():
    env = {**_env_without("MASSIVE_POLL_INTERVAL"), "MASSIVE_API_KEY": "test-key"}
    with patch.dict(os.environ, env, clear=True):
        provider, interval = make_provider()
    assert isinstance(provider, FallbackMarketData)
    assert isinstance(provider.primary, MassiveEodSimulatorMarketData)
    assert interval == 0.5


def test_make_provider_can_use_paid_snapshot_mode():
    env = {**_env_without("MASSIVE_POLL_INTERVAL"), "MASSIVE_API_KEY": "test-key", "MASSIVE_MODE": "snapshot"}
    with patch.dict(os.environ, env, clear=True):
        provider, interval = make_provider()
    assert isinstance(provider, FallbackMarketData)
    assert isinstance(provider.primary, MassiveMarketData)
    assert interval == 15.0
