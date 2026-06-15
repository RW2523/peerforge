-- Add autonomous review mode columns and extend debate state machine
-- These columns support the autonomous review loop and host orchestration.

ALTER TABLE debates
  ADD COLUMN IF NOT EXISTS autonomous_mode         BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS autonomous_status       VARCHAR(50) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS auto_turn_delay_seconds INTEGER DEFAULT 5,
  ADD COLUMN IF NOT EXISTS max_rounds              INTEGER DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS current_round           INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS enable_host             BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS host_agent_id           UUID DEFAULT NULL;

-- Extend the state enum to include aliases used by legacy routes
ALTER TABLE debates DROP CONSTRAINT IF EXISTS debates_state_check;
ALTER TABLE debates ADD CONSTRAINT debates_state_check
  CHECK (state IN ('draft','pending','running','paused','ended','live','complete'));

COMMENT ON COLUMN debates.autonomous_mode IS 'Whether the review runs turn-by-turn without human intervention';
COMMENT ON COLUMN debates.enable_host IS 'Whether a Review Chair agent synthesises a final peer-review recommendation';
