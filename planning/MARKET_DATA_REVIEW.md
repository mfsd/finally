# Market Data Backend — Code Review

**Reviewer:** automated code review (Claude)
**Date:** 2026-06-02
**Scope:** `backend/market/*` and `backend/tests/market/*` as of `main` @ `0b86aaa`
(PR #4, "feat: build complete market data backend").
**Reference specs:** `PLAN.md` §6/§8/§12, `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`,
`MASSIVE_API.md`, `MARKET_DATA_DESIGN.md`.

---

## 1. Verdict

The implementation is a faithful, clean realization of the design docs: the unified
`MarketDataProvider` seam, the `PriceCache` bookkeeping, the single `MarketPoller`, the
env-driven factory, and both the simulator and Massive adapters are all present and closely
match the documented contracts. Code quality is high — small modules, clear docstrings, good
separation between the GBM **engine** and the provider **adapter**.

However, **the test suite does not pass as committed**, and one of the failures points to a
genuine calibration defect in the simulator, not a bad test:

| Severity | Issue | Effect |
|---|---|---|
| **Critical** | Syntax error in `test_types.py:34` | Aborts collection of the **entire** suite by default |
| **High** | Simulator correlation is statistically ~0 | A core design goal (correlated motion) is not met; one test fails |
| **Medium** | Package does not build (`uv sync` fails) | `uv sync`, Docker build, and `uv run` are all broken |
| **Medium** | No FastAPI app / SSE route wiring exists | Modules are unit-tested but not actually served anywhere |
| **Low** | Massive trade timestamps discarded; `_resolve_ts` unused in live path | `Quote.ts` is server-receive time, not trade time; dead code |
| **Low** | `resid` variance-normalization comment is inaccurate | Cosmetic; `var(z) ≈ 1` claim doesn't hold |

---

## 2. Test Run

Environment: Python 3.12 venv, deps `fastapi uvicorn httpx python-dotenv pytest
pytest-asyncio respx` (the project itself could not be installed — see §5.3).

**Default run (`pytest`):** collection is **aborted** by a `SyntaxError` and *no tests run*:

```
ERROR tests/market/test_types.py
E     File ".../tests/market/test_types.py", line 34
E       assert event := q.to_event()
E                    ^^
E   SyntaxError: invalid syntax
!!!!!!!! Interrupted: 1 error during collection !!!!!!!!
```

**With `--continue-on-collection-errors`:**

```
1 failed, 95 passed, 1 error in 1.61s
FAILED tests/market/test_sim_engine.py::test_same_sector_tickers_positively_correlated
ERROR  tests/market/test_types.py   (6 tests never collected)
```

So as committed: **0 tests pass on a normal invocation**; with the workaround, 95/101 pass,
1 fails, and 6 are uncollectable.

---

## 3. Critical — suite-aborting syntax error

`backend/tests/market/test_types.py:34`:

```python
assert event := q.to_event()        # SyntaxError
```

A bare assignment-expression after `assert` is invalid; the walrus must be parenthesized:

```python
assert (event := q.to_event())
```

Because this is a **collection-time** `SyntaxError`, pytest's default behavior aborts the whole
session — *every* market test is skipped, masking the state of the other 95 tests and the
correlation failure. Verified: with the parenthesized fix, all 6 `test_types.py` tests pass.

**Fix:** add the parentheses (one character each side). Consider also running pytest in CI with
the import-mode that surfaces such errors early, and treating collection errors as failures.

---

## 4. High — simulator correlation is effectively zero

`test_same_sector_tickers_positively_correlated` asserts two same-sector tickers have
log-return correlation `> 0.3`. It fails:

```
AssertionError: Expected positive correlation for tech tickers, got 0.000
assert 0.00030016411402055874 > 0.3
```

**This is a real defect, not a flaky/incorrect test.** Root-cause analysis:

1. The correlated shock `z` *is* computed correctly — measured `corr(z_AAPL, z_MSFT) = 0.807`,
   exactly as the shared-market-factor model predicts.
2. But the GBM step size is tiny. With `DT = 0.5 / (252·6.5·3600) ≈ 8.5e-8`, the per-step
   move is `σ·√dt`:

   | vol | per-step σ·√dt | design target (`MARKET_SIMULATOR.md` §6) |
   |---|---|---|
   | 0.20 | **0.0058%** | 0.05–0.15% |
   | 0.30 | **0.0087%** | 0.05–0.15% |
   | 0.60 | **0.0175%** | 0.05–0.15% |

   The actual GBM motion is **~10× below the document's own stated target** (i.e. `DT` is
   roughly 100× too small, since std scales with `√dt`).
