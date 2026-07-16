# Contributing to PeerForge

Thanks for working on PeerForge. This guide covers the local workflow and the
conventions the codebase follows.

## Prerequisites

- Docker Desktop, Node.js 20+, Python 3.11
- An OpenRouter API key (for any flow that calls an LLM or generates embeddings)

## Local setup

See the [README quick start](README.md#quick-start). In short:

```bash
docker compose -f infra/docker/docker-compose.yml up -d db redis minio
# API
cd apps/api && cp .env.example .env && uvicorn src.main:app --reload --port 8000
celery -A src.celery_app worker --queues=celery,materials,preflight
# Web
cd apps/web && cp .env.example .env.local && npm install && npm run dev
```

`./run_app.sh` from `arinar-v2/` does all of this in one command.

## Before you open a PR

Run the checks the CI runs:

```bash
make verify          # lint + typecheck + test + api-test
# or individually:
cd apps/web && npx tsc --noEmit          # frontend typecheck (must be 0 errors)
cd apps/api && pytest                     # backend tests
```

- **Frontend must typecheck cleanly** (`tsc --noEmit` → 0 errors).
- **API must import cleanly** and boot (`uvicorn src.main:app`).
- If your change is visible in the app, verify it in the browser before pushing.

## Conventions

- **Provenance is sacred.** Anything that grounds an AI claim in a source must be
  verifiable — hard-link to a chunk, re-verify the SHA-256, and flag gaps
  honestly. Never fabricate a citation or a page number.
- **No marks/grades in the UI.** Numeric scores exist internally (for logic and
  the certificate) but the researcher-facing UI shows qualitative feedback only.
- **OpenRouter is the only LLM provider.** All model calls go through it with a
  bring-your-own-key model; the browser key is never stored server-side.
- **Migrations are numbered SQL** in `apps/api/migrations/`. Add the next number;
  never edit an applied migration.
- Match the surrounding code's style, naming, and comment density.

## Security

- Never commit secrets. `.env` / `.env.local` are gitignored — keep them that way.
- The public mirror (`RW2523/PeerReview`) contains the same source; scan diffs for
  live keys (`sk-or-…`, `sb_secret_…`, PEM private keys) before pushing.

## Commit & branch

- Branch off the working branch; don't commit directly to the default branch.
- Write descriptive commit messages that explain the *why*.
