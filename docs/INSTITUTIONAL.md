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

## Billing (scaffold — no payment processor)

The operator sets `PLAN` in the API environment; `services/plans.py` gates
features and `GET /billing/plan` exposes the active plan to clients.

| Plan | Departments / invites / SSO | Advisory limits |
|---|---|---|
| `community` | — | 5 active sessions, 10 materials/session |
| `professional` | — | 25 active sessions, 30 materials/session |
| `institution` (default) | ✓ | none |

Gated endpoints return **402** with the reason when the plan lacks a feature.
Unknown `PLAN` values fail closed to `community`. Limits are advisory
(surfaced, not yet enforced). When a payment processor is added, checkout only
has to set the same per-tenant value.

## Production checklist

- Apply migrations through `014_departments.sql`
- `REQUIRE_AUTH=true` + Supabase auth vars
- `CERT_SIGNING_KEY_PEM` — managed Ed25519 key for certificate signing
- `KEY_ENCRYPTION_SECRET` — encrypts account-stored OpenRouter keys
- `PLAN=institution` (or the tier you sell)
