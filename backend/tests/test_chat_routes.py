import json
import sqlite3

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from chat.context import load_recent_messages
from chat.parser import ChatParseError, parse_model_response
from db import init_db
from market.cache import PriceCache
from market.simulator import SimulatorMarketData
from routes.chat import router as chat_router


@pytest.fixture
def chat_app(monkeypatch) -> FastAPI:
    monkeypatch.setenv("LLM_MOCK", "true")
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db(conn)

    cache = PriceCache()
    provider = SimulatorMarketData()
    cache.seed("AAPL", 100.0)

    app = FastAPI()
    app.state.db = conn
    app.state.price_cache = cache
    app.state.market_provider = provider
    app.include_router(chat_router)
    return app


def test_parse_model_response_extracts_json_from_text():
    parsed = parse_model_response(
        'Sure.\n{"message":"Done","trades":[{"ticker":"aapl","side":"buy","quantity":1}],'
        '"watchlist_changes":[{"ticker":"PYPL","action":"add"}]}\nThanks.'
    )

    assert parsed["message"] == "Done"
    assert parsed["trades"] == [{"ticker": "aapl", "side": "buy", "quantity": 1}]
    assert parsed["watchlist_changes"] == [{"ticker": "PYPL", "action": "add"}]


def test_parse_model_response_rejects_malformed_output():
    with pytest.raises(ChatParseError):
        parse_model_response("prefix {not json}")


def test_recent_messages_are_capped_at_last_20(chat_app):
    conn = chat_app.state.db
    for index in range(25):
        conn.execute(
            """
            INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
            VALUES (?, 'default', 'user', ?, NULL, ?)
            """,
            (f"m{index}", f"message {index}", f"2026-01-01T00:00:{index:02d}+00:00"),
        )
    conn.commit()

    messages = load_recent_messages(conn, limit=20)

    assert len(messages) == 20
    assert messages[0]["content"] == "message 5"
    assert messages[-1]["content"] == "message 24"


def test_chat_mock_mode_executes_trade_action(chat_app):
    with TestClient(chat_app) as client:
        response = client.post("/api/chat", json={"message": "please buy something"})

    assert response.status_code == 200
    body = response.json()
    assert body["trades"] == [{"ticker": "AAPL", "side": "buy", "quantity": 1}]
    assert body["errors"] == []
    assert body["results"][0]["type"] == "trade"

    position = chat_app.state.db.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE ticker = 'AAPL'"
    ).fetchone()
    assert position["quantity"] == 1
    assert position["avg_cost"] == 100

    rows = chat_app.state.db.execute(
        "SELECT role, actions FROM chat_messages ORDER BY created_at"
    ).fetchall()
    assert [row["role"] for row in rows] == ["user", "assistant"]
    assert json.loads(rows[-1]["actions"])["results"][0]["type"] == "trade"


def test_chat_mock_mode_executes_watchlist_action(chat_app):
    with TestClient(chat_app) as client:
        response = client.post("/api/chat", json={"message": "add a watchlist idea"})

    assert response.status_code == 200
    body = response.json()
    assert body["watchlist_changes"] == [{"ticker": "PYPL", "action": "add"}]
    assert body["errors"] == []

    row = chat_app.state.db.execute(
        "SELECT ticker FROM watchlist WHERE ticker = 'PYPL'"
    ).fetchone()
    assert row is not None


def test_chat_reports_malformed_model_output(monkeypatch, chat_app):
    monkeypatch.setenv("LLM_MOCK", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def broken_call(*_args, **_kwargs):
        raise ChatParseError("invalid json")

    monkeypatch.setattr("chat.service.call_assistant", broken_call)

    with TestClient(chat_app) as client:
        response = client.post("/api/chat", json={"message": "analyze my account"})

    assert response.status_code == 200
    body = response.json()
    assert body["trades"] == []
    assert body["watchlist_changes"] == []
    assert body["errors"] == [{"action": "parse", "error": "invalid json"}]


def test_chat_falls_back_to_mock_when_llm_provider_fails(monkeypatch, chat_app):
    monkeypatch.setenv("LLM_MOCK", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def broken_call(*_args, **_kwargs):
        raise RuntimeError("provider credits exhausted")

    monkeypatch.setattr("chat.service.call_assistant", broken_call)

    with TestClient(chat_app) as client:
        response = client.post("/api/chat", json={"message": "please buy something"})

    assert response.status_code == 200
    body = response.json()
    assert body["message"].startswith("Mock mode:")
    assert body["trades"] == [{"ticker": "AAPL", "side": "buy", "quantity": 1}]
    assert body["errors"][0]["action"] == "llm"
    assert "provider credits exhausted" in body["errors"][0]["error"]


def test_chat_reports_failed_action(chat_app):
    with TestClient(chat_app) as client:
        response = client.post("/api/chat", json={"message": "buy too much and fail"})

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["errors"][0]["action"] == "trade"
    assert body["errors"][0]["error"]["code"] == "insufficient_cash"

    trade_count = chat_app.state.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    assert trade_count == 0