3. The random "events" (`_maybe_event`) inject **2–5%** jumps (log-return ≈ 0.03) on a single
   **uncorrelated** ticker ~1% of steps. A single event is ~**290×** larger than a GBM tick, so
   event variance (~`0.01 × 0.03² ≈ 8.7e-6`) is ~**870×** the GBM variance (~`1e-8`). Events
   therefore dominate total variance and, being applied to one random ticker independently,
   wash the correlated GBM signal down to noise.

Empirical confirmation (events disabled): correlation jumps to **0.816**.

**Consequences beyond the test:** the simulator's headline features — drift, per-ticker
volatility, and inter-ticker correlation — are statistically and visually invisible. Almost all
observable price motion is random, uncorrelated event jumps. This contradicts goals 1, 3, and 4
in `MARKET_SIMULATOR.md` §1 ("realistic motion", "correlation", "deterministic dynamics") and
the PLAN §6 intent that tech stocks "move together".

**Suggested fix (calibration):**
- Increase `DT` by ~100× (or set a per-step `σ·√dt` directly) so GBM moves land in the
  documented 0.05–0.15% band — this makes drift/vol/correlation actually visible.
- Re-balance events so they read as occasional drama rather than the dominant signal: lower
  `EVENT_PROB_PER_STEP` and/or reduce magnitude relative to the (now larger) GBM step, so a
  typical minute is mostly correlated GBM with rare punctuating jumps.
- After re-calibration, the existing correlation test should pass without modification.

---

## 5. Medium-severity findings

### 5.1 No FastAPI app or SSE route is wired up
`MARKET_DATA_DESIGN.md` §8–§9 and `MARKET_INTERFACE.md` §6 describe `backend/app.py`
(lifespan: build cache + provider, synchronously seed the tracked set, start the poller) and a
`/api/stream/prices` route mounting `price_event_stream`. **Neither exists** — `backend/`
contains only `market/`, `tests/`, and `pyproject.toml`. The market layer is fully unit-tested
in isolation but is not actually served, so the end-to-end path (SSE → frontend, lifespan
seeding, injecting the `get_tracked_symbols(db)` callable) is unverified. If this PR was meant
to deliver only the market modules this is expected, but it is the main gap between
"implemented" and "running backend".

### 5.2 Simulator GBM step size disagrees with the design (see §4)
Tracked here as well because it is independently a spec-conformance issue, not only the cause
of the failing test.

### 5.3 Project does not build / install
`uv sync --extra dev` fails:

```
ValueError: Unable to determine which files to ship inside the wheel ...
no directory that matches the name of your project (finally_backend)
```

`pyproject.toml` declares `name = "finally-backend"` with the `hatchling` build backend, but
the package directory is `market/` and there is no `[tool.hatch.build.targets.wheel]`
configuration. Consequently `uv sync`, the Docker `uv sync` stage (PLAN §11), and `uv run
pytest` will all fail. Tests only ran here by creating a venv and installing dependencies
manually, relying on the `conftest.py` `sys.path` hack to import `market`.

**Fix:** add e.g.

```toml
[tool.hatch.build.targets.wheel]
packages = ["market"]
```

(or rename to a `finally_backend/` package, or set `tool.hatch.build.targets.wheel.only-include`).
Then `tests/conftest.py`'s `sys.path.insert` becomes unnecessary.

---

## 6. Low-severity findings

