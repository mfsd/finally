from typing import Any


def mock_response(message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    text = message.lower()
    if "fail" in text or "too much" in text:
        return {
            "message": "I will try that trade, but it may fail validation if it exceeds available buying power.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1_000_000}],
            "watchlist_changes": [],
        }
    if "buy" in text or "trade" in text:
        return {
            "message": "Mock mode: buying 1 share of AAPL at the current simulated price.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}],
            "watchlist_changes": [],
        }
    if "watchlist" in text or "add" in text:
        return {
            "message": "Mock mode: adding PYPL to the watchlist.",
            "trades": [],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
    total = context.get("total_value") if context else None
    suffix = f" Current total value is ${total:,.2f}." if isinstance(total, int | float) else ""
    return {
        "message": f"Mock mode: your portfolio context is loaded and ready.{suffix}",
        "trades": [],
        "watchlist_changes": [],
    }

