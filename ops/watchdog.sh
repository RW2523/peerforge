#!/usr/bin/env bash
# PeerForge 24/7 watchdog — idempotent; safe to run every 2 min from cron.
# Ensures: docker services, backend API, cloudflared tunnels, frontend (prod build),
# and keeps the frontend pointed at the current backend tunnel URL.

set -u
ROOT="/home/echomind/Desktop/peerforge"
API_DIR="$ROOT/apps/api"
WEB_DIR="$ROOT/apps/web"
OPS="$ROOT/ops"
LOGS="$OPS/logs"
CF="$HOME/bin/cloudflared"
mkdir -p "$LOGS"

exec 9>"$OPS/.watchdog.lock"
flock -n 9 || exit 0

export PATH="/usr/local/bin:/usr/bin:/bin:$HOME/bin"
log() { echo "[$(date '+%F %T')] $*" >> "$LOGS/watchdog.log"; }

# ── 1. Docker infra ─────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q '^arinar-db$'; then
  log "starting docker services"
  docker compose -f "$ROOT/infra/docker/docker-compose.yml" up -d db redis minio >> "$LOGS/watchdog.log" 2>&1
  sleep 10
fi

# ── 2. Backend API (port 8000) ──────────────────────────────────
# Restart only after 3 consecutive failed health checks (a busy server that is
# slow to answer once must not be killed mid-request).
if curl -sf -m 15 http://localhost:8000/health > /dev/null; then
  echo 0 > "$OPS/.api-fails"
else
  FAILS=$(( $(cat "$OPS/.api-fails" 2>/dev/null || echo 0) + 1 ))
  echo "$FAILS" > "$OPS/.api-fails"
  log "backend health check failed ($FAILS/3)"
  if [ "$FAILS" -ge 3 ]; then
    log "backend unhealthy 3x — restarting"
    echo 0 > "$OPS/.api-fails"
    pkill -f 'uvicorn src.main:app' 2>/dev/null || true
    sleep 2
    cd "$API_DIR"
    nohup .venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 \
      >> "$LOGS/api.log" 2>&1 &
    sleep 5
  fi
fi

# ── 3. Backend tunnel (public URL for API) ──────────────────────
if ! pgrep -f 'cloudflared.*localhost:8000' > /dev/null; then
  log "starting backend tunnel"
  rm -f "$LOGS/cf-backend.log"
  nohup "$CF" tunnel --url http://localhost:8000 --no-autoupdate \
    >> "$LOGS/cf-backend.log" 2>&1 &
  for i in $(seq 1 30); do
    grep -q 'trycloudflare.com' "$LOGS/cf-backend.log" 2>/dev/null && break
    sleep 2
  done
fi
BACKEND_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOGS/cf-backend.log" 2>/dev/null | head -1)
# fall back to last known URL if log rotated
[ -n "$BACKEND_URL" ] && echo "$BACKEND_URL" > "$OPS/.backend-url" || BACKEND_URL=$(cat "$OPS/.backend-url" 2>/dev/null || true)

# ── 4. Frontend env sync + rebuild on URL change ────────────────
REBUILD=0
if [ -n "$BACKEND_URL" ]; then
  CUR=$(grep '^NEXT_PUBLIC_API_URL=' "$WEB_DIR/.env.local" | cut -d= -f2-)
  if [ "$CUR" != "$BACKEND_URL" ]; then
    log "backend URL changed: $CUR -> $BACKEND_URL — resyncing frontend"
    WS_URL="wss://${BACKEND_URL#https://}"
    sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=$BACKEND_URL|; s|^NEXT_PUBLIC_WS_URL=.*|NEXT_PUBLIC_WS_URL=$WS_URL|" "$WEB_DIR/.env.local"
    REBUILD=1
  fi
fi
if [ ! -d "$WEB_DIR/.next" ]; then
  REBUILD=1
fi
if [ "$REBUILD" = "1" ]; then
  log "building frontend"
  cd "$WEB_DIR"
  npm run build >> "$LOGS/web-build.log" 2>&1 || { log "frontend build FAILED"; }
  pkill -f 'next start' 2>/dev/null || true
  pkill -f 'next-server' 2>/dev/null || true
  sleep 2
fi

# ── 5. Frontend (port 3001, production server) ──────────────────
if ! curl -sf -m 5 -o /dev/null http://localhost:3001; then
  log "frontend down — starting"
  pkill -f 'next start' 2>/dev/null || true
  pkill -f 'next-server' 2>/dev/null || true
  sleep 2
  cd "$WEB_DIR"
  nohup npx next start -p 3001 >> "$LOGS/web.log" 2>&1 &
  sleep 5
fi

# ── 6. Frontend tunnel ──────────────────────────────────────────
if ! pgrep -f 'cloudflared.*localhost:3001' > /dev/null; then
  log "starting frontend tunnel"
  rm -f "$LOGS/cf-frontend.log"
  nohup "$CF" tunnel --url http://localhost:3001 --no-autoupdate \
    >> "$LOGS/cf-frontend.log" 2>&1 &
  for i in $(seq 1 30); do
    grep -q 'trycloudflare.com' "$LOGS/cf-frontend.log" 2>/dev/null && break
    sleep 2
  done
fi
FRONTEND_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOGS/cf-frontend.log" 2>/dev/null | head -1)
[ -n "$FRONTEND_URL" ] && echo "$FRONTEND_URL" > "$OPS/.frontend-url" || FRONTEND_URL=$(cat "$OPS/.frontend-url" 2>/dev/null || true)

# ── 7. Status file ──────────────────────────────────────────────
cat > "$OPS/current-urls.txt" <<EOF
Updated:  $(date '+%F %T')
App:      $FRONTEND_URL
API:      $BACKEND_URL
EOF
