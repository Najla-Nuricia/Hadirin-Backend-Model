#!/usr/bin/env bash
# Jalankan Hadirin Backend API dalam satu perintah: ./run.sh
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

# 1. Virtualenv
if [ ! -d .venv ]; then
  echo "==> Membuat virtualenv .venv ..."
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
else
  ./.venv/bin/python -c "import fastapi, uvicorn" 2>/dev/null || {
    echo "==> Dependency belum lengkap, install ulang ..."
    ./.venv/bin/pip install -q -r requirements.txt
  }
fi

# 2. File .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "!! .env dibuat dari .env.example."
  echo "!! Isi SUPABASE_URL, SUPABASE_SERVICE_KEY, JWT_SECRET_KEY lalu jalankan ulang ./run.sh"
  exit 1
fi

# 3. Start server
echo "==> Server: http://127.0.0.1:${PORT}/docs  (Ctrl+C untuk berhenti)"
exec ./.venv/bin/uvicorn app.main:app --reload --host "$HOST" --port "$PORT"
