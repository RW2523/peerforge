# PeerForge — Production Deployment

Two supported configurations — same code, env vars decide:

| | **Free ($0/mo)** | **Paid (~$5/mo)** |
|---|---|---|
| Frontend | Vercel Hobby | Vercel Hobby |
| DB + Auth | Supabase free | Supabase free |
| API | **Render free** web service | Railway Hobby |
| Background tasks | `CELERY_TASK_ALWAYS_EAGER=true` (inline, no worker/Redis) | Celery worker + Redis services |
| File storage | **Supabase Storage** (`STORAGE_BACKEND=s3`) | MinIO service (`STORAGE_BACKEND=minio`) |
| Trade-offs | ~50s cold start after 15 min idle; Auto Mode only advances while awake | none |

## 0 · Free path (Render) — quick version

1. render.com → New → Web Service → connect repo, root `apps/api`,
   runtime Docker. Instance type: **Free**.
2. Env vars: everything from §2 below **plus**
   `CELERY_TASK_ALWAYS_EAGER=true`, `STORAGE_BACKEND=s3`, and the
   `S3_*` values from your Supabase project
   (Storage → create bucket `peerforge-materials` → Settings → S3 access keys):
   ```bash
   S3_ENDPOINT_URL=https://<project-ref>.storage.supabase.co/storage/v1/s3
   S3_REGION=<project region>
   S3_ACCESS_KEY=...
   S3_SECRET_KEY=...
   S3_BUCKET=peerforge-materials
   ```
   Omit `REDIS_URL` entirely.
3. Continue with §1 (Supabase) and §3 (Vercel) as written.

To upgrade later: create the Railway services in §2, flip
`CELERY_TASK_ALWAYS_EAGER` off and `STORAGE_BACKEND=minio`. No code changes.

---

Paid-path architecture: **Vercel** (Next.js frontend) · **Supabase** (Postgres + Auth) ·
**Railway** (FastAPI API + Celery worker + Redis + MinIO).

```
Browser ──► Vercel (apps/web)
              │  NEXT_PUBLIC_API_URL
              ▼
          Railway: API (apps/api, Dockerfile)
              │            │
              │            ├─► Railway: Redis  (broker)
              │            ├─► Railway: Worker (same image, celery command)
              │            └─► Railway: MinIO  (file storage)
              ▼
          Supabase: Postgres (schema) + Auth (JWT)
```

---

## 1 · Supabase (database + auth)

1. Create the project (new org). Apply the schema:
   the full DDL replica of local dev lives at `/tmp/e2e/peerforge_schema.sql`
   (regenerate any time: `pg_dump --schema-only --no-owner --no-privileges --schema=public <local-dsn>`),
   or apply `apps/api/migrations/*.sql` in order on a fresh database.
2. Auth → enable Email provider (Google optional later).
3. Auth → URL configuration: site URL = your Vercel domain,
   redirect URLs += `https://<vercel-domain>/**`.
4. Workspace provisioning trigger (run once in SQL editor) — every new
   sign-up gets an isolated workspace:

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE new_workspace_id uuid;
BEGIN
  INSERT INTO workspaces (workspace_id, tenant_id, name, created_at)
  VALUES (gen_random_uuid(), gen_random_uuid(),
          COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)) || '''s workspace',
          NOW())
  RETURNING workspace_id INTO new_workspace_id;

  INSERT INTO user_workspaces (user_id, workspace_id, role, created_at)
  VALUES (NEW.id::text, new_workspace_id, 'owner', NOW());
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

(Adjust column names if `workspaces` / `user_workspaces` differ — check the
schema dump.)

---

## 2 · Railway (backend)

Create a Railway project with four services:

| Service | Source | Start command |
|---|---|---|
| **api** | repo, root `apps/api` (Dockerfile) | default (`uvicorn src.main:app --host 0.0.0.0 --port $PORT`) |
| **worker** | same repo/root/image | `celery -A src.celery_app worker --loglevel=info -Q celery,materials,preflight --concurrency=2` |
| **redis** | Railway Redis template | — |
| **minio** | Railway MinIO template | — |

**Budget option (one service):** skip worker + redis, set
`CELERY_TASK_ALWAYS_EAGER=true` on the api service — tasks run inline.

### Environment variables (api + worker)

```bash
DATABASE_URL=postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres
REDIS_URL=${{Redis.REDIS_URL}}                 # omit in eager mode
REQUIRE_AUTH=true
SUPABASE_JWT_SECRET=<Supabase → Settings → API → JWT secret>
KEY_ENCRYPTION_SECRET=<openssl rand -hex 32>   # encrypts stored OpenRouter keys
OPENROUTER_API_KEY=                            # optional server fallback key
MINIO_ENDPOINT=${{MinIO host:port}}
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET=peerforge-materials
MINIO_SECURE=false                             # true if MinIO behind TLS
CORS_ORIGINS=https://<your-vercel-domain>
```

(Check `apps/api/src/config.py` for the authoritative variable list; CORS is
configured in `src/main.py`.)

---

## 3 · Vercel (frontend)

Project root: `apps/web`. Environment variables:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon / publishable key>
NEXT_PUBLIC_API_URL=https://<railway-api-domain>
```

---

## 4 · Auth & key model (how it fits together)

- Supabase issues JWTs at sign-in; the frontend sends them as
  `Authorization: Bearer …` (REST) and `?token=` (WebSocket). The backend
  verifies them when `REQUIRE_AUTH=true` and scopes everything to the user's
  workspace.
- At sign-up the user lands on `/onboarding` — a **skippable** step that
  stores their OpenRouter key on the account (encrypted with
  `KEY_ENCRYPTION_SECRET`, masked everywhere after saving; manage it in
  Settings → Account API Key).
- Key resolution per request: `X-OpenRouter-Key` header (browser-local key)
  → account-stored key → `OPENROUTER_API_KEY` server fallback.

## 5 · Post-deploy smoke test

1. Sign up → onboarding → connect key (or skip).
2. New Review Session → upload a document → materials reach "Ready".
3. Practice Q&A: analyse → panel → questions → answer → feedback report.
4. Review Room: ⚡ Auto Mode runs turns and concludes with a summary.
5. Session Report tab: journey card + Academic Assessment Matrix generate.
