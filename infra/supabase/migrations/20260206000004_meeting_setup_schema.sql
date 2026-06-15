-- Migration: Add meeting setup schema (materials + agent model_id)
-- Date: 2026-02-06
-- Ticket: TICKET-08B.1

-- Add model_id column to agents table
ALTER TABLE agents ADD COLUMN IF NOT EXISTS model_id VARCHAR(200);

COMMENT ON COLUMN agents.model_id IS 'OpenRouter model ID for this agent';

-- Create meeting_materials table (metadata only, no file storage yet)
CREATE TABLE IF NOT EXISTS meeting_materials (
    material_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    kind VARCHAR(50) NOT NULL,
    title VARCHAR(500),
    body_text TEXT,
    url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT meeting_materials_kind_check CHECK (kind IN ('text', 'link', 'file_placeholder'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_meeting_materials_debate_id ON meeting_materials(debate_id);
CREATE INDEX IF NOT EXISTS idx_meeting_materials_kind ON meeting_materials(kind);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_meeting_materials_updated_at ON meeting_materials;
CREATE TRIGGER update_meeting_materials_updated_at
    BEFORE UPDATE ON meeting_materials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS policies
ALTER TABLE meeting_materials ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Enable all for service_role" ON meeting_materials;
CREATE POLICY "Enable all for service_role"
    ON meeting_materials
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Comments
COMMENT ON TABLE meeting_materials IS 'Meeting materials metadata (text/links/file placeholders)';
COMMENT ON COLUMN meeting_materials.kind IS 'text: inline text, link: URL, file_placeholder: future upload';
COMMENT ON COLUMN meeting_materials.title IS 'Material title/name';
COMMENT ON COLUMN meeting_materials.body_text IS 'For kind=text: the actual text content';
COMMENT ON COLUMN meeting_materials.url IS 'For kind=link or file_placeholder: the URL';
