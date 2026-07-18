-- 016: Stripe subscription linkage (full billing lifecycle)
-- Correlates a workspace with its Stripe customer + subscription so webhook
-- events (cancellation, plan change, payment failure) can find the workspace
-- and downgrade/adjust it. plan_status tracks the subscription's health.

ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT;
-- active | canceling (paid through period end) | canceled | past_due | none
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS plan_status VARCHAR(30);
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS plan_renews_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_workspaces_stripe_sub  ON workspaces (stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_stripe_cust ON workspaces (stripe_customer_id);
