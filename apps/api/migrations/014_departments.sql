-- 014: Departments + workspace invites (institutional layer, B2)
-- A department groups a workspace's review sessions (e.g. "Computer Science",
-- "Biology") so an advisor console can filter cohorts. Invites let an advisor
-- bring students/advisors into a shared workspace with a role — the enforcement
-- side lives in user_workspaces.role via require_role().

-- Widen the legacy role check (owner/admin/member/viewer) to include the
-- academic roles the RBAC layer enforces. Existing rows stay valid.
ALTER TABLE user_workspaces DROP CONSTRAINT IF EXISTS user_workspaces_role_check;
ALTER TABLE user_workspaces ADD CONSTRAINT user_workspaces_role_check
    CHECK (role IN ('owner', 'admin', 'advisor', 'member', 'student', 'viewer'));

CREATE TABLE IF NOT EXISTS departments (
    department_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  UUID NOT NULL,
    name          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, name)
);
CREATE INDEX IF NOT EXISTS idx_departments_workspace ON departments (workspace_id);

ALTER TABLE debates ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES departments (department_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_debates_department ON debates (department_id);

CREATE TABLE IF NOT EXISTS workspace_invites (
    invite_token  TEXT PRIMARY KEY,
    workspace_id  UUID NOT NULL,
    role          VARCHAR(50) NOT NULL DEFAULT 'student',
    department_id UUID REFERENCES departments (department_id) ON DELETE SET NULL,
    created_by    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL,
    used_by       UUID,
    used_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_invites_workspace ON workspace_invites (workspace_id);
