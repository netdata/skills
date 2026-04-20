#!/usr/bin/env bash
# End-to-end test: Netdata container + instrumented sample app + MCP probe.
#
# Usage:
#   run-e2e.sh nodejs|python            # local-agent MCP verify
#   run-e2e.sh nodejs|python cloud      # also claim to Cloud + verify
#                                       # there (requires env vars)
#
# Cloud-mode env vars (all required for `cloud`):
#   NETDATA_CLAIM_TOKEN        claim token from the target space
#   NETDATA_CLAIM_ROOMS        comma-separated room IDs
#   NETDATA_CLOUD_API_TOKEN    bearer token for the Cloud MCP probe
# Optional:
#   NETDATA_CLAIM_URL          default https://app.netdata.cloud
#   NETDATA_CLOUD_MCP_URL      default https://app.netdata.cloud/api/v1/mcp
#
# Host port overrides (see tests/e2e/README.md):
#   19998 -> Netdata dashboard+MCP  (container 19999)
#   4317  -> OTLP gRPC              (same inside container)
#   8088  -> sample app             (sample app internally listens on $PORT)

set -euo pipefail

LANG_=${1:-nodejs}
MODE=${2:-local}
cd "$(dirname "$0")"

if [ "$MODE" = "cloud" ]; then
  : "${NETDATA_CLAIM_TOKEN:?set NETDATA_CLAIM_TOKEN to run cloud mode}"
  : "${NETDATA_CLAIM_ROOMS:?set NETDATA_CLAIM_ROOMS to run cloud mode}"
  : "${NETDATA_CLOUD_API_TOKEN:?set NETDATA_CLOUD_API_TOKEN to run cloud mode}"
  export NETDATA_CLAIM_TOKEN NETDATA_CLAIM_ROOMS
  export NETDATA_CLAIM_URL="${NETDATA_CLAIM_URL:-https://app.netdata.cloud}"
fi

NETDATA_URL=http://localhost:19998
APP_URL=http://localhost:8088/hello
OTLP_ENDPOINT=http://localhost:4317

APP_PID=""

cleanup() {
  echo "[e2e] cleanup"
  if [ -n "${APP_PID:-}" ]; then
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
  docker compose down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "[e2e] =================================================="
echo "[e2e] starting Netdata container..."
docker compose up -d

echo "[e2e] waiting for Netdata web on :19998..."
for i in $(seq 1 40); do
  if curl -sf "$NETDATA_URL/api/v1/info" > /dev/null; then
    echo "[e2e]   Netdata reachable (attempt $i)"
    break
  fi
  sleep 3
  if [ "$i" = 40 ]; then
    echo "[e2e] ERROR: Netdata web never came up"
    docker compose logs netdata | tail -60
    exit 1
  fi
done

echo "[e2e] waiting for OTLP receiver on :4317..."
for i in $(seq 1 30); do
  if nc -zv localhost 4317 2>/dev/null; then
    echo "[e2e]   OTLP port open (attempt $i)"
    break
  fi
  sleep 2
  if [ "$i" = 30 ]; then
    echo "[e2e] ERROR: OTLP port never opened"
    docker compose logs netdata | grep -i otel | tail -30
    exit 1
  fi
done

echo "[e2e] installing $LANG_ sample app dependencies..."
cd "sample-apps/$LANG_"
if [ "$LANG_" = "nodejs" ]; then
  npm install --silent --no-audit --no-fund
  export OTEL_SERVICE_NAME="hello-nodejs"
  export OTEL_RESOURCE_ATTRIBUTES="service.version=0.1.0,deployment.environment=e2e"
  export OTEL_EXPORTER_OTLP_ENDPOINT="$OTLP_ENDPOINT"
  export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
  export PORT=8088
  node --require ./instrument.js index.js &
  APP_PID=$!
elif [ "$LANG_" = "python" ]; then
  python3 -m venv .venv
  # shellcheck source=/dev/null
  source .venv/bin/activate
  pip install -q -r requirements.txt
  export OTEL_SERVICE_NAME="hello-python"
  export OTEL_SERVICE_VERSION="0.1.0"
  export DEPLOYMENT_ENV="e2e"
  export OTEL_EXPORTER_OTLP_ENDPOINT="$OTLP_ENDPOINT"
  export PORT=8088
  python app.py &
  APP_PID=$!
else
  echo "[e2e] ERROR: unknown language '$LANG_'"
  exit 1
fi
cd ../..

echo "[e2e] sample app PID: $APP_PID"
echo "[e2e] waiting for sample app on :8088..."
for i in $(seq 1 30); do
  if curl -sf "$APP_URL" > /dev/null; then
    echo "[e2e]   sample app reachable (attempt $i)"
    break
  fi
  sleep 1
  if [ "$i" = 30 ]; then
    echo "[e2e] ERROR: sample app never came up"
    exit 1
  fi
done

echo "[e2e] generating traffic for 30 seconds..."
bash traffic.sh 30 "$APP_URL"

echo "[e2e] waiting 15 seconds for batch export..."
sleep 15

if [ "$LANG_" = "python" ]; then
  VERIFY_SIGNAL=both
else
  VERIFY_SIGNAL=metrics
fi

echo "[e2e] verifying arrived (signal=$VERIFY_SIGNAL)..."
python3 verify-metrics.py --app="$LANG_" --url="$NETDATA_URL" --signal="$VERIFY_SIGNAL"

if [ "$MODE" = "cloud" ]; then
  SERVICE_NAME="hello-$LANG_"
  echo "[e2e] waiting 45 seconds for Cloud stream + aggregation..."
  sleep 45
  echo "[e2e] verifying metrics arrived in Netdata Cloud..."
  python3 verify-metrics-cloud.py --service="$SERVICE_NAME"
fi

echo "[e2e] =================================================="
echo "[e2e] PASS"
