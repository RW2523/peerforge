-- Add autonomous debate columns
ALTER TABLE debates ADD COLUMN IF NOT EXISTS autonomous_mode BOOLEAN DEFAULT false;
ALTER TABLE debates ADD COLUMN IF NOT EXISTS autonomous_status TEXT CHECK (autonomous_status IN ('running', 'paused', 'completed', NULL));
ALTER TABLE debates ADD COLUMN IF NOT EXISTS auto_turn_delay_seconds INTEGER DEFAULT 10;

-- Index for querying running autonomous debates
CREATE INDEX IF NOT EXISTS idx_debates_autonomous_status ON debates(autonomous_status) WHERE autonomous_status IS NOT NULL;
