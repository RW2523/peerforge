-- 015: Per-workspace billing plan (paywall)
-- A workspace's plan decides which features it can use and how many review
-- sessions / materials it may create. NULL means "inherit the deployment
-- default" (config PLAN env). Resolution + gates live in services/plans.py.

ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS plan VARCHAR(50);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS plan_updated_at TIMESTAMPTZ;
-- Where the current plan came from: 'default' (env), 'manual' (owner switch),
-- or 'stripe' (checkout webhook). Audit only — never trusted for gating.
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS plan_source VARCHAR(20);

ALTER TABLE workspaces DROP CONSTRAINT IF EXISTS workspaces_plan_check;
ALTER TABLE workspaces ADD CONSTRAINT workspaces_plan_check
    CHECK (plan IS NULL OR plan IN ('community', 'professional', 'institution'));
