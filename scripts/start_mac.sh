#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
IMAGE_NAME="${FINALLY_IMAGE:-finally:latest}"
CONTAINER_NAME="${FINALLY_CONTAINER:-finally-app}"
PORT="${FINALLY_PORT:-8000}"
ENV_FILE="$ROOT_DIR/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found in PATH." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  echo "Created .env from .env.example. Edit it to add API keys when needed."
fi

mkdir -p "$ROOT_DIR/db"

docker build -t "$IMAGE_NAME" "$ROOT_DIR"

if docker ps -a --format '{{.Names}}' | grep -Fx "$CONTAINER_NAME" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

docker run -d \
  --name "$CONTAINER_NAME" \
  --env-file "$ENV_FILE" \
  -e DB_PATH=/app/db/finally.db \
  -p "$PORT:8000" \
  -v "$ROOT_DIR/db:/app/db" \
  "$IMAGE_NAME" >/dev/null

echo "FinAlly is running at http://localhost:$PORT"
