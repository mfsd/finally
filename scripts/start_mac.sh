#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="finally"
CONTAINER_NAME="finally"
PORT=8000

cd "$PROJECT_ROOT"

# Parse flags
BUILD=false
for arg in "$@"; do
  case $arg in
    --build|-b) BUILD=true ;;
  esac
done

# Check if image exists
if ! docker image inspect "$IMAGE_NAME" &>/dev/null || [ "$BUILD" = "true" ]; then
  echo "Building FinAlly Docker image..."
  docker build -t "$IMAGE_NAME" .
fi

# Stop existing container if running
if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
  echo "Stopping existing container..."
  docker stop "$CONTAINER_NAME" && docker rm "$CONTAINER_NAME"
elif docker ps -aq -f name="$CONTAINER_NAME" | grep -q .; then
  docker rm "$CONTAINER_NAME"
fi

# Ensure .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
  echo "Warning: .env not found. Copying from .env.example..."
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

echo "Starting FinAlly..."
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "$PORT:8000" \
  -v finally-data:/app/db \
  --env-file "$PROJECT_ROOT/.env" \
  "$IMAGE_NAME"

echo ""
echo "FinAlly is running at http://localhost:$PORT"
echo ""
echo "To view logs: docker logs -f $CONTAINER_NAME"
echo "To stop:      ./scripts/stop_mac.sh"

# Open browser after a short wait (macOS only)
sleep 2
if command -v open &>/dev/null; then
  open "http://localhost:$PORT"
fi
