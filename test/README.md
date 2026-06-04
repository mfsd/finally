# FinAlly E2E Tests

This directory owns the Playwright integration suite for the fully integrated app.

## Run

Against an already running app:

```bash
cd test
npm install
APP_BASE_URL=http://127.0.0.1:8000 npm test
```

With Docker Compose once the production `Dockerfile` exists:

```bash
docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright
```

The test environment sets `LLM_MOCK=true` by default.

## Expected Frontend Hooks

The tests prefer accessible roles and labels, but these `data-testid` hooks make the suite stable:

- `watchlist`, `watchlist-row-AAPL`, `watchlist-symbol-input`, `add-watchlist-button`, `remove-PYPL`
- `cash-balance`, `connection-status`
- `trade-symbol-input`, `trade-quantity-input`, `buy-button`, `sell-button`
- `positions-table`, `position-row-AAPL`
- `portfolio-heatmap`, `pnl-chart`
- `ai-chat`, `chat-input`, `chat-send-button`

Equivalent accessible labels/roles are acceptable when they identify the same controls and regions.
