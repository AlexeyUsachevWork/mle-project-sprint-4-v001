#!/usr/bin/env bash
# Остановка сервисов, запущенных start_services.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="${ROOT}/scripts/.service_pids.txt"

if [[ ! -f "$PID_FILE" ]]; then
  echo "PID file not found: $PID_FILE"
  exit 0
fi

while read -r pid; do
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "stopped pid $pid"
  fi
done < "$PID_FILE"

# Освобождаем порты на случай «зависших» uvicorn
for port in 8000 8010 8020; do
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
    for pid in $pids; do
      kill "$pid" 2>/dev/null && echo "stopped listener on :$port (pid $pid)"
    done
  fi
done

rm -f "$PID_FILE"
echo "Done."
