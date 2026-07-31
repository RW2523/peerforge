# Architecture

What the system is, how the pieces fit, and where the sharp edges are. Written
against the code as it stands — if something here disagrees with the code, the
code is right and this file is a bug.

## Shape

```
apps/web     Next.js 15 App Router, React 18, CSS modules
apps/api     FastAPI, synchronous psycopg2 over a pooled connection
apps/workers Celery tasks (material processing, preflight)
infra        Postgres, Redis, MinIO via docker compose
```

The API is synchronous by design: psycopg2 rather than an async driver. That
choice has consequences documented under *Sharp edges*.

## The hierarchy

```
tenant (university)  ->  workspace (course)  ->  member
```

`tenants` is the organization table. It already carried name, slug, status and
settings, and workspaces already referenced it, so adding a fourth level would
have duplicated what existed.

Two membership tables, deliberately separate:

- `organization_members` — who belongs to the university, and in what capacity.
  Independent of any one course.
- `user_workspaces` — enrolment in a specific course.

A professor belongs to the organization once, and to each course they teach.
They can reach every workspace in their organization without being enrolled in
each; that set is computed once per request in `get_accessible_workspace_ids`
so authorization stays a set lookup rather than a query per check.

**Roles.** `org_admin`, `professor`, `ta`, `student`. A professor may staff
their courses but cannot mint administrators or other professors; the last
admin cannot be demoted or removed.

## Authentication

Supabase JWTs, verified with `SUPABASE_JWT_SECRET`.

Two rules matter more than the rest:

1. **Membership in the database is the authority.** A `workspace_id` claim in
   the token *selects* among the caller's workspaces; it never grants access.
   The same is true of the `X-Workspace-Id` header. A crafted or stale claim
   cannot reach another tenant.

2. **The application refuses to boot** with `REQUIRE_AUTH=true` and a
   placeholder secret. A half-finished switch fails loudly rather than looking
   secure while accepting forged tokens.

With `REQUIRE_AUTH=false` every visitor resolves to one dev identity in one
workspace. That is a local-development mode, not a deployment mode.

## A review session

```
create session -> upload material -> conversation -> apply -> turns -> assessment
```

**Setup is a conversation.** `/setup/chat` describes the work in prose; each
turn retrieves passages from the uploaded material and returns a *complete*
proposal — title, problem statement, panel, rounds — never a patch. The panel
on screen is always exactly what would be created.

**Reviewer lanes.** Six: advisor, methodology professor, domain expert,
skeptical reviewer, friendly professor, external examiner. The lane is resolved
from `role_description` on the participant. This matters: reading a key that is
never written collapses every reviewer onto one lane and the panel says the
same thing six times.

**A turn** runs reasoning, then response generation, both with the participant's
configured model. Turn advancement takes a `FOR NO KEY UPDATE` row lock — see
*Sharp edges*.

**Material is untrusted.** The document under review is written by the person
being reviewed, so it is fenced in the user role with delimiters stripped from
the text, and the system prompt states that content between the markers is
evidence, never instruction.

## Measuring output

`apps/api/src/services/transcript_quality.py` scores a recorded transcript with
no model calls: agreement-opener rate, self-similarity, role differentiation,
placeholder leakage, grounding. Thresholds are calibrated against real
transcripts this project produced before and after the lane fix.

It does not judge whether a review is *good* — that needs a reader. It detects
the specific ways this panel is known to fail. Exposed at
`GET /debates/{id}/quality`, and enforced by the test suite.

## Sharp edges

Things that will bite if you do not know them.

**`FOR UPDATE` on `debates` deadlocks against itself.** `events.debate_id` is a
foreign key, so every `INSERT INTO events` takes `FOR KEY SHARE` on the parent
row — and the thinking service writes events on a separate connection during
the turn. Use `FOR NO KEY UPDATE`, which serialises writers without blocking
foreign-key child inserts.

**The connection pool has an overflow path on purpose.** One turn nests 12–15
connections. A pool that blocks when empty would deadlock two concurrent turns
against each other, so exhaustion falls back to a direct connection instead of
waiting.

**Both migration directories must be applied.** `infra/supabase/migrations`
*and* `apps/api/migrations`, infra first. Applying only the first leaves 14
tables missing and several features returning 500. `scripts/db_apply_migrations.sh`
handles both; so does CI.

**The Celery worker needs `-Q celery,materials,preflight`.** Tasks route to
named queues. A worker started without those flags listens only on `celery`
and uploads queue forever. `celery_app.conf.worker_queues` is not a real
setting and does nothing.

**`npm audit fix --omit=dev` prunes devDependencies**, removing TypeScript. A
plain `npm install` restores it.

## Known limits

Stated because they are true, not because they are urgent.

- **Multi-instance needs Redis.** Broadcasts fan out over a Redis channel and
  autonomous debates are owned through a renewable lease, so two API processes
  no longer show divergent transcripts or double-drive a session. Without Redis
  both degrade to local-only, which is correct for one instance and is what
  `GET /readiness` reports.
- **Seats count every role alike**, so a professor consumes a student seat.
- **Async side effects are skipped on the HTTP turn path.** Document writing
  and autonomous behaviours require an event loop that only the WebSocket
  handler sets. The room uses WebSocket, so users are unaffected.

## Where to look

| Concern | File |
|---|---|
| Authentication, membership, roles | `apps/api/src/auth.py` |
| Organizations, invitations, seats, cohort | `apps/api/src/routes/organizations.py` |
| A review turn | `apps/api/src/turn_orchestrator.py` |
| Conversational setup | `apps/api/src/services/conversational_setup.py` |
| Output quality | `apps/api/src/services/transcript_quality.py` |
| What is unconfigured | `GET /readiness` |
| Turning it on | `GOING-LIVE.md` |
| How past bugs were fixed | `docs/history/` (historical; several superseded) |
