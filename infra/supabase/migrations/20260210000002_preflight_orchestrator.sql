-- ============================================================================
-- PREFLIGHT ORCHESTRATOR SCHEMA
-- Tracks agent preparation runs before debate starts
-- ============================================================================

-- Preflight runs table (one per debate)
CREATE TABLE IF NOT EXISTS preflight_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT,
    metadata JSONB DEFAULT '{}',
    CONSTRAINT unique_active_run_per_debate UNIQUE (debate_id)
);

-- Preflight participant runs (one per participant per run)
CREATE TABLE IF NOT EXISTS preflight_participant_runs (
    participant_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES preflight_runs(run_id) ON DELETE CASCADE,
    participant_id UUID NOT NULL REFERENCES participants(participant_id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(agent_id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('queued', 'running', 'success', 'failed', 'skipped')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT,
    skip_reason TEXT,
    prep_pack_knowledge_id UUID REFERENCES agent_knowledge_units(knowledge_id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    CONSTRAINT unique_participant_per_run UNIQUE (run_id, participant_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_preflight_runs_debate ON preflight_runs(debate_id);
CREATE INDEX IF NOT EXISTS idx_preflight_runs_status ON preflight_runs(status);
CREATE INDEX IF NOT EXISTS idx_preflight_participant_runs_run ON preflight_participant_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_preflight_participant_runs_participant ON preflight_participant_runs(participant_id);
CREATE INDEX IF NOT EXISTS idx_preflight_participant_runs_status ON preflight_participant_runs(status);

-- Comments
COMMENT ON TABLE preflight_runs IS 'Tracks preflight preparation runs for debates';
COMMENT ON TABLE preflight_participant_runs IS 'Tracks per-participant preflight preparation status';
COMMENT ON COLUMN preflight_participant_runs.prep_pack_knowledge_id IS 'Links to the generated prep pack in agent_knowledge_units';
COMMENT ON COLUMN preflight_participant_runs.skip_reason IS 'Human-readable reason if status=skipped';
