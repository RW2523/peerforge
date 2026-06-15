-- Migration: Add user_workspaces mapping table for Supabase Auth
-- Date: 2026-02-06
-- Ticket: TICKET-08A

-- Maps Supabase auth users to workspaces
-- Used by API to resolve workspace_id from user_id when JWT doesn't contain workspace claim
CREATE TABLE IF NOT EXISTS user_workspaces (
    user_id UUID NOT NULL,  -- Supabase auth.users.id
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (user_id, workspace_id),
    CONSTRAINT user_workspaces_role_check CHECK (role IN ('owner', 'admin', 'member', 'viewer'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_workspaces_user_id ON user_workspaces(user_id);
CREATE INDEX IF NOT EXISTS idx_user_workspaces_workspace_id ON user_workspaces(workspace_id);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_user_workspaces_updated_at ON user_workspaces;
CREATE TRIGGER update_user_workspaces_updated_at
    BEFORE UPDATE ON user_workspaces
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS policies
ALTER TABLE user_workspaces ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Enable all for service_role" ON user_workspaces;
CREATE POLICY "Enable all for service_role"
    ON user_workspaces
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Comments
COMMENT ON TABLE user_workspaces IS 'Maps Supabase auth users to workspaces';
COMMENT ON COLUMN user_workspaces.user_id IS 'Supabase auth.users.id';
COMMENT ON COLUMN user_workspaces.workspace_id IS 'Workspace the user has access to';
COMMENT ON COLUMN user_workspaces.role IS 'User role in workspace (owner/admin/member/viewer)';
