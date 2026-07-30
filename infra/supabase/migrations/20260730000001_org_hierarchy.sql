-- Institutional hierarchy: university -> course -> student
-- ========================================================
-- `tenants` is reused as the organization (university). It already carries
-- name, slug, status and settings, and workspaces already reference it, so a
-- fourth level would only duplicate what exists.
--
--   tenant     = university / institution
--   workspace  = a course, cohort or department space
--   membership = user_workspaces row (enrolment)

-- ── Organization membership ─────────────────────────────────────────────────
-- Membership was only expressible per-workspace, so there was no way to say
-- "this person belongs to the university" independent of any one course.
CREATE TABLE IF NOT EXISTS organization_members (
    org_id      UUID        NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id     UUID        NOT NULL,
    org_role    VARCHAR(50) NOT NULL DEFAULT 'student',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, user_id),
    CONSTRAINT organization_members_role_check
        CHECK (org_role IN ('org_admin', 'professor', 'ta', 'student'))
);

CREATE INDEX IF NOT EXISTS idx_org_members_user ON organization_members(user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_org  ON organization_members(org_id, org_role);

COMMENT ON TABLE organization_members IS
    'Who belongs to a university, and in what capacity, independent of course enrolment.';

-- ── Invitations ─────────────────────────────────────────────────────────────
-- There was no provisioning path at all: users had to be created by hand in
-- Supabase Studio and mapped with raw SQL.
CREATE TABLE IF NOT EXISTS invitations (
    invite_id     UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id        UUID        NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    -- Null for an org-level invite (e.g. inviting a professor); set when
    -- enrolling someone directly into a course.
    workspace_id  UUID        REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    email         TEXT        NOT NULL,
    invited_role  VARCHAR(50) NOT NULL DEFAULT 'student',
    token         TEXT        NOT NULL UNIQUE,
    invited_by    UUID,
    expires_at    TIMESTAMPTZ NOT NULL,
    accepted_at   TIMESTAMPTZ,
    accepted_by   UUID,
    revoked_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT invitations_role_check
        CHECK (invited_role IN ('org_admin', 'professor', 'ta', 'student'))
);

CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token);
CREATE INDEX IF NOT EXISTS idx_invitations_org   ON invitations(org_id, created_at DESC);
-- First login looks a pending invite up by email, so it must be fast and
-- case-insensitive.
CREATE INDEX IF NOT EXISTS idx_invitations_email_pending
    ON invitations(LOWER(email))
    WHERE accepted_at IS NULL AND revoked_at IS NULL;

-- ── Seats ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organization_seats (
    org_id            UUID        PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    seats_purchased   INTEGER     NOT NULL DEFAULT 0,
    plan              VARCHAR(50) NOT NULL DEFAULT 'trial',
    period_end        TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT organization_seats_purchased_check CHECK (seats_purchased >= 0)
);

COMMENT ON COLUMN organization_seats.seats_purchased IS
    'Seats consumed are counted live from organization_members, not stored, so the two cannot drift.';

-- ── Session ownership ───────────────────────────────────────────────────────
-- A debate belonged to a workspace but had no author, so a shared course space
-- could not distinguish one student''s work from another''s.
ALTER TABLE debates ADD COLUMN IF NOT EXISTS owner_user_id UUID;
CREATE INDEX IF NOT EXISTS idx_debates_owner ON debates(workspace_id, owner_user_id);

COMMENT ON COLUMN debates.owner_user_id IS
    'The student or researcher whose session this is. Null for sessions created before ownership was tracked.';

-- ── Course-level roles ──────────────────────────────────────────────────────
-- Extend the existing enrolment roles rather than replacing them; owner/admin/
-- member/viewer rows already exist in the wild.
ALTER TABLE user_workspaces DROP CONSTRAINT IF EXISTS user_workspaces_role_check;
ALTER TABLE user_workspaces ADD CONSTRAINT user_workspaces_role_check
    CHECK (role IN ('owner', 'admin', 'member', 'viewer', 'professor', 'ta', 'student'));
