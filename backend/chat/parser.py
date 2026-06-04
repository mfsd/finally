import json
from typing import Any


RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "trades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "number", "exclusiveMinimum": 0},
                },
                "required": ["ticker", "side", "quantity"],
                "additionalProperties": False,
            },
        },
        "watchlist_changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "action": {"type": "string", "enum": ["add", "remove"]},
                },
                "required": ["ticker", "action"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["message"],
    "additionalProperties": False,
}


class ChatParseError(ValueError):
    """Raised when a model response cannot be parsed into the chat schema."""


def parse_model_response(raw: Any) -> dict[str, Any]:
    """Parse LiteLLM content or a dict into the expected assistant action shape."""
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(_extract_json_object(raw))
        except json.JSONDecodeError as exc:
            raise ChatParseError("Model response JSON was invalid.") from exc
    else:
        raise ChatParseError("Model returned an unsupported response type.")

    if not isinstance(data, dict):
        raise ChatParseError("Model response must be a JSON object.")

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ChatParseError("Model response is missing a message.")

    trades = data.get("trades") or []
    watchlist_changes = data.get("watchlist_changes") or []
    _validate_trades(trades)
    _validate_watchlist_changes(watchlist_changes)

    return {
        "message": message.strip(),
        "trades": trades,
        "watchlist_changes": watchlist_changes,
    }


def _validate_trades(trades: Any) -> None:
    if trades is None:
        return
    if not isinstance(trades, list):
        raise ChatParseError("trades must be an array.")
    for trade in trades:
        if not isinstance(trade, dict):
            raise ChatParseError("Each trade must be an object.")
        if not isinstance(trade.get("ticker"), str) or not trade["ticker"].strip():
            raise ChatParseError("Each trade needs a ticker.")
        if trade.get("side") not in {"buy", "sell"}:
            raise ChatParseError("Each trade side must be buy or sell.")
        quantity = trade.get("quantity")
        if not isinstance(quantity, int | float) or quantity <= 0:
            raise ChatParseError("Each trade quantity must be positive.")


def _validate_watchlist_changes(changes: Any) -> None:
    if changes is None:
        return
    if not isinstance(changes, list):
        raise ChatParseError("watchlist_changes must be an array.")
    for change in changes:
        if not isinstance(change, dict):
            raise ChatParseError("Each watchlist change must be an object.")
        if not isinstance(change.get("ticker"), str) or not change["ticker"].strip():
            raise ChatParseError("Each watchlist change needs a ticker.")
        if change.get("action") not in {"add", "remove"}:
            raise ChatParseError("Each watchlist action must be add or remove.")


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ChatParseError("Model response did not include JSON.")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]

    raise ChatParseError("Model response JSON was incomplete.")
