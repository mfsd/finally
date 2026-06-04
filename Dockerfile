# syntax=docker/dockerfile:1.7

FROM node:20-bookworm-slim AS frontend-builder
WORKDIR /src

COPY . .

RUN set -eux; \
    mkdir -p /frontend-out; \
    if [ -f frontend/package.json ]; then \
        cd frontend; \
        if [ -f package-lock.json ]; then npm ci --legacy-peer-deps; else npm install --legacy-peer-deps; fi; \
        npm run build; \
        if [ -d out ]; then cp -a out/. /frontend-out/; \
        elif [ -d dist ]; then cp -a dist/. /frontend-out/; \
        else echo "Frontend build completed, but no static export directory was found (expected frontend/out)." >&2; exit 1; \
        fi; \
    else \
        printf '%s\n' \
          '<!doctype html>' \
          '<html lang="en">' \
          '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FinAlly</title></head>' \
          '<body><main><h1>FinAlly backend is running</h1><p>The frontend static export has not been built into this image yet.</p></main></body>' \
          '</html>' > /frontend-out/index.html; \
    fi

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH" \
    DB_PATH="/app/db/finally.db"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && rm -rf /root/.local

COPY backend/pyproject.toml backend/uv.lock ./backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev --no-install-project

WORKDIR /app
COPY backend ./backend
COPY --from=frontend-builder /frontend-out ./backend/static
RUN mkdir -p /app/db

EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