### 6.1 Massive trade timestamps are discarded; `_resolve_ts` is dead in the live path
`MassiveMarketData.get_prices` returns only `{ticker: price}` and the poller calls
`cache.update(ticker, price)` **without** `ts`, so `Quote.ts` is the server receive time, not
the trade SIP timestamp. `massive._resolve_ts` correctly normalizes ns/ms timestamps but is
only ever called from tests — it is dead code relative to the production path. Either thread the
resolved `ts` through `get_prices` → `cache.update(..., ts=...)`, or remove `_resolve_ts` to
avoid implying a behavior that doesn't happen. (The session-open baseline still works either
way, so this is minor.)

### 6.2 `resid` does not normalize `var(z)` to ~1
In `_derive_params`, `resid = max(0.2, sqrt(1 - 0.25·beta² - sector_beta²))` with the comment
"so total variance ≈ 1". The actual `var(z) = beta² + sector_beta² + resid²`. For
`beta=1.0, sector_beta=0.3, resid=0.5` that is `1.0 + 0.09 + 0.25 = 1.34`, not 1. The factor
weights don't achieve unit variance. Harmless given the tiny absolute vol, but the comment is
misleading and per-ticker effective volatility drifts from the configured `σ`.

### 6.3 `test_event_always_fires_when_prob_forced_to_1` over-stubs the RNG
The test sets `engine._rng.random = lambda: 0.0`, which also forces `gauss`/`uniform`/`choice`
inputs. It passes and is well-reasoned, but it couples to internal RNG call structure; a small
refactor of `step()`'s draw order could break it spuriously. Consider asserting on the event
mechanism more directly (e.g. patch `_maybe_event` inputs) if churn becomes a problem.

---

## 7. What is correct and well done

- **`PriceCache`** (`cache.py`): session-open-set-once, prev-price roll, `direction`, snapshot
  copy semantics, and `seed` no-op-when-present are all correct and thoroughly tested
  (`test_cache.py`, 12 cases).
- **`seeds.py`**: deterministic hashing into `$50–$300`, table override, determinism across
  processes — correct and well covered.
- **`MassiveMarketData`**: single-request filtered snapshot, tolerant
  `lastTrade.p → min.c → day.c` resolution, omission of unknown symbols, Bearer auth, dedup of
  the ticker list, `raise_for_status`, idempotent `aclose` — all correct, and `test_massive.py`
  exercises them well with `respx` fixtures.
- **`MarketPoller`**: dynamic tracked-set recomputed per poll, empty-set short-circuit,
  exception isolation (loop survives a transient provider error), and clean task
  cancellation/`aclose` on stop — correctly implemented and tested.
- **`get_tracked_symbols`**: the union (watchlist ∪ positions), user-id filtering, and the
  "held-but-unwatched still streams" invariant are correct and explicitly tested.
- **`price_event_stream`**: correct SSE framing (`event: prices\ndata: …\n\n`), heartbeat
  cadence, empty-cache skip, parameterized intervals for fast tests.
- **Adapter conformance**: both providers subclass `MarketDataProvider`; `seed_price`
  contract (sim never `None`, Massive always `None`) is honored and asserted.

Test coverage is broad (101 cases across 10 files) and generally meaningful, exercising the
PLAN §12 hooks (determinism, GBM positivity, parsing fallbacks, poller resilience, SSE shape).

---

## 8. Recommended actions (priority order)

1. **Fix the syntax error** in `test_types.py:34` (`assert (event := q.to_event())`). Without
   this, CI runs green-looking-but-empty or red, and all other results are hidden.
2. **Re-calibrate the simulator** (§4): raise `DT`/per-step σ into the documented 0.05–0.15%
   band and rebalance event probability/magnitude so correlated GBM is the dominant signal.
   Verify `test_same_sector_tickers_positively_correlated` passes afterward.
3. **Fix packaging** (§5.3): add `[tool.hatch.build.targets.wheel] packages = ["market"]` so
   `uv sync` / Docker / `uv run pytest` work; drop the `conftest.py` path hack.
4. **Wire the FastAPI app + SSE route** (§5.1) and add an integration test that boots the app,
   seeds the tracked set, and reads a frame from `/api/stream/prices`.
5. Address the low-severity items (Massive `ts` threading, `resid` normalization/comment) as
   cleanup.

Once items 1–2 are done, the suite should be **101 passed**.
