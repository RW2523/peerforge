<div align="center">

# 🎓 PeerForge

### The auditable review-rehearsal platform for researchers

**Upload your manuscript → get interrogated by an AI review panel grounded in *your own* materials → rehearse your answers → walk away with a signed, publicly verifiable readiness record.**

Every other tool says *"trust me."* PeerForge shows the receipts — the verified source line behind every critique, or an honest admission that the materials don't back it up.

`Next.js` · `FastAPI` · `PostgreSQL` · `Redis` · `MinIO` · `Celery` · `OpenRouter` · `Ed25519`

</div>

---

## What is PeerForge?

PeerForge is an **AI academic peer-review rehearsal platform**. A PhD student, researcher, or author uploads their paper, thesis, or manuscript; PeerForge builds a panel of AI reviewers that critique it **grounded in the uploaded document itself**, lets the researcher practice answering the panel's questions (by text or voice), tracks their readiness across ten academic dimensions over time, and issues a **tamper-evident certificate** anyone can verify.

It is **not** a writing checker, a paraphraser, or a from-scratch article generator. It is a *rehearsal* tool — the researcher is the one under examination.

### The problem it solves

Researchers walk into thesis defenses and journal reviews under-prepared because realistic practice is scarce and expensive. Generic chatbots will happily critique a paper — but they hallucinate citations, can't prove their critiques come from the actual document, forget everything between sessions, and produce nothing an institution can trust. PeerForge closes that gap with **verifiable grounding** at every step.

### The USP: verifiability

The market is full of AI-review tools and even a few mock-viva tools. What no one else does — and what PeerForge is architected around — is **proving** the AI's critique against the researcher's own document:

- Every reviewer claim hard-links to the exact source chunk it quotes, with the chunk's **SHA-256 re-verified live**.
- When the AI *can't* ground a claim, it's flagged as an **evidence gap in the researcher's own writing** — turning the AI's weakness into an honest signal.
- The final readiness certificate is **Ed25519-signed** and anchored to an append-only evidence ledger, so a grad school or journal can verify it without logging in.

---

## The Three Pillars

| Pillar | What it does | Where |
|---|---|---|
| 🔍 **Glass-Box Provenance** | Every reviewer question & live panel turn hard-links to the source chunk it quotes; SHA-256 re-verified on view; unsupported claims flagged as evidence gaps; click through to the **actual PDF** with the passage highlighted. | *Evidence* tab |
| 👥 **Committee Twin** | Name the real people who'll sit on your panel → PeerForge pulls their **actual publications** (Crossref author search), ingests them as grounded corpus, and builds a reviewer twin that questions you citing *their own papers*. Twins can join the live panel. | *Committee* tab |
| 📜 **Readiness Certificate** | A per-dimension readiness **trajectory** across sessions, drill-down from every score to the answer → question → verified source line, and an **Ed25519-signed, publicly verifiable** export with a QR code. | *Certificate* tab |

---

## Features

### Session setup
- **6-step wizard** — research topic, materials, review panel, prior-session memory import, literature discovery, preflight & launch
- **AI panel suggestion** — ranks reviewer templates from your title + abstract
- **Draft autosave** to localStorage, session-length modes (time or rounds), autonomous "YOLO" mode
- **Reasoning modes** (light / medium / heavy) that route between cheap and frontier models per task

### Materials & RAG
- Upload PDF / DOCX / TXT / audio (transcribed) or paste text & links
- Async **Celery** pipeline: text extraction (+ scanned-PDF OCR detection) → semantic chunking with SHA-256, page numbers & char offsets → OpenRouter embeddings
- **Grant-based memory retrieval** with a full audit log; cross-session memory import
- **Literature search** across arXiv, Semantic Scholar, PubMed, Crossref & OpenAlex

### The review panel (multi-agent engine)
- **6 specialized reviewer lanes** — Advisor, Methodology Professor, Domain Expert, Skeptical Reviewer, Friendly Professor, Independent Examiner
- **3-stage constitutional pipeline** per turn — reason → respond → validate, with citation enforcement and no hallucinated references
- **Live provenance chips** on every panel message (Pillar 1)
- **@mention routing**, a host/chair that synthesizes a peer-review verdict, real-time WebSocket streaming, and a moderator intervene composer

