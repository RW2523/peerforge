# Going live

The application runs today with authentication disabled. Everything in the
institution tier — organizations, courses, invitations, roles, the cohort view
— is built and tested, but inert until auth is on, because without it every
visitor resolves to the same identity in the same workspace.

`GET /readiness` reports what is still unconfigured at any time.

## 1. Turn authentication on

Both of these, together. The API refuses to boot with auth enabled and a
placeholder secret, so a half-done switch fails loudly rather than looking
secure while accepting forged tokens.

```
REQUIRE_AUTH=true
SUPABASE_JWT_SECRET=<the JWT secret from your Supabase project settings>
```

The frontend needs the matching project:

```
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable key>
```

Remove `NEXT_PUBLIC_AUTH_MODE=development` and `NEXT_PUBLIC_TEST_TOKEN` from
any deployed environment. A production build ignores the bypass regardless,
but leaving them set is misleading.

## 2. Lock the browser origins

```
CORS_ALLOW_ORIGINS=https://your-frontend-domain
```

A wildcard disables credentialed requests, because the CORS specification
forbids pairing one with `Access-Control-Allow-Credentials`.

## 3. Let people save an API key

```
KEY_ENCRYPTION_SECRET=<a Fernet key>
```

Generate one with:

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Without it the account key vault refuses to store anything rather than
writing keys unencrypted, so users must paste a key each session.

## 4. Send invitations

Either:

```
SMTP_HOST=smtp.your-provider.com
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=no-reply@your-domain
```

or set `SUPABASE_SERVICE_ROLE_KEY` to use Supabase's admin invite, which also
creates the user.

With neither, invitations still work — the API returns the link and the
organization page shows it to copy.

Set `APP_BASE_URL` to the public frontend URL so invitation links point
somewhere real.

## 5. Give the worker a key

```
OPENROUTER_API_KEY=<key>
```

The worker needs this to embed uploaded material. Without it, retrieval falls
back to keyword matching — functional, but weaker than semantic search.

Note this is a *server-side* key. Do not set it while the deployment is public
and unauthenticated: any visitor's session would spend it.

## 6. Bootstrap the first organization

There is no seeded institution. The first person to sign in creates one:

```
POST /organizations   {"name": "Your University"}
```

They become its `org_admin` and can invite professors from `/organization`.

## Verifying

```
curl https://<api>/readiness
```

`ready_for_public_launch` turns true once authentication and the JWT secret
both pass. The remaining checks are degradations, not blockers, and each one
names the feature it costs you.
