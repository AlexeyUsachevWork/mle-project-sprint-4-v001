#!/usr/bin/env bash
# Запуск трёх микросервисов рекомендаций (Linux/macOS).
# Использование из корня репозитория:
#   bash scripts/start_services.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/env_recsys_start/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

# Проверяем артефакты этапа 3 до старта
"$PYTHON" -c "from app.paths import check_artifacts; m=check_artifacts(); import sys; sys.exit(1 if m else 0)" \
  || { echo "Сначала подготовьте recsys/recommendations/*.parquet"; exit 1; }

PID_FILE="${ROOT}/scripts/.service_pids.txt"
: > "$PID_FILE"

start_service() {
  local module="$1"
  local port="$2"
  # nohup — сервисы продолжают работать после закрытия терминала
  nohup "$PYTHON" -m uvicorn "$module" --host 127.0.0.1 --port "$port" \
    > "${ROOT}/scripts/uvicorn_${port}.log" 2>&1 &
  echo $! >> "$PID_FILE"
  echo "started $module on :$port (pid $!)"
}

echo "Starting services..."

# Event Store — без тяжёлой загрузки
start_service "app.events_service:app" 8020

# Feature Store грузит большой similar.parquet
start_service "app.features_service:app" 8010

wait_health() {
  local urls=("$@")
  local deadline=$((SECONDS + 600))
  while (( SECONDS < deadline )); do
    local all_up=1
    for url in "${urls[@]}"; do
      if ! curl -fsS "$url" >/dev/null 2>&1; then
        all_up=0
        break
      fi
    done
    if [[ "$all_up" -eq 1 ]]; then
      return 0
    fi
    sleep 5
  done
  return 1
}

if wait_health "http://127.0.0.1:8020/health" "http://127.0.0.1:8010/health"; then
  echo "Event + Feature stores are up."
else
  echo "WARNING: Event/Feature Store не поднялись за 10 минут."
fi

# Recommendation Store — после Feature Store (меньше пик RAM)
start_service "app.recommendations_service:app" 8000

if wait_health \
  "http://127.0.0.1:8020/health" \
  "http://127.0.0.1:8010/health" \
  "http://127.0.0.1:8000/health"; then
  echo "All services are up."
else
  echo "WARNING: health-check не прошёл за 10 минут. См. scripts/uvicorn_*.log"
fi

echo "PIDs saved to $PID_FILE"
echo "Run tests: python test_service.py > test_service.log"
