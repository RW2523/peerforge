# Supabase Cloud and MCP Setup

## Scope
This runbook configures:
- API auth/runtime settings for Supabase Cloud.
- Cursor MCP server entry for Supabase.

## API Environment
Create `apps/api/.env.local` with:

```dotenv
SUPABASE_URL=https://pdreemhonhlpuwnxswqo.supabase.co
SUPABASE_PROJECT_REF=pdreemhonhlpuwnxswqo
SUPABASE_ANON_KEY=<set locally>
SUPABASE_SERVICE_ROLE_KEY=<set locally>
SUPABASE_JWT_SECRET=<set locally from Supabase Auth settings>
REQUIRE_AUTH=true
```

Notes:
- Keep secrets only in local `.env.local` (never commit).
- `SUPABASE_JWT_SECRET` is required for JWT verification in current API auth implementation.
- `DATABASE_URL` can remain local during active development, or you can switch to Supabase Cloud using one of these templates:

```dotenv
# Direct DB host (common)
DATABASE_URL=postgresql://postgres:<DB_PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres?sslmode=require

# Pooler host (recommended for app runtime if available in project settings)
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres?sslmode=require
```

## Cursor MCP
Project-local MCP config file:
- `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "supabase": {
      "url": "https://mcp.supabase.com/mcp?project_ref=pdreemhonhlpuwnxswqo"
    }
  }
}
```

If Cursor does not auto-load project MCP config, paste the same JSON into Cursor MCP settings manually.

## Security
- Rotate any key that was shared in chat/history.
- Do not store secrets in tracked files.
