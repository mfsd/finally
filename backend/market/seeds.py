import hashlib

SEED_PRICES: dict[str, float] = {
    "AAPL": 190.0,
    "GOOGL": 175.0,
    "MSFT": 420.0,
    "AMZN": 185.0,
    "TSLA": 240.0,
    "NVDA": 1180.0,
    "META": 500.0,
    "JPM": 200.0,
    "V": 280.0,
    "NFLX": 650.0,
}


def seed_price(ticker: str) -> float:
    """Deterministic starting price. Known tickers use the realistic table;
    everything else hashes into the $50–$300 band."""
    if ticker in SEED_PRICES:
        return SEED_PRICES[ticker]
    digest = hashlib.sha256(ticker.encode()).digest()
    frac = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    return round(50.0 + frac * 250.0, 2)
