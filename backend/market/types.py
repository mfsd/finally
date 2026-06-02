from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    """A single price observation for one ticker."""

    ticker: str
    price: float
    prev_price: float
    session_open: float
    ts: float

    @property
    def direction(self) -> str:
        if self.price > self.prev_price:
            return "up"
        if self.price < self.prev_price:
            return "down"
        return "flat"

    def to_event(self) -> dict:
        """Shape pushed over SSE. Frontend computes daily change % as
        (price - session_open) / session_open."""
        return {
            "ticker": self.ticker,
            "price": round(self.price, 4),
            "prev_price": round(self.prev_price, 4),
            "session_open": round(self.session_open, 4),
            "ts": self.ts,
            "direction": self.direction,
        }
