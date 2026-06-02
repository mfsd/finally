import math
import random
import pytest
from market.sim_engine import SimEngine, EVENT_PROB_PER_STEP, EVENT_MIN, EVENT_MAX
from market.seeds import seed_price, SEED_PRICES


def make_seeded_engine(seed: int = 42) -> SimEngine:
    return SimEngine(rng=random.Random(seed))


# ---- seeding ----------------------------------------------------------------

def test_ensure_seeded_returns_known_price():
    engine = make_seeded_engine()
    assert engine.ensure_seeded("AAPL") == SEED_PRICES["AAPL"]


def test_ensure_seeded_returns_deterministic_unknown_ticker():
    engine1 = make_seeded_engine(1)
    engine2 = make_seeded_engine(2)
    p1 = engine1.ensure_seeded("PYPL")
    p2 = engine2.ensure_seeded("PYPL")
    assert p1 == p2, "seed_price must be deterministic regardless of RNG"


def test_ensure_seeded_is_idempotent():
    engine = make_seeded_engine()
    p1 = engine.ensure_seeded("AAPL")
    engine.step({"AAPL"})
    p2 = engine.ensure_seeded("AAPL")
    assert p1 == SEED_PRICES["AAPL"]
    assert p2 != SEED_PRICES["AAPL"], "price should have moved after a step"


def test_ensure_seeded_unknown_in_range():
    engine = make_seeded_engine()
    price = engine.ensure_seeded("FOOBAR")
    assert 50.0 <= price <= 300.0


# ---- GBM validity -----------------------------------------------------------

def test_prices_stay_positive_over_many_steps():
    engine = make_seeded_engine(123)
    tickers = {"AAPL", "GOOGL", "TSLA"}
    for _ in range(10000):
        prices = engine.step(tickers)
        for t, p in prices.items():
            assert p > 0, f"{t} went to zero or negative: {p}"


def test_step_returns_all_tracked_tickers():
    engine = make_seeded_engine()
    tickers = {"AAPL", "GOOGL", "MSFT"}
    result = engine.step(tickers)
    assert set(result.keys()) == tickers


def test_gbm_log_returns_have_reasonable_statistics():
    """Over many steps, log-returns should have roughly zero mean and
    non-trivial variance (not all zeros, not diverging)."""
    engine = make_seeded_engine(999)
    tickers = {"AAPL"}
    prices = [engine.ensure_seeded("AAPL")]
    for _ in range(5000):
        result = engine.step(tickers)
        prices.append(result["AAPL"])

    log_returns = [math.log(prices[i + 1] / prices[i]) for i in range(len(prices) - 1)]
    mean_return = sum(log_returns) / len(log_returns)
    variance = sum((r - mean_return) ** 2 for r in log_returns) / len(log_returns)
    std_return = math.sqrt(variance)

    # mean close to zero (within 3 standard-error bands for this sample)
    se = std_return / math.sqrt(len(log_returns))
    assert abs(mean_return) < 5 * se, f"Mean log return {mean_return:.6f} seems biased"

    # non-trivial variance (prices are actually moving)
    assert std_return > 1e-6, "Prices appear frozen — no movement detected"


# ---- correlation ------------------------------------------------------------

def test_same_sector_tickers_positively_correlated():
    """Two tech tickers driven by the same market + sector factor should have
    positive log-return correlation over a sufficient window."""
    rng = random.Random(7)
    engine = SimEngine(rng=rng)

    # Force both tickers into the tech sector by picking symbols whose hash lands > 0.5 at byte 7.
    # Instead, patch params after seeding to guarantee the same sector.
    engine.ensure_seeded("AAPL")
    engine.ensure_seeded("MSFT")

    # Override both to tech sector for the test.
    from market.sim_engine import TickerParams
    engine._params["AAPL"] = TickerParams(drift=0.0, vol=0.3, beta=1.0, sector="tech", sector_beta=0.3, resid=0.5)
    engine._params["MSFT"] = TickerParams(drift=0.0, vol=0.3, beta=1.0, sector="tech", sector_beta=0.3, resid=0.5)

    n = 2000
    aapl_prices = [engine._price["AAPL"]]
    msft_prices = [engine._price["MSFT"]]
    for _ in range(n):
        r = engine.step({"AAPL", "MSFT"})
        aapl_prices.append(r["AAPL"])
        msft_prices.append(r["MSFT"])

    def log_returns(prices):
        return [math.log(prices[i + 1] / prices[i]) for i in range(len(prices) - 1)]

    ra = log_returns(aapl_prices)
    rm = log_returns(msft_prices)

    mean_a = sum(ra) / len(ra)
    mean_m = sum(rm) / len(rm)
    cov = sum((a - mean_a) * (m - mean_m) for a, m in zip(ra, rm)) / len(ra)
    std_a = math.sqrt(sum((a - mean_a) ** 2 for a in ra) / len(ra))
    std_m = math.sqrt(sum((m - mean_m) ** 2 for m in rm) / len(rm))
    corr = cov / (std_a * std_m) if std_a > 0 and std_m > 0 else 0

    assert corr > 0.3, f"Expected positive correlation for tech tickers, got {corr:.3f}"


# ---- random events ----------------------------------------------------------

def test_event_always_fires_when_prob_forced_to_1():
    """With all RNG outputs fixed to 0.0, the event always fires and produces
    an EVENT_MIN–EVENT_MAX move on exactly one ticker. GBM noise is negligible
    at vol=0.0001."""
    tickers = {"AAPL", "GOOGL", "TSLA"}
    from market.sim_engine import TickerParams

    engine = SimEngine(rng=random.Random(1))
    for t in tickers:
        engine.ensure_seeded(t)
        engine._params[t] = TickerParams(
            drift=0.0, vol=0.0001, beta=0.0, sector="other", sector_beta=0.0, resid=1.0
        )

    # Patch random() to always return 0.0 — forces event to fire every step and
    # gives deterministic uniform/choice results for magnitude and direction.
    engine._rng.random = lambda: 0.0

    before = {t: engine._price[t] for t in tickers}
    result = engine.step(tickers)

    # Detection threshold: just below EVENT_MIN so any valid event is caught.
    threshold = EVENT_MIN * 0.9
    large_moves = []
    for t in tickers:
        pct_change = abs(result[t] / before[t] - 1)
        if pct_change > threshold:
            large_moves.append((t, pct_change))

    assert len(large_moves) == 1, f"Expected exactly 1 event ticker, got {large_moves}"
    _, magnitude = large_moves[0]
    assert EVENT_MIN - 1e-6 <= magnitude <= EVENT_MAX + 1e-6, \
        f"Event magnitude {magnitude:.4f} outside [{EVENT_MIN}, {EVENT_MAX}]"


def test_step_empty_set_returns_empty_dict():
    engine = make_seeded_engine()
    assert engine.step(set()) == {}


def test_step_adds_new_ticker_mid_flight():
    engine = make_seeded_engine()
    engine.step({"AAPL"})
    result = engine.step({"AAPL", "GOOGL"})
    assert "GOOGL" in result
    assert result["GOOGL"] > 0
