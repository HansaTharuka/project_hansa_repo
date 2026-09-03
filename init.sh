#!/bin/bash
set -euo pipefail

echo "=== Bootstrapping dev environment ==="

# Backend dependencies
cd backend && uv sync && cd ..

# Frontend dependencies
cd frontend && npm ci && cd ..

# Environment
if [ -f ".env.example" ] && [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your API keys"
fi

# Local dev servers (no Docker — verification.mode = local)
echo "Starting backend (uvicorn) and frontend (vite) dev servers..."
( cd backend && uv run uvicorn app.main:app --reload --port 8000 ) &
( cd frontend && npm run dev -- --port 5173 ) &

# Health checks
echo "Waiting for services..."
for i in $(seq 1 5); do
  curl -sf http://localhost:8000/health && break || sleep 2
done
for i in $(seq 1 5); do
  curl -sf http://localhost:5173 >/dev/null && break || sleep 2
done

echo "=== Environment ready ==="