### Practice, voice & assessment
- **Practice Q&A** with a 6-axis narrative evaluation (scores kept internal; only qualitative feedback shown — no marks/grades in the UI)
- **Voice practice** — the persona speaks questions (TTS), you dictate answers (STT) via the browser's Web Speech API
- **10-dimension academic assessment** that regenerates automatically as you work, building the readiness trajectory

### Verifiable outputs
- **Public `/verify/{id}` page** — recomputes signature validity, hash integrity, and live-evidence match with no login
- **QR code + share link** on the printable certificate
- **Progress dashboard** — a cohort view of every session's readiness band, trajectory, and issued certificates

### Trust demo
- **Side-by-side comparison**: ask a raw model (no document) for a critique's source — it fabricates one — next to PeerForge's SHA-256-verified line.

---

## Architecture

```
                          ┌──────────────────────────────┐
   Browser  ───────────►  │  Next.js 15 frontend (:3000) │
                          │  Room · Evidence · Committee  │
                          │  Certificate · Progress       │
                          └──────────────┬───────────────┘
                                         │  REST + WebSocket
                          ┌──────────────▼───────────────┐
                          │   FastAPI backend (:8000)     │
                          │   ~30 routers · auth · BYOK   │
                          └───┬───────────┬──────────┬────┘
                              │           │          │
              ┌───────────────▼──┐   ┌────▼─────┐  ┌─▼──────────────┐
              │  PostgreSQL      │   │  Redis   │  │  MinIO          │
              │  (:5433)         │   │  (:6379) │  │  (:9000)        │
              │  sessions,       │   │  Celery  │  │  uploaded files │
              │  chunks, events, │   │  broker  │  └────────────────┘
              │  certificates    │   └────┬─────┘
              └──────────────────┘        │
                                    ┌─────▼──────────┐
                                    │  Celery worker │
                                    │  materials ·   │
                                    │  preflight     │
                                    └────────────────┘

   LLM calls (BYOK) ─────────────►  OpenRouter  (embeddings + chat, all providers)
```

**Stack:** Next.js 15 (App Router, TypeScript) · FastAPI (Python 3.11) · PostgreSQL · Redis · MinIO/S3 · Celery · OpenRouter (only LLM provider, bring-your-own-key) · Supabase auth · Ed25519 signing (`cryptography`).

See [`docs/`](docs/) and the architecture ADRs in [`docs/architecture/`](docs/architecture/) for deeper detail.

---

## Repository structure

```
arinar-v2/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── src/routes/         # ~30 API routers (defense, assessment, materials, …)
│   │   ├── src/services/       # provenance, certificate, cert_signing, committee_twin, …
│   │   ├── src/tasks/          # Celery tasks (material processing, preflight)
│   │   └── migrations/         # numbered SQL migrations
│   └── web/                    # Next.js frontend
│       └── src/
│           ├── app/            # routes: room, history, progress, verify/[id], setup, …
│           ├── components/room # GlassBoxPanel, CommitteeTwinBuilder, ReadinessCertificate, …
│           └── lib/api.ts      # typed API client
├── infra/docker/               # docker-compose (db, redis, minio)
├── docs/                       # architecture, product, runbooks (+ archive/)
├── run_app.sh                  # one-command local startup
└── Makefile                    # install / lint / typecheck / test / db-* targets
```

---

## Quick start

