# Massive API — Stock Price Reference

> Research notes and code examples for retrieving **real-time** and **end-of-day** stock
> prices from the [Massive](https://massive.com) REST API, for use by FinAlly's market-data
> layer (see [MARKET_INTERFACE.md](./MARKET_INTERFACE.md)).

## 1. What Massive Is

Massive (formerly **Polygon.io**) is a market-data provider exposing REST and WebSocket
APIs for US stocks, options, forex, crypto, and indices. It is **Polygon.io-compatible**:
the REST surface, URL paths, JSON field names, and auth all mirror Polygon's. The official
Python client (`api.massive.com`) still accepts `api.polygon.io` as a fallback host, and
Polygon documentation/SDKs work against Massive with only a host swap.

**Practical consequence for FinAlly:** treat Polygon's published JSON schema as the working
assumption, confirm exact field names against a live key, and keep the parser tolerant of
minor differences. We only need a tiny slice of this API: *the latest price for a set of
tickers*, plus optionally a previous-day close.

## 2. Base URL & Authentication

| Item | Value |
|------|-------|
| REST base URL | `https://api.massive.com` |
| Legacy/compatible host | `https://api.polygon.io` (still accepted) |
| Auth — header (preferred) | `Authorization: Bearer <MASSIVE_API_KEY>` |
| Auth — query param (fallback) | `?apiKey=<MASSIVE_API_KEY>` |

Both auth styles are accepted (Polygon compatibility). FinAlly uses the **Bearer header** so
the key never lands in URLs/logs. An invalid or missing key returns `401`.

```bash
# Header auth (preferred)
curl -s 'https://api.massive.com/v2/last/trade/AAPL' \
  -H 'Authorization: Bearer YOUR_API_KEY'

# Query-param auth (equivalent)
curl -s 'https://api.massive.com/v2/last/trade/AAPL?apiKey=YOUR_API_KEY'
```

## 3. Rate Limits

Limits are plan-dependent. The free tier is the binding constraint for FinAlly's polling
cadence.

| Plan | Rate limit | Data freshness |
|------|-----------|----------------|
| Free / Basic | ~5 requests / minute | 15-minute delayed |
| Starter | Elevated | 15-minute delayed |
| Advanced / Business | High / unlimited | Real-time |

**Polling design that respects the free tier:** Use **one request per poll** that returns
*all* tracked tickers at once (the multi-ticker Snapshot, §4.3), rather than one request per
ticker. At 5 req/min the safe interval is **≥ 15 seconds**. FinAlly's poller defaults to a
15s interval on the free tier and a faster interval (2–15s) on paid tiers, configurable.

> Because the free tier is 15-minute delayed, "real-time" in simulator-free mode means
> "delayed real trades." That is acceptable for the demo; the simulator is the default
> experience.

## 4. Endpoints We Use

All paths below are appended to the base URL. Timestamps in responses are **Unix
nanoseconds** for trades/quotes and **Unix milliseconds** for aggregate bars — normalize on
ingest.

### 4.1 Last Trade — single ticker

The most direct "what did this print at" call.

```
GET /v2/last/trade/{stocksTicker}
```

```bash
curl -s 'https://api.massive.com/v2/last/trade/AAPL' \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

```json
{
  "request_id": "f05562305bd26ced64b98ed68b3c5d96",
  "status": "OK",
  "results": {
    "T": "AAPL",
    "p": 129.8473,
    "s": 25,
    "ds": "25.0",
    "t": 1617901342969834000,
    "y": 1617901342968000000,
    "f": 1617901342969796400,
    "i": "118749",
    "x": 4,
    "c": [37],
    "q": 3135876,
    "r": 202,
    "e": null,
    "z": 3
  }
}
```

Key fields: `results.p` = trade price, `results.s` = size, `results.t` = SIP timestamp
(nanoseconds). **One ticker per call** — not used for the main poll loop (too many requests),
but handy for ad-hoc validation.

### 4.2 Single-Ticker Snapshot

Returns the day bar, last minute bar, previous-day bar, last trade, and last quote for one
ticker. Richer than Last Trade; also one ticker per call.

```
GET /v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}
```

```bash
curl -s 'https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/AAPL' \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

