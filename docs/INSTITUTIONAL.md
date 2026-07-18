# Institutional layer — roles, departments, SSO, billing

How a university department (rather than a single researcher) runs PeerForge.
Everything here is already enforced in code; this page tells an operator how to
activate it.

## Roles (RBAC)

Membership lives in `user_workspaces (user_id, workspace_id, role)`:

| Role | Meaning | Gets |
|---|---|---|
| `owner` | Workspace creator | Everything — passes every role gate |
| `advisor` | Supervisor / coordinator | Advisor console, cohort views, departments, invites, labels |
| `student` | Researcher being reviewed | Their own sessions; no cohort views |

Enforcement is `require_role(...)` in `apps/api/src/auth.py`. Endpoints gated
today: `students-overview`, `readiness-overview`, `student-label`, all
`/departments` and `/invites` routes. Users with no membership row default to
`student` (least privilege).

Dev mode (`REQUIRE_AUTH=false`) maps the synthetic test user to `owner` so
local development keeps full access while the enforcement path stays live.

## Departments

Migration `014_departments.sql`. A department groups review sessions inside a
workspace; the Advisor Console (`/advisor`) has a filter dropdown, an inline
"New department" control, and a per-session department selector.

API: `GET/POST /workspaces/{id}/departments`,
`POST /debates/{id}/department`, and `?department_id=` on `students-overview`.

## Invites

An advisor mints a single-use token carrying a role (and optionally a
department): **Advisor Console → Create invite**, or
`POST /workspaces/{id}/invites {role, department_id?, expires_days}`.

The invitee (signed in via Supabase) redeems it with
`POST /invites/{token}/accept` — this writes their `user_workspaces` row with
the invited role and marks the token spent. Expired or reused tokens are
rejected (410). Redemption requires a real authenticated user, so it is
inert in `REQUIRE_AUTH=false` dev mode by design.

## SSO (via Supabase Auth)

The API already validates Supabase JWTs (`SUPABASE_JWT_SECRET`), so SSO is
Supabase configuration, not code:

1. Supabase Dashboard → Authentication → Providers → enable **Google** and/or
   **Azure (Entra ID)** with your institution's OAuth client. SAML 2.0 is
   available on Supabase Pro for Shibboleth/ADFS campuses.
2. Restrict sign-ups to your domain (Authentication → Settings → allowed
   email domains), e.g. `@university.edu`.
3. Set `REQUIRE_AUTH=true` on the API and fill `SUPABASE_URL`,
   `SUPABASE_JWT_SECRET`, `SUPABASE_ANON_KEY`.
4. First sign-in auto-provisions a personal workspace (`auth.py`); joining the
   department workspace happens via an invite token from an advisor.

## Billing & the paywall

Each **workspace** holds a plan (`workspaces.plan`, migration 015). `NULL`
inherits the deployment default (`PLAN` env). `services/plans.py` resolves the
plan per workspace and enforces both feature gates and usage quotas.

| Plan | Departments / invites / SSO | Sessions | Materials/session |
|---|---|---|---|
| `community` | — | 5 | 10 |
| `professional` | — | 25 | 30 |
| `institution` | ✓ | unlimited | unlimited |

**Enforcement (real, not advisory):**
- Feature gates → **402** (departments, invites; SSO is deployment-level).
- Session quota → **402** on `POST /debates` past `max_sessions`.
- Material quota → **402** on material upload past `max_materials_per_session`.
- Unknown plan values and DB errors **fail closed to `community`**.

**Endpoints:**
- `GET /me` — the caller's workspace, role, and resolved plan (the frontend
  uses this instead of hardcoding a workspace id).
- `GET /workspaces/{id}/billing` — current plan, all tiers, live usage.
- `POST /workspaces/{id}/billing/plan` — **owner-only** plan switch.
- `POST /workspaces/{id}/billing/checkout` + `POST /billing/webhook` — Stripe.

**Payment (optional).** Without Stripe, the owner plan-switch applies
immediately (self-serve / trials / manual provisioning). With
`STRIPE_SECRET_KEY` + `STRIPE_PRICE_IDS` set, a *paid upgrade* must go through
Stripe Checkout; the direct switch is then limited to downgrades and the free
tier, so nobody unlocks paid tiers without paying. The `stripe` library is
imported lazily — not a hard dependency for deployments that don't use it.

