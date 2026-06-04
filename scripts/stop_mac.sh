#!/usr/bin/env sh
set -eu

CONTAINER_NAME="${FINALLY_CONTAINER:-finally-app}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but was not found in PATH." >&2
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -Fx "$CONTAINER_NAME" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER_NAME" >/dev/null
  echo "Stopped $CONTAINER_NAME."
else
  echo "$CONTAINER_NAME is not running."
fi