### Prerequisites
- **Docker Desktop**, **Node.js 20+**, **Python 3.11**
- An **[OpenRouter API key](https://openrouter.ai/)** (bring your own; used for all LLM + embedding calls)

### 1 · Infrastructure (Postgres, Redis, MinIO)
```bash
cd arinar-v2
docker compose -f infra/docker/docker-compose.yml up -d db redis minio
```

### 2 · Backend (FastAPI + Celery)
```bash
cd apps/api
cp .env.example .env                     # then fill in values
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# apply migrations (see migrations/ for the ordered SQL files)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 &

# Celery worker (or set CELERY_TASK_ALWAYS_EAGER=true to run tasks inline)
celery -A src.celery_app worker --queues=celery,materials,preflight --loglevel=info &
```

### 3 · Frontend (Next.js)
```bash
cd apps/web
cp .env.example .env.local                # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                               # http://localhost:3000
```

> **Shortcut:** `./run_app.sh` from `arinar-v2/` brings the whole stack up in one command.

Open **http://localhost:3000**, add your OpenRouter key in **Settings**, and start a session from **New Session**.

### Local defaults
| Service | URL / Port |
|---|---|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 ( `/docs` for OpenAPI ) |
| PostgreSQL | localhost:5433 |
| Redis | localhost:6379 |
| MinIO | localhost:9000 (console :9001) |

For local development you can run without auth by setting `REQUIRE_AUTH=false` in the API `.env`.

---

## Environment variables

Full templates live in [`apps/api/.env.example`](apps/api/.env.example) and [`apps/web/.env.example`](apps/web/.env.example). Highlights:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection (default `postgresql://postgres:postgres@localhost:5433/peerforge_local`) |
| `REDIS_URL` / `CELERY_*` | Redis broker & Celery config; `CELERY_TASK_ALWAYS_EAGER=true` runs tasks inline (free-tier friendly) |
| `STORAGE_BACKEND` + `MINIO_*` / `S3_*` | Object storage for uploaded files |
| `OPENROUTER_API_KEY` | Server-side fallback key (users normally bring their own via header) |
| `KEY_ENCRYPTION_SECRET` | Fernet key encrypting stored account OpenRouter keys |
| `CERT_SIGNING_KEY_PEM` | **Ed25519 key** signing readiness certificates (Pillar 3); auto-generated in dev |
| `REQUIRE_AUTH`, `SUPABASE_*` | Auth mode & Supabase JWT settings |
| `TAVILY_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` | Optional literature/web-search integrations |

---

## Key API endpoints

| Method & path | What it does |
|---|---|
| `POST /debates/setup` | Create a review session |
| `POST /debates/{id}/materials/upload` | Upload a manuscript (async processing) |
| `GET  /debates/{id}/materials/{mid}/file` | Stream the original PDF (for highlighting) |
| `POST /debates/{id}/analyze-research` | Build the structured research profile |
| `POST /debates/{id}/defense-questions/generate` | Generate grounded panel questions |
| `GET  /debates/{id}/provenance` | Glass-Box lineage (claims → verified sources) |
| `POST /debates/{id}/turn/next` | Advance the live panel one turn (with citations) |
| `POST /debates/{id}/committee-twins` | Build reviewer twins from real publications |
| `POST /debates/{id}/answers` | Submit a practice answer for evaluation |
| `POST /debates/{id}/assessment/generate` | 10-dimension academic assessment |
| `GET  /debates/{id}/certificate` | Assemble the readiness certificate |
| `POST /debates/{id}/certificate/issue` | Ed25519-sign & persist the certificate |
| `GET  /verify/{certificate_id}` | **Public** — verify signature, hash & live evidence |
| `GET  /workspaces/{id}/readiness-overview` | Cohort readiness dashboard data |

Interactive OpenAPI docs at **http://localhost:8000/docs**.

---

## Deployment

Designed to run on free/low-cost tiers: **Vercel** (frontend) → **Railway** (FastAPI + Celery) → **Supabase** (Postgres + auth), with object storage on MinIO/S3/R2. See [`DEPLOYMENT.md`](DEPLOYMENT.md) and [`RUNBOOK.md`](RUNBOOK.md).

Production notes:
- Apply the numbered migrations in `apps/api/migrations/` (including `012_issued_certificates.sql`).
- Set `CERT_SIGNING_KEY_PEM` to a managed Ed25519 key so certificate signatures come from a stable, secret-managed key.
- `.env` / `.env.local` are gitignored — never commit real keys.

---

## Roadmap

Phases 0–3 are implemented. Next: institutional pilots (department cohort licensing), academic validation of grounding quality against human reviewers, a pluggable retriever abstraction, and richer research-profile visualizations. See [`docs/product/`](docs/product/).

---

## License

**Proprietary — © 2026 PeerForge. All rights reserved.** This repository is source-available for review; it is not licensed for redistribution or commercial reuse. Replace this section if you choose a different license.

---

<div align="center">
<em>Rehearse the review you'll actually face — and prove every word of it.</em>
</div>
