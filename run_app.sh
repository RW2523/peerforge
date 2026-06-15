#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$ROOT_DIR/apps/api"
WEB_DIR="$ROOT_DIR/apps/web"
COMPOSE_FILE="$ROOT_DIR/infra/docker/docker-compose.yml"

BACKEND_PORT=8000
FRONTEND_PORT=3001

echo "=========================================="
echo "Starting Arinar V2 application..."
echo "Project root: $ROOT_DIR"
echo "=========================================="

cd "$ROOT_DIR"

echo ""
echo "Step 1: Starting Docker services..."
docker compose -f "$COMPOSE_FILE" up -d db redis minio

echo ""
echo "Step 2: Creating backend .env.local..."
cat > "$API_DIR/.env.local" <<ENVEOF
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
REQUIRE_AUTH=false
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=peerforge-materials
MINIO_SECURE=false
OPENROUTER_API_KEY=
JINA_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=
TAVILY_API_KEY=
ENVEOF

echo ""
echo "Step 3: Creating frontend .env.local..."
cat > "$WEB_DIR/.env.local" <<ENVEOF
NEXT_PUBLIC_API_URL=http://localhost:$BACKEND_PORT
NEXT_PUBLIC_WS_URL=ws://localhost:$BACKEND_PORT
NEXT_PUBLIC_AUTH_MODE=development
NEXT_PUBLIC_TEST_TOKEN=dev-bypass-token
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=dev-anon-key
ENVEOF

echo ""
echo "Step 4: Setting up backend Python environment..."
cd "$API_DIR"

if [ ! -d ".venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if [ ! -f ".venv/.deps_installed" ]; then
  echo "Installing backend dependencies..."
  pip install -r requirements.txt
  touch .venv/.deps_installed
else
  echo "Backend dependencies already installed. Skipping pip install."
fi

echo ""
echo "Step 5: Applying database migrations..."
cd "$ROOT_DIR"
make db-migrate

echo ""
echo "Step 6: Setting up frontend dependencies..."
cd "$WEB_DIR"

if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
else
  echo "Frontend dependencies already installed. Skipping npm install."
fi

echo ""
echo "Step 7: Starting backend and frontend..."
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo ""
echo "Press Ctrl+C to stop both servers."
echo "=========================================="

cd "$API_DIR"
source .venv/bin/activate
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

sleep 3

cd "$WEB_DIR"
npm run dev -- -p "$FRONTEND_PORT" &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "Stopping servers..."
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
  echo "Servers stopped."
}

trap cleanup EXIT INT TERM

wait
