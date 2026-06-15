-- Migration: Add debate_outputs table for M3 end-of-meeting summaries
-- Date: 2026-02-06
-- Ticket: TICKET-07

-- Create debate_outputs table
CREATE TABLE IF NOT EXISTS debate_outputs (
    output_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    
    -- Core outputs
    summary TEXT NOT NULL,
    minutes TEXT NOT NULL,
    action_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Metadata
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_used VARCHAR(200),
    token_count INTEGER,
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT debate_outputs_unique_debate UNIQUE(debate_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_debate_outputs_debate_id ON debate_outputs(debate_id);
CREATE INDEX IF NOT EXISTS idx_debate_outputs_generated_at ON debate_outputs(generated_at DESC);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_debate_outputs_updated_at ON debate_outputs;
CREATE TRIGGER update_debate_outputs_updated_at
    BEFORE UPDATE ON debate_outputs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS policies (match debates table pattern)
ALTER TABLE debate_outputs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Enable all for service_role" ON debate_outputs;
CREATE POLICY "Enable all for service_role"
    ON debate_outputs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Comments
COMMENT ON TABLE debate_outputs IS 'M3 end-of-meeting outputs: summary, minutes, action items';
COMMENT ON COLUMN debate_outputs.summary IS 'Short summary (1-3 sentences)';
COMMENT ON COLUMN debate_outputs.minutes IS 'Detailed meeting minutes (full discussion recap)';
COMMENT ON COLUMN debate_outputs.action_items IS 'Array of action items with owner/description/priority';
COMMENT ON COLUMN debate_outputs.model_used IS 'OpenRouter model ID used for generation';
