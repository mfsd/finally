from abc import ABC, abstractmethod
from collections.abc import Iterable


class MarketDataProvider(ABC):
    """Source of latest prices for a dynamic set of tickers."""

    @abstractmethod
    async def get_prices(self, tickers: Iterable[str]) -> dict[str, float]:
        """Latest price per ticker. Tickers with no available price are OMITTED
        from the returned dict (a missing key means 'no price yet')."""

    @abstractmethod
    def seed_price(self, ticker: str) -> float | None:
        """Synchronously return an immediately-usable price for a newly added
        ticker, or None if one cannot be produced without I/O.
          - Simulator: deterministic hash-derived seed (never None).
          - Massive:   None (price only known after the next poll)."""

    @abstractmethod
    async def validate_ticker(self, ticker: str) -> bool:
        """Whether the symbol is tradeable/known.
          - Simulator: True for any well-formed symbol.
          - Massive:   True only if the snapshot endpoint resolves the symbol."""

    async def start(self) -> None:
        """Optional one-time setup (e.g. open an httpx client). Default: no-op."""

    async def aclose(self) -> None:
        """Optional teardown. Default: no-op."""
