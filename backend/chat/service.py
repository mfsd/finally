import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .actions import execute_actions
from .context import load_portfolio_context, load_recent_messages
from .llm import call_assistant
from .mock import mock_response
from .parser import ChatParseError


async def handle_chat(
    conn: sqlite3.Connection,
    price_cache: Any,
    provider: Any,
    message: str,
    user_id: str = "default",
) -> dict[str, Any]:
    text = message.strip()
    if not text:
        raise ValueError("Message is required.")

    history = load_recent_messages(conn, user_id=user_id, limit=20)
    context = load_portfolio_context(conn, price_cache, user_id=user_id)
    _persist_message(conn, user_id, "user", text, None)
    conn.commit()

    errors: list[dict[str, Any]] = []
    try:
        assistant = mock_response(text, context) if _use_mock_llm() else call_assistant(text, context, history)
    except ChatParseError as exc:
        assistant = {
            "message": "I could not parse the model response into a valid action plan.",
            "trades": [],
            "watchlist_changes": [],
        }
        errors.append({"action": "parse", "error": str(exc)})
    except Exception as exc:
        assistant = mock_response(text, context)
        errors.append(
            {
                "action": "llm",
                "error": f"LLM request failed; used mock response instead: {exc}",
            }
        )

    actions = await execute_actions(
        conn,
        price_cache,
        provider,
        assistant.get("trades", []),
        assistant.get("watchlist_changes", []),
        user_id=user_id,
    )
    errors.extend(actions["errors"])

    persisted_actions = {
        "trades": assistant.get("trades", []),
        "watchlist_changes": assistant.get("watchlist_changes", []),
        "results": actions["results"],
        "errors": errors,
    }
    _persist_message(conn, user_id, "assistant", assistant["message"], persisted_actions)
    conn.commit()

    return {
        "message": assistant["message"],
        "trades": assistant.get("trades", []),
        "watchlist_changes": assistant.get("watchlist_changes", []),
        "actions": {
            "trades": assistant.get("trades", []),
            "watchlist_changes": assistant.get("watchlist_changes", []),
        },
        "results": actions["results"],
        "errors": errors,
    }


def _persist_message(
    conn: sqlite3.Connection,
    user_id: str,
    role: str,
    content: str,
    actions: dict[str, Any] | None,
) -> None:
    conn.execute(
        """
        INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            user_id,
            role,
            content,
        json.dumps(actions, separators=(",", ":")) if actions is not None else None,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def _use_mock_llm() -> bool:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    if os.environ.get("LLM_MOCK", "").lower() == "true":
        return True
    return not os.environ.get("OPENROUTER_API_KEY", "").strip()