```json
{
  "status": "OK",
  "request_id": "657e430f1ae768891f018e08e03598d8",
  "ticker": {
    "ticker": "AAPL",
    "todaysChange": 1.42,
    "todaysChangePerc": 0.79,
    "updated": 1605192959994246100,
    "day":     { "o": 181.0, "h": 184.2, "l": 180.5, "c": 183.1, "v": 50217287, "vw": 182.5 },
    "min":     { "o": 183.0, "h": 183.2, "l": 182.9, "c": 183.1, "v": 12345,   "vw": 183.05, "t": 1605192900000 },
    "prevDay": { "o": 179.5, "h": 182.0, "l": 179.1, "c": 181.7, "v": 48123456, "vw": 180.9 },
    "lastTrade": { "p": 183.12, "s": 100, "t": 1605192959987654300, "x": 4, "c": [14] },
    "lastQuote": { "P": 183.13, "S": 2, "p": 183.11, "s": 3, "t": 1605192959900000000 }
  }
}
```

For "latest price," prefer `ticker.lastTrade.p`; fall back to `ticker.min.c` (last minute
close) then `ticker.day.c` if `lastTrade` is absent on the plan. `ticker.prevDay.c` gives a
real previous close if we ever want it.

### 4.3 Full-Market Snapshot, filtered by tickers — **the poll endpoint**

This is the one FinAlly's poller calls. A **single request returns snapshots for a
comma-separated list of tickers**, so the whole tracked set costs one request per poll.

```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,TSLA,GOOGL
```

```bash
curl -s 'https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,TSLA,GOOGL' \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

```json
{
  "status": "OK",
  "count": 3,
  "tickers": [
    {
      "ticker": "AAPL",
      "todaysChange": 1.42,
      "todaysChangePerc": 0.79,
      "updated": 1605192894630916600,
      "day":     { "o": 181.0, "h": 184.2, "l": 180.5, "c": 183.1, "v": 50217287 },
      "min":     { "c": 183.12, "t": 1605192894000 },
      "prevDay": { "c": 181.7 },
      "lastTrade": { "p": 183.12, "s": 100, "t": 1605192894600000000 }
    },
    { "ticker": "TSLA",  "lastTrade": { "p": 242.55, "t": 1605192894500000000 }, "prevDay": { "c": 240.10 }, "todaysChange": 2.45 },
    { "ticker": "GOOGL", "lastTrade": { "p": 175.31, "t": 1605192894550000000 }, "prevDay": { "c": 174.02 }, "todaysChange": 1.29 }
  ]
}
```

Notes:
- `tickers` is **case-sensitive** and comma-separated, e.g. `tickers=AAPL,TSLA,GOOG`.
- `include_otc=false` by default.
- A symbol that **does not exist is simply omitted** from the `tickers` array (the response
  doesn't error). This is how we detect unknown tickers on add (see §6).
- Per-row latest price resolution is the same as §4.2: `lastTrade.p` → `min.c` → `day.c`.

### 4.4 Previous-Day Bar (end-of-day OHLC)

For an explicit end-of-day / previous-close value per ticker (e.g. a true daily-change
baseline rather than FinAlly's session-open substitute).

```
GET /v2/aggs/ticker/{stocksTicker}/prev?adjusted=true
```

```json
{
  "ticker": "AAPL",
  "adjusted": true,
  "queryCount": 1,
  "resultsCount": 1,
  "status": "OK",
  "request_id": "6a7e466379af0a71039d60cc78e72282",
  "results": [
    { "T": "AAPL", "o": 115.55, "h": 117.59, "l": 114.13, "c": 115.97, "v": 131704427, "vw": 116.3058, "t": 1605042000000 }
  ]
}
```

`results[0].c` = previous-day close. `t` here is **milliseconds**. One ticker per call. FinAlly
uses a server-side session-open baseline by default (see PLAN §6), so this endpoint is
optional — documented for completeness and possible future use.

## 5. Timestamp & Field Normalization

| Source | Unit | Convert to |
|--------|------|-----------|
| `lastTrade.t`, `last/trade.results.t` | Unix **nanoseconds** | `t / 1e9` → epoch seconds |
| `min.t` | Unix **milliseconds** | `t / 1e3` → epoch seconds |
| aggregate `results.t` (prev bar) | Unix **milliseconds** | `t / 1e3` → epoch seconds |

Latest-price resolution order (tolerant parsing), per ticker row:

```
price = lastTrade.p  or  min.c  or  day.c   # first present, in this order
```

If none are present, treat the ticker as "no price yet" (see §6).

## 6. Unknown / Not-Yet-Priced Tickers

- **Add validation:** when the user/AI adds a ticker, call the filtered snapshot (§4.3) for
  just that symbol. If the `tickers` array comes back empty (symbol omitted), the symbol is
  invalid → reject the add with `400` (PLAN §8).
- **Not yet polled:** a just-added valid ticker may have no cached price until the next poll
  lands. Trades against it are rejected with a "price not yet available" error until then
  (PLAN §8). This race exists only in Massive mode; the simulator assigns a seed price
  synchronously.

## 7. Reference Python Client (optional)

Massive ships an official Polygon-compatible client. FinAlly does **not** depend on it (we use
`httpx` directly for a small, tolerant parser — see MARKET_INTERFACE.md), but it's useful for
exploration:

```bash
pip install -U massive
```

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_API_KEY")   # defaults to api.massive.com

trade = client.get_last_trade(ticker="AAPL")
print(trade.price, trade.sip_timestamp)

snap = client.get_snapshot_ticker("stocks", "AAPL")
print(snap.last_trade.price, snap.prev_day.close)
```

