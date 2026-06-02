import time
from threading import RLock

from .types import Quote


class PriceCache:
    """In-memory, thread-safe store of the latest Quote per ticker.

    Owns prev-price / session-open / direction bookkeeping so providers stay dumb.
    session_open is set on first insert and never overwritten until backend restart.
    """

    def __init__(self) -> None:
        self._quotes: dict[str, Quote] = {}
        self._lock = RLock()

    def snapshot(self) -> dict[str, Quote]:
        """Return a point-in-time copy of all quotes."""
        with self._lock:
            return dict(self._quotes)

    def get(self, ticker: str) -> Quote | None:
        with self._lock:
            return self._quotes.get(ticker)

    def update(self, ticker: str, price: float, ts: float | None = None) -> Quote:
        """Apply a new price, deriving prev_price and preserving session_open."""
        ts = ts if ts is not None else time.time()
        with self._lock:
            existing = self._quotes.get(ticker)
            if existing is None:
                q = Quote(ticker=ticker, price=price, prev_price=price,
                          session_open=price, ts=ts)
            else:
                q = Quote(ticker=ticker, price=price, prev_price=existing.price,
                          session_open=existing.session_open, ts=ts)
            self._quotes[ticker] = q
            return q

    def seed(self, ticker: str, price: float) -> Quote:
        """Insert a ticker with no prior entry (synchronous sim seeding).
        No-op if already present; returns existing quote in that case."""
        with self._lock:
            if ticker not in self._quotes:
                return self.update(ticker, price)
            return self._quotes[ticker]
