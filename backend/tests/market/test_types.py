import time
import pytest
from market.types import Quote


def test_direction_up():
    q = Quote("AAPL", price=100.0, prev_price=99.0, session_open=98.0, ts=0.0)
    assert q.direction == "up"


def test_direction_down():
    q = Quote("AAPL", price=99.0, prev_price=100.0, session_open=98.0, ts=0.0)
    assert q.direction == "down"


def test_direction_flat():
    q = Quote("AAPL", price=100.0, prev_price=100.0, session_open=98.0, ts=0.0)
    assert q.direction == "flat"


def test_to_event_shape():
    q = Quote("AAPL", price=190.1234567, prev_price=190.0, session_open=189.0, ts=1234567890.5)
    event = q.to_event()
    assert event["ticker"] == "AAPL"
    assert event["price"] == round(190.1234567, 4)
    assert event["prev_price"] == 190.0
    assert event["session_open"] == 189.0
    assert event["ts"] == 1234567890.5
    assert event["direction"] == "up"


def test_to_event_rounds_to_4_decimal_places():
    q = Quote("X", price=1.23456789, prev_price=1.0, session_open=1.0, ts=0.0)
    assert event := q.to_event()
    assert event["price"] == 1.2346


def test_quote_is_frozen():
    q = Quote("AAPL", price=100.0, prev_price=99.0, session_open=98.0, ts=0.0)
    with pytest.raises((AttributeError, TypeError)):
        q.price = 200.0  # type: ignore
