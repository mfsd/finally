# FinAlly — the Finance Ally

An AI-powered trading workstation: live market data, a simulated portfolio, and an LLM chat assistant that can analyze positions and execute trades on your behalf. A Bloomberg-style terminal with an AI copilot.

> Capstone for an agentic AI coding course — built entirely by orchestrated coding agents.

## Features

- Live price streaming (SSE) with green/red flash animations and sparklines
- Simulated trading — market orders, instant fill, $10,000 starting cash
- Portfolio views — positions table, P&L chart, and P&L-colored treemap
- AI assistant — chat to analyze your portfolio, trade, and manage your watchlist

## Architecture

A single Docker container on port 8000:

- **Frontend** — Next.js + TypeScript static export, served by FastAPI
- **Backend** — FastAPI (Python, `uv`)
- **Database** — SQLite, volume-mounted, lazily initialized and seeded
- **Real-time** — Server-Sent Events (`/api/stream/prices`)
- **Market data** — built-in GBM simulator by default; real data via Massive API if a key is set
- **AI** — LiteLLM → OpenRouter (`openai/gpt-oss-120b` on Cerebras), structured outputs

## Quick Start

```bash
cp .env.example .env    # add your OPENROUTER_API_KEY
./scripts/start_mac.sh  # start_windows.ps1 on Windows
```

Open http://localhost:8000. Stop with `./scripts/stop_mac.sh`.

## Configuration

`.env` keys (see `.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | yes | Enables the LLM chat assistant |
| `MASSIVE_API_KEY` | no | Real market data; omit for the simulator |
| `LLM_MOCK` | no | `true` for mock LLM responses (testing) |

## Documentation

Full specification: [`planning/PLAN.md`](planning/PLAN.md).
