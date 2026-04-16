#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env nếu tồn tại
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"

echo "Khởi động Trung Tâm Tri Thức tại http://${HOST}:${PORT}/"
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
