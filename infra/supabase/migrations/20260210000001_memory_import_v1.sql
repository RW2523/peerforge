-- Migration: Memory Import V1 (Grants + Audit Extensions)
-- Date: 2026-02-10
-- Ticket: TICKET-15
-- Description: Adds debate_memory_grants table for user-controlled memory import
--              and extends memory_access_log for compliance auditing

-- 1. Create debate_memory_grants table (explicit allowlist for memory import)
CREATE TABLE IF NOT EXISTS debate_memory_grants (
    grant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    source_debate_id UUID REFERENCES debates(debate_id) ON DELETE CASCADE,
    source_artifact_id UUID,  -- Optional: if importing specific artifact
    source_type VARCHAR(50) NOT NULL,  -- 'debate_full', 'artifact', 'materials_only'
    scope VARCHAR(50) NOT NULL,  -- 'all_agents', 'specific_agents'
    allowed_participant_ids UUID[],  -- NULL if scope='all_agents'
    granted_by VARCHAR(255) NOT NULL,  -- user_id who granted access
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,  -- Optional: time-bound access
    metadata JSONB DEFAULT '{}',  -- Import context (why, what topics)
    
    -- Ensure scope consistency
    CONSTRAINT valid_scope CHECK (
        (scope = 'all_agents' AND allowed_participant_ids IS NULL) OR
        (scope = 'specific_agents' AND allowed_participant_ids IS NOT NULL AND array_length(allowed_participant_ids, 1) > 0)
    ),
    
    -- Prevent duplicate grants for same source
    CONSTRAINT unique_grant_per_source UNIQUE (debate_id, source_debate_id, source_artifact_id, scope)
);

-- Indexes for grant lookups
CREATE INDEX IF NOT EXISTS idx_memory_grants_debate ON debate_memory_grants(debate_id);
CREATE INDEX IF NOT EXISTS idx_memory_grants_source ON debate_memory_grants(source_debate_id);
CREATE INDEX IF NOT EXISTS idx_memory_grants_artifact ON debate_memory_grants(source_artifact_id) WHERE source_artifact_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_grants_scope ON debate_memory_grants(debate_id, scope);

-- Comment
COMMENT ON TABLE debate_memory_grants IS 'Explicit grants for memory import: which debates/artifacts can be accessed by which agents';
COMMENT ON COLUMN debate_memory_grants.scope IS 'all_agents: any participant can access; specific_agents: only allowed_participant_ids';
COMMENT ON COLUMN debate_memory_grants.source_type IS 'What to import: debate_full (all chunks), artifact (specific artifact chunks), materials_only (just materials)';

-- 2. Extend memory_access_log for compliance auditing
-- Add columns to track which chunks were returned and which grants allowed access
ALTER TABLE memory_access_log ADD COLUMN IF NOT EXISTS chunk_ids UUID[];
ALTER TABLE memory_access_log ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Index for chunk_ids array lookups (GIN index for contains queries)
CREATE INDEX IF NOT EXISTS idx_memory_access_chunk_ids ON memory_access_log USING GIN(chunk_ids);

-- Comment
COMMENT ON COLUMN memory_access_log.chunk_ids IS 'UUIDs of chunks returned in this retrieval (for audit trail)';
COMMENT ON COLUMN memory_access_log.metadata IS 'Additional context: grant_ids that allowed access, retrieval_method, etc.';

-- 3. Create helper view for compliance auditing (optional, for debugging)
CREATE OR REPLACE VIEW memory_access_audit AS
SELECT
    mal.access_id,
    mal.agent_id,
    mal.debate_id,
    mal.access_type,
    mal.query_text,
    mal.results_count,
    mal.created_at AS accessed_at,
    mal.chunk_ids,
    mal.metadata->>'grant_ids' AS grant_ids_used,
    mal.metadata->>'retrieval_method' AS retrieval_method,
    d.title AS debate_title
FROM memory_access_log mal
LEFT JOIN debates d ON mal.debate_id = d.debate_id
ORDER BY mal.created_at DESC;

COMMENT ON VIEW memory_access_audit IS 'Compliance-ready audit view showing who accessed what memory and why';
