-- Member identity on the roster
-- =============================
-- organization_members stored only a Supabase user UUID, so a roster rendered
-- as a list of UUIDs. The API has no view onto auth.users (the Supabase
-- project may be shared with another app), so identity is denormalised here
-- at the moment someone joins — which is exactly when we know their address,
-- because they joined by redeeming an invitation sent to it.

ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE organization_members ADD COLUMN IF NOT EXISTS display_name TEXT;

CREATE INDEX IF NOT EXISTS idx_org_members_email
    ON organization_members(org_id, LOWER(email));

COMMENT ON COLUMN organization_members.email IS
    'Captured when the invitation was redeemed. Null for members added before identity was tracked, or seeded directly.';

-- Backfill from the invitation each member accepted.
UPDATE organization_members om
SET email = i.email
FROM invitations i
WHERE om.email IS NULL
  AND i.accepted_by = om.user_id
  AND i.org_id = om.org_id;