**Subscription lifecycle.** The webhook (`POST /billing/webhook`) is the source
of truth and handles the full lifecycle, keyed on the Stripe customer +
subscription IDs stored on the workspace (migration 016):

| Event | Effect |
|---|---|
| `checkout.session.completed` | Activate the purchased plan; store customer + subscription IDs; `plan_status = active`. |
| `customer.subscription.updated` | Plan change (live price → plan), `cancel_at_period_end` → `canceling` (paid through period end), `past_due` on failed payment. |
| `customer.subscription.deleted` | Downgrade to `community`; clear the subscription link; `plan_status = canceled`. |

Hardening (all covered by tests):
- **Signature required in production** — an unsigned webhook is refused unless
  `REQUIRE_AUTH=false` (local dev); a missing `STRIPE_WEBHOOK_SECRET` returns 500.
- **No stale-event revival** — Stripe does not guarantee event order and retries
  for days, so an `updated` event is ignored when the workspace is already
  `canceled` with no linked subscription, or when its `id` doesn't match the
  workspace's linked subscription. A genuine re-subscribe only comes via
  `checkout.session.completed`.
- **Entitlement allowlist** — only `active`/`trialing` grant the plan;
  `incomplete`/`paused`/etc. never do. Unmapped prices are logged, not guessed.

**Self-service.** `POST /workspaces/{id}/billing/portal` (owner-only) opens the
Stripe billing portal so a customer can update their card, change plan, or
cancel — cancellation there fires the `subscription.*` webhooks above. The
`/billing` page shows subscription status (Canceling / Past due), the renewal
date, and a **Manage subscription** button. Set `PUBLIC_BASE_URL` so Stripe
return URLs point at your deployed site rather than localhost.

**Nightly reconciliation (belt-and-suspenders).** Stripe only retries a webhook
for ~3 days, so a longer endpoint outage could leave a workspace on the wrong
tier. A nightly job (`services/billing_sync.reconcile_all`) fetches the LIVE
subscription for every linked workspace and repairs any drift — a missed
cancellation downgrades, a missed plan change corrects, a subscription Stripe no
longer knows about is treated as canceled. It shares the exact webhook mapping
(so the two paths can't diverge), is idempotent, and only writes when the
workspace's state actually differs. A transient fetch error is counted and
skipped, never a wrongful downgrade. No-op when Stripe is unconfigured.

It has a **circuit breaker**: a misconfigured Stripe key (a test key against
live objects, or the wrong account) makes *every* subscription look missing. If
too many report missing in one run (≥10 and >50% of those checked), the sweep
aborts without downgrading anyone and logs a CRITICAL — so a bad key can't
mass-cancel your paying customers. Fix the key and the next run reconciles
normally.

Run it one of two ways:
- **Celery Beat** (already scheduled for 03:17 UTC in `celery_app.beat_schedule`):
  `celery -A src.celery_app beat --loglevel=info` alongside the worker.
- **Cron / platform scheduler** (deployments without Beat, e.g. eager mode):
  `python -m src.jobs.reconcile_billing` — prints a JSON summary
  (`{checked, corrected, errors}`) and exits non-zero if any workspace errored,
  so the scheduler can alert.

Production payment env: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
`STRIPE_PRICE_IDS` (JSON `{"professional":"price_…","institution":"price_…"}`),
`PUBLIC_BASE_URL`, and `pip install stripe` (pinned in requirements).

**UI:** `/billing` (plan cards + usage meters + upgrade/downgrade), a plan pill
in the top nav, a locked-feature prompt on the advisor console, and `/join` for
redeeming invite tokens.

## Production checklist

- Apply migrations through `014_departments.sql`
- `REQUIRE_AUTH=true` + Supabase auth vars
- `CERT_SIGNING_KEY_PEM` — managed Ed25519 key for certificate signing
- `KEY_ENCRYPTION_SECRET` — encrypts account-stored OpenRouter keys
- `PLAN=institution` (or the tier you sell)
