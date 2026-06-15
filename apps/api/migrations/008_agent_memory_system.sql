-- Agent Memory System - Persistent learning across debates
-- Enables agents to learn from past debates and get better over time

CREATE TABLE IF NOT EXISTS agent_memories (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    agent_role TEXT NOT NULL,  -- "Professional Arguer", "Visionary", etc.
    memory_type TEXT NOT NULL,  -- "stance", "reasoning_pattern", "effectiveness", "relationship"
    content JSONB NOT NULL,
    debate_ids UUID[] DEFAULT ARRAY[]::UUID[],  -- Which debates contributed to this memory
    confidence FLOAT DEFAULT 0.5,  -- How confident we are in this memory (0-1)
    effectiveness FLOAT DEFAULT 0.5,  -- How effective this pattern/stance has been (0-1)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE,
    use_count INTEGER DEFAULT 0
);

-- Index for fast lookups by agent role
CREATE INDEX IF NOT EXISTS idx_agent_memories_role ON agent_memories(agent_role, workspace_id);

-- Index for memory type filtering
CREATE INDEX IF NOT EXISTS idx_agent_memories_type ON agent_memories(memory_type);

-- Index for effectiveness scoring
CREATE INDEX IF NOT EXISTS idx_agent_memories_effectiveness ON agent_memories(effectiveness DESC);

-- Agent Personality Profiles
CREATE TABLE IF NOT EXISTS agent_personalities (
    personality_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    agent_role TEXT NOT NULL,
    personality_traits JSONB NOT NULL DEFAULT '{}'::JSONB,
    signature_phrases TEXT[] DEFAULT ARRAY[]::TEXT[],
    debate_style JSONB DEFAULT '{}'::JSONB,
    relationships JSONB DEFAULT '{}'::JSONB,  -- Who they often agree/disagree with
    debates_participated INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(workspace_id, agent_role)
);

-- Index for personality lookups
CREATE INDEX IF NOT EXISTS idx_agent_personalities_role ON agent_personalities(agent_role, workspace_id);

-- Debate Analytics (for replay & analysis)
CREATE TABLE IF NOT EXISTS debate_analytics (
    analytics_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::JSONB,  -- progress_score, new_info_rate, etc.
    insights JSONB DEFAULT '{}'::JSONB,  -- turning_points, influential_agents, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(debate_id, turn_number)
);

-- Index for analytics queries
CREATE INDEX IF NOT EXISTS idx_debate_analytics_debate ON debate_analytics(debate_id, turn_number);

COMMENT ON TABLE agent_memories IS 'Persistent agent memory across debates - enables learning over time';
COMMENT ON TABLE agent_personalities IS 'Agent personality profiles that evolve with experience';
COMMENT ON TABLE debate_analytics IS 'Per-turn analytics for debate replay and analysis';
