#!/bin/bash
set -euo pipefail

# Always resolve paths relative to this script's own location, not the caller's
# cwd — running `bash path/to/init.sh` from elsewhere must not silently cd into
# the wrong tree.
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d backend ] || [ ! -d frontend ]; then
  echo "error: expected backend/ and frontend/ next to init.sh — run this from the repo root." >&2
  exit 1
fi
for tool in uv npm curl openssl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "error: '$tool' is not on PATH. Install it and re-run." >&2
    exit 1
  fi
done

echo "=== Bootstrapping dev environment ==="

# Subshells so a failed step can never strand the working directory in a
# child folder for whatever runs next (set -e's exit-on-error inside a `cmd &&
# cmd` chain is unreliable across shells — a subshell makes this safe either way).
( cd backend && uv sync )
( cd frontend && npm ci )

# Environment — backend/.env and frontend/.env must never exist on disk
# (backend/tests/unit/test_config.py::TestGitignore::test_no_real_env_file_exists_on_disk
# asserts this). Export real shell env vars instead; see backend/.env.example and
# frontend/.env.example for the full documented list and defaults.
export DATABASE_URL="${DATABASE_URL:-sqlite:///./wealthwise.db}"
if [ -z "${JWT_SECRET:-}" ]; then
  JWT_SECRET="$(openssl rand -hex 32)"
  export JWT_SECRET
  echo "Generated a JWT_SECRET for this run (set your own to keep tokens valid across restarts)."
fi
export JWT_ACCESS_TOKEN_EXPIRY_MINUTES="${JWT_ACCESS_TOKEN_EXPIRY_MINUTES:-60}"
export DEFAULT_DRIFT_THRESHOLD_PERCENT="${DEFAULT_DRIFT_THRESHOLD_PERCENT:-5}"
export SEED_CSV_PATH="${SEED_CSV_PATH:-seed}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-http://localhost:5173}"
export VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:8000}"

# Migrate (idempotent) and seed (idempotent) before the server starts serving traffic.
echo "Running migrations and seed data..."
( cd backend && uv run alembic upgrade head )
( cd backend && uv run python -c "
from src.db.session import get_session_factory, session_scope
from src.db.seed import seed_database
with session_scope(get_session_factory()) as s:
    seed_database(s)
" )

# Local dev servers (no Docker — verification.mode = local). No --reload: a
# generator-only reload watcher was found to desync the app's env/process
# lifecycle across requests (see claude-progress.txt, Group F/G notes).
echo "Starting backend (uvicorn) and frontend (vite) dev servers..."
( cd backend && uv run uvicorn src.app.main:app --host 0.0.0.0 --port 8000 ) &
( cd frontend && npm run dev -- --port 5173 ) &

# Health checks
echo "Waiting for services..."
for i in $(seq 1 10); do
  curl -sf http://localhost:8000/health >/dev/null && break || sleep 2
done
for i in $(seq 1 10); do
  curl -sf http://localhost:5173 >/dev/null && break || sleep 2
done

echo "=== Environment ready ==="
echo "Backend:  http://localhost:8000  (docs at /docs)"
echo "Frontend: http://localhost:5173"
echo "Demo accounts: backend/seed/demo_accounts.json, password WealthWise-Demo-Synthetic-2026!"

wait
