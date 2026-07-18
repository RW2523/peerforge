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
Stripe Checkout; the webhook (`checkout.session.completed`) flips the
workspace's plan. The direct switch is then limited to downgrades and the free
tier, so nobody unlocks paid tiers without paying. The `stripe` library is
imported lazily — it is not a hard dependency for deployments that don't use it.

**UI:** `/billing` (plan cards + usage meters + upgrade/downgrade), a plan pill
in the top nav, a locked-feature prompt on the advisor console, and `/join` for
redeeming invite tokens.

## Production checklist

- Apply migrations through `014_departments.sql`
- `REQUIRE_AUTH=true` + Supabase auth vars
- `CERT_SIGNING_KEY_PEM` — managed Ed25519 key for certificate signing
- `KEY_ENCRYPTION_SECRET` — encrypts account-stored OpenRouter keys
- `PLAN=institution` (or the tier you sell)
