# PeerForge — Local Development Runbook

AI-Powered Academic Peer Review platform for PhD students and researchers.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12 (not 3.14) | `brew install python@3.12` |
| Node.js | 18+ | `brew install node` |
| Colima (Docker runtime) | any | `brew install colima docker docker-compose` |
| PostgreSQL client | 15 | `brew install postgresql@15` |
| MinIO client | any | `brew install minio/stable/mc` |

> **Docker Desktop alternative**: PeerForge uses [Colima](https://github.com/abiosoft/colima) as a lightweight Docker runtime. If Docker Desktop is not running you can use Colima:
> ```bash
> colima start --cpu 2 --memory 4 --disk 20
> ```

---

## Quick Start (from scratch)

### 1. Start Infrastructure (Postgres + Redis + MinIO)

```bash
# Start Colima VM (if Docker Desktop isn't running)
colima start --cpu 2 --memory 4 --disk 20

cd arinar-v2/infra/docker
docker compose -f docker-compose.dev.yml up -d

# Verify all 3 containers are Up
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected output:
```
peerforge-db      Up …   0.0.0.0:5433->5432/tcp
peerforge-redis   Up …   0.0.0.0:6379->6379/tcp
peerforge-minio   Up …   0.0.0.0:9000-9001->9000-9001/tcp
```

### 2. Run Database Migrations

```bash
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
DB="postgresql://postgres:postgres@localhost:5433/peerforge_local"

# Create database (if first time)
psql postgresql://postgres:postgres@localhost:5433/postgres -c "CREATE DATABASE peerforge_local;"

# Apply all migrations (including dev seed)
cd arinar-v2
for f in infra/supabase/migrations/*.sql; do
  echo "→ $f"
  psql "$DB" -f "$f" 2>&1 | grep -v "^--" | tail -3
done
```

> Role errors (`service_role`, `anon`, `authenticated`) are Supabase-specific RLS roles and are expected — they do not affect the core schema.

### 3. Create MinIO Bucket

```bash
mc alias set peerforge http://localhost:9000 minioadmin minioadmin
mc mb peerforge/peerforge-materials
mc anonymous set public peerforge/peerforge-materials
```

### 4. Install Python Dependencies

```bash
cd arinar-v2/apps/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Configure Environment Files

**`apps/api/.env`** (already committed — review/update):
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/peerforge_local
REQUIRE_AUTH=false
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=peerforge-materials
REDIS_URL=redis://localhost:6379/0
OPENROUTER_API_KEY=your-openrouter-api-key-here
# Optional:
# SEMANTIC_SCHOLAR_API_KEY=your-key
# JINA_API_KEY=your-key
```

**`apps/web/.env.local`** (already committed — review/update):
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_AUTH_MODE=development
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=dev-anon-key-placeholder
```

### 6. Start the FastAPI Backend

```bash
cd arinar-v2/apps/api
source .venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify: `curl http://localhost:8000/health` → `{"status":"healthy"}`

### 7. Start the Celery Worker

In a separate terminal:
```bash
cd arinar-v2/apps/api
source .venv/bin/activate
# Must include all three queues — material processing uses the "materials" queue,
# preflight uses "preflight"; omitting them leaves uploaded files stuck at "pending".
celery -A src.celery_app worker --loglevel=info --queues=celery,materials,preflight
```

### 8. Install Frontend Dependencies & Start Dev Server

In a separate terminal:
```bash
cd arinar-v2/apps/web
npm install
npm run dev
```

App available at: **http://localhost:3000**

### 9. Add Your OpenRouter API Key

Visit **http://localhost:3000/settings** → paste your [OpenRouter](https://openrouter.ai) API key.

Without a key, AI turns return placeholder text.

---

## Smoke Test (End-to-End)

```bash
WS="00000000-0000-0000-0000-000000000101"

# 1. Health
curl http://localhost:8000/health

# 2. Create a review session
DEBATE=$(curl -s -X POST http://localhost:8000/debates/setup \
  -H "Content-Type: application/json" \
  -d "{
    \"workspace_id\": \"$WS\",
    \"title\": \"Sparse Transformer Attention\",
    \"problem_statement\": \"Novel sparse attention reducing quadratic to linear complexity.\",
    \"enable_host\": true,
    \"participants\": [
      {\"name\":\"Review Chair\",\"role_description\":\"Neutral chair\",\"system_prompt\":\"You are a Review Chair.\",\"model_id\":\"openai/gpt-4o-mini\"},
      {\"name\":\"Methodologist\",\"role_description\":\"Methods expert\",\"system_prompt\":\"You are a Methodologist.\",\"model_id\":\"openai/gpt-4o-mini\"}
    ],
    \"materials\": []
  }" | python3 -c "import json,sys; print(json.load(sys.stdin)['debate_id'])")
echo "Debate: $DEBATE"

# 3. Literature search (arXiv — no key needed)
curl -s -X POST "http://localhost:8000/debates/$DEBATE/literature/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"sparse attention transformer","sources":["arxiv"],"max_results":3}' | python3 -c "
import json,sys; d=json.load(sys.stdin)
for p in d['papers'][:2]: print(p['year'], p['title'][:60])"

# 4. Start review
curl -s -X POST "http://localhost:8000/debates/$DEBATE/start" | python3 -c "import json,sys; print('state:', json.load(sys.stdin)['state'])"

# 5. Trigger preflight (agent preparation)
curl -s -X POST "http://localhost:8000/debates/$DEBATE/preflight/start" | python3 -c "import json,sys; d=json.load(sys.stdin); print('preflight:', d['status'], 'participants:', d['participant_count'])"

# 6. Agent templates (verify 22 academic reviewers loaded)
curl -s http://localhost:8000/agent-templates | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} templates loaded')"
```

---

## Key URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| PeerForge Web App | http://localhost:3000 | dev bypass (no login needed) |
| API docs (Swagger) | http://localhost:8000/docs | — |
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin` |
| Postgres | localhost:5433 | `postgres` / `postgres` |
| Redis | localhost:6379 | — |

---

## 5-Stage Review Flow

```
Stage 1 → Idea & Scope        (BasicInfoStep)      Research question, agenda, objectives
Stage 2 → Document Ingestion  (MaterialsStep)      Upload draft/proposal/notes → Celery OCR/chunk
Stage 3 → AI Reviewer Selection (ParticipantsStep) Pick from 22 academic reviewer personas
Stage 4 → Prior Memory Recall (MemoryImportStep)   Import context from past review sessions
Stage 5 → Literature Search   (LiteratureStep)     arXiv / Semantic Scholar / PubMed / Crossref
Stage 6 → Deep-Research Debate + Peer-Review Report (Room)
```

---

## Architecture Notes

- **REQUIRE_AUTH=false** → all API calls use fixed workspace `00000000-0000-0000-0000-000000000101`
- **LLM calls** require an OpenRouter API key (set via Settings page); without it, agent turns return placeholder text
- **Celery worker** processes: document OCR/chunking, preflight agent prep packs, embeddings
- **Literature search** (arXiv, PubMed, Crossref/OpenAlex) requires no API keys; Semantic Scholar works better with a key

---

## Troubleshooting

### Docker won't start
```bash
colima start --cpu 2 --memory 4   # use Colima instead of Docker Desktop
docker context use colima
```

### Port 5432 already in use
The dev compose maps Postgres to port **5433** to avoid conflicts. `DATABASE_URL` is already set to port 5433.

### `psycopg2` build error
```bash
pip install psycopg2-binary  # use the binary wheel
```

### npm install fails (disk full)
```bash
rm -rf ~/.npm ~/.npm/_cacache
pip cache purge
# Then retry npm install
```

### `@popperjs/core` webpack error
Already fixed in `next.config.js` via webpack alias to the CJS bundle.

### API 500 on `/debates/{id}/literature/search`
Run the latest migrations — the `autonomous_mode` column may be missing:
```bash
psql "$DB" -f infra/supabase/migrations/20260601000002_autonomous_columns.sql
```

### Workspace not found (FK violation on debate creation)
Run the dev seed migration:
```bash
psql "$DB" -f infra/supabase/migrations/20260601000003_dev_seed.sql
```
