import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .parser import RESPONSE_SCHEMA, parse_model_response


MODEL = "openrouter/openai/gpt-oss-120b:free"


def call_assistant(
    user_message: str,
    portfolio_context: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    _load_project_env()
    import litellm

    messages = build_messages(user_message, portfolio_context, history)
    response = litellm.completion(
        model=MODEL,
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        messages=messages,
        temperature=0.2,
        max_tokens=1024,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "finally_chat_response",
                "schema": RESPONSE_SCHEMA,
                "strict": True,
            },
        },
    )
    content = response.choices[0].message.content
    return parse_model_response(content)


def build_messages(
    user_message: str,
    portfolio_context: dict[str, Any],
    history: list[dict[str, Any]],
) -> list[dict[str, str]]:
    system = (
        "You are FinAlly, an AI trading assistant for a simulated trading workstation. "
        "Be concise, data-driven, and practical. Analyze portfolio composition, risk, "
        "P&L, and watchlist opportunities. Execute trades or watchlist changes only "
        "when the user asks for them or clearly agrees. Always respond with valid JSON "
        "matching this shape exactly: {\"message\": string, \"trades\": [{\"ticker\": "
        "string, \"side\": \"buy\"|\"sell\", \"quantity\": number}], "
        "\"watchlist_changes\": [{\"ticker\": string, \"action\": \"add\"|\"remove\"}]}. "
        "Use empty arrays when there are no actions."
    )
    messages = [{"role": "system", "content": system}]
    messages.append({
        "role": "system",
        "content": "Current portfolio context:\n" + json.dumps(portfolio_context, separators=(",", ":")),
    })
    for item in history[-20:]:
        role = item.get("role")
        if role in {"user", "assistant"}:
            messages.append({"role": role, "content": str(item.get("content", ""))})
    messages.append({"role": "user", "content": user_message})
    return messages


def _load_project_env() -> None:
    root_env = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(root_env, override=False)
