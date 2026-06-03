#!/usr/bin/env bash
set -e

CONTAINER_NAME="finally"

if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
  echo "Stopping FinAlly..."
  docker stop "$CONTAINER_NAME"
  docker rm "$CONTAINER_NAME"
  echo "FinAlly stopped."
else
  echo "FinAlly is not running."
  # Clean up stopped container if it exists
  if docker ps -aq -f name="$CONTAINER_NAME" | grep -q .; then
    docker rm "$CONTAINER_NAME"
  fi
fi