## 8. Minimal Direct httpx Example (what FinAlly actually does)

A self-contained poll of the tracked set in one request, with tolerant parsing:

```python
import os
import httpx

BASE_URL = "https://api.massive.com"

def poll_prices(tickers: list[str], api_key: str) -> dict[str, dict]:
    """Return {ticker: {"price": float, "ts": float}} for all resolvable tickers."""
    url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
    params = {"tickers": ",".join(tickers)}
    headers = {"Authorization": f"Bearer {api_key}"}

    resp = httpx.get(url, params=params, headers=headers, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()

    out: dict[str, dict] = {}
    for row in data.get("tickers", []):
        sym = row.get("ticker")
        price = _resolve_price(row)
        if sym and price is not None:
            out[sym] = {"price": price, "ts": _resolve_ts(row)}
    return out


def _resolve_price(row: dict) -> float | None:
    for path in (("lastTrade", "p"), ("min", "c"), ("day", "c")):
        node = row.get(path[0]) or {}
        val = node.get(path[1])
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    return None


def _resolve_ts(row: dict) -> float:
    lt = row.get("lastTrade") or {}
    if "t" in lt:                       # nanoseconds
        return lt["t"] / 1e9
    mn = row.get("min") or {}
    if "t" in mn:                       # milliseconds
        return mn["t"] / 1e3
    return 0.0


if __name__ == "__main__":
    key = os.environ["MASSIVE_API_KEY"]
    print(poll_prices(["AAPL", "TSLA", "GOOGL"], key))
```

This function is the seam the `MassiveMarketData` provider wraps in
[MARKET_INTERFACE.md](./MARKET_INTERFACE.md).

## 9. Open Items to Confirm Against a Live Key

1. Exact host (`api.massive.com`) and that the Bearer header is honored (vs. `apiKey` only).
2. Whether `lastTrade` is included on the **free** tier or whether we must rely on
   `min.c` / `day.c` (15-min delayed). The parser already falls back, so either works.
3. Real free-tier rate limit (assumed ~5/min) to finalize the default poll interval.
4. Behavior of the filtered snapshot when *every* requested symbol is invalid (expect
   `count: 0`, empty `tickers`).

## Sources

- [Stock Market API | Massive](https://massive.com/)
- [Stocks REST API — Overview](https://massive.com/docs/rest/stocks/overview)
- [REST API Quickstart](https://massive.com/docs/rest/quickstart)
- [Single Ticker Snapshot](https://massive.com/docs/rest/stocks/snapshots/single-ticker-snapshot)
- [Full Market Snapshot](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot)
- [Last Trade](https://massive.com/docs/rest/stocks/trades-quotes/last-trade)
- [Previous Day Bar](https://massive.com/docs/rest/stocks/aggregates/previous-day-bar)
- [Official Python client (massive-com/client-python)](https://github.com/massive-com/client-python)
- [Pricing | Massive](https://massive.com/pricing)
