#!/usr/bin/env bash
DURATION=${1:-30}
ENDPOINT=${2:-http://localhost:8088/hello}
end=$((SECONDS + DURATION))
while [ $SECONDS -lt $end ]; do
  curl -sf "$ENDPOINT" > /dev/null || true
  sleep 0.2
done
