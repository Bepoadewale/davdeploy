#!/usr/bin/env bash
set -euo pipefail

api_base="${DAVDEPLOY_API_BASE_URL:-http://127.0.0.1:8080}"
executor_base="${DAVDEPLOY_EXECUTOR_BASE_URL:-http://127.0.0.1:8090}"
prometheus_base="${DAVDEPLOY_PROMETHEUS_BASE_URL:-http://127.0.0.1:9090}"
grafana_base="${DAVDEPLOY_GRAFANA_BASE_URL:-http://127.0.0.1:3000}"
tempo_base="${DAVDEPLOY_TEMPO_BASE_URL:-http://127.0.0.1:3200}"
opa_base="${DAVDEPLOY_OPA_BASE_URL:-http://127.0.0.1:8181}"

wait_for() {
  local label="$1" url="$2"
  for _ in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null 2>&1; then echo "$label ready"; return 0; fi
    sleep 1
  done
  echo "$label did not become ready: $url" >&2
  exit 1
}

wait_for api "${api_base%/}/healthz"
docker compose ps --status running worker | grep -q worker
echo "worker ready"
wait_for executor "${executor_base%/}/healthz"
wait_for prometheus "${prometheus_base%/}/-/ready"
wait_for grafana "${grafana_base%/}/api/health"
wait_for tempo "${tempo_base%/}/ready"
curl -fsS "${opa_base%/}/health" >/dev/null
echo "OPA ready"
