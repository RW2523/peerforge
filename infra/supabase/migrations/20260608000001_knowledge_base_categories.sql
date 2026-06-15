-- Migration: Knowledge Base Categories & Action-Item Committee
-- Date: 2026-06-08
-- Description: Adds material categories (main research / research / transcript /
--   supplementary), a pinned "main research file" flag, audio material support,
--   and a transcript_action_items table that links extracted action items to the
--   short autonomous committee debates that decide them.

-- ============================================================================
-- CATEGORIZE meeting_materials + SUPPORT AUDIO TRANSCRIPTS
-- ============================================================================

ALTER TABLE meeting_materials
    ADD COLUMN IF NOT EXISTS material_category VARCHAR(50) DEFAULT 'supplementary',
    ADD COLUMN IF NOT EXISTS is_primary BOOLEAN DEFAULT false;

-- Allow 'audio' kind (audio transcripts) alongside all previously-permitted kinds
-- (includes 'web' and 'literature' added by later migrations)
ALTER TABLE meeting_materials DROP CONSTRAINT IF EXISTS meeting_materials_kind_check;
ALTER TABLE meeting_materials ADD CONSTRAINT meeting_materials_kind_check
    CHECK (kind IN ('text', 'link', 'file_placeholder', 'file', 'web', 'literature', 'audio'));

-- Constrain the category to the known set
ALTER TABLE meeting_materials DROP CONSTRAINT IF EXISTS meeting_materials_category_check;
ALTER TABLE meeting_materials ADD CONSTRAINT meeting_materials_category_check
    CHECK (material_category IN ('main_research', 'research', 'transcript', 'supplementary'));

-- At most one pinned primary (main research) file per debate
CREATE UNIQUE INDEX IF NOT EXISTS idx_meeting_materials_one_primary
    ON meeting_materials(debate_id)
    WHERE is_primary = true;

CREATE INDEX IF NOT EXISTS idx_meeting_materials_category
    ON meeting_materials(debate_id, material_category);

COMMENT ON COLUMN meeting_materials.material_category IS 'Role in the knowledge base: main_research, research, transcript, supplementary';
COMMENT ON COLUMN meeting_materials.is_primary IS 'True for the single pinned main research file (always in the knowledge base)';

-- ============================================================================
-- TRANSCRIPT ACTION ITEMS + DECISION DEBATES
-- ============================================================================

CREATE TABLE IF NOT EXISTS transcript_action_items (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    material_id UUID REFERENCES meeting_materials(material_id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    owner TEXT,
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(30) NOT NULL DEFAULT 'extracted',
    decision_debate_id UUID REFERENCES debates(debate_id) ON DELETE SET NULL,
    decision TEXT,
    decision_rationale TEXT,
    seq_order INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT transcript_action_items_status_check
        CHECK (status IN ('extracted', 'debating', 'decided')),
    CONSTRAINT transcript_action_items_priority_check
        CHECK (priority IN ('low', 'medium', 'high'))
);

CREATE INDEX IF NOT EXISTS idx_action_items_debate ON transcript_action_items(debate_id);
CREATE INDEX IF NOT EXISTS idx_action_items_material ON transcript_action_items(material_id);

COMMENT ON TABLE transcript_action_items IS 'Action items extracted from meeting transcripts and the committee debates that decide them';
COMMENT ON COLUMN transcript_action_items.status IS 'extracted (just parsed), debating (child debate running), decided (decision stored)';
COMMENT ON COLUMN transcript_action_items.decision_debate_id IS 'Child debate spawned to decide this action item';

-- updated_at trigger (reuses update_updated_at_column() from initial schema)
DROP TRIGGER IF EXISTS update_action_items_updated_at ON transcript_action_items;
CREATE TRIGGER update_action_items_updated_at BEFORE UPDATE ON transcript_action_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- RLS
-- ============================================================================

ALTER TABLE transcript_action_items ENABLE ROW LEVEL SECURITY;

-- Create the service_role policy only when that role exists (Supabase);
-- local/non-Supabase databases skip it gracefully.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        DROP POLICY IF EXISTS "Enable all for service_role" ON transcript_action_items;
        CREATE POLICY "Enable all for service_role"
            ON transcript_action_items FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;
