-- Dev seed: create a default tenant + workspace for local development.
-- Safe to run in production — uses fixed UUIDs with ON CONFLICT DO NOTHING.

INSERT INTO tenants (tenant_id, name, slug, created_at, updated_at)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'PeerForge Local Dev',
  'peerforge-dev',
  NOW(), NOW()
) ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO workspaces (workspace_id, tenant_id, name, slug, created_at, updated_at)
VALUES (
  '00000000-0000-0000-0000-000000000101',
  '00000000-0000-0000-0000-000000000001',
  'PeerForge Dev Workspace',
  'peerforge-dev-ws',
  NOW(), NOW()
) ON CONFLICT (workspace_id) DO NOTHING;
