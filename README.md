# FinAlly — the Finance Ally

An AI-powered trading workstation: stream live market data, trade a simulated
$10,000 portfolio, and chat with an LLM copilot that can analyze your positions
and execute trades on your behalf. It looks and feels like a modern Bloomberg
terminal with an AI assistant built in.

> Capstone project for an agentic AI coding course — built entirely by
> orchestrated coding agents. No login, no signup, fake money, zero stakes.

## Features

- **Live prices** streamed over SSE, with green/red flash animations and
  progressive sparklines
- **Simulated trading** — market orders, instant fill, fractional shares
- **Portfolio analytics** — positions table, P&L treemap heatmap, and a
  portfolio-value chart over time
- **AI chat copilot** that analyzes your portfolio and auto-executes trades and
  watchlist changes from natural language
- **Market simulator by default** (geometric Brownian motion), with optional
  real data via the Massive API

## Architecture

A single Docker container on one port (8000):

- **Frontend** — Next.js + TypeScript, static export, served by the backend
- **Backend** — FastAPI (Python, managed with `uv`); REST + SSE on `/api/*`
- **Database** — SQLite, lazily initialized and seeded on first request
- **AI** — LiteLLM → OpenRouter (`gpt-oss-120b` via Cerebras), structured outputs

Same origin throughout, so no CORS in production.

## Quick Start

Requires Docker and an [OpenRouter](https://openrouter.ai) API key.

```bash
cp .env.example .env        # then add your OPENROUTER_API_KEY
./scripts/start_mac.sh      # macOS/Linux  (Windows: scripts/start_windows.ps1)
```

Open <http://localhost:8000>. Stop with `./scripts/stop_mac.sh` (data persists in
a Docker volume).

## Configuration

Set in `.env` (see `.env.example`):

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | yes | Enables the AI chat assistant |
| `MASSIVE_API_KEY` | no | Use real market data; falls back to the simulator if empty |
| `LLM_MOCK` | no | `true` returns deterministic mock LLM responses (for tests) |

## Documentation

The full specification lives in [`planning/PLAN.md`](planning/PLAN.md) — vision,
architecture, schema, API endpoints, and design decisions.

## License

[MIT](LICENSE)
