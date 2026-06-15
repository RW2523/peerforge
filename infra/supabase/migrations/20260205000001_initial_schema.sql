-- Migration: 20260205000001_initial_schema.sql
-- Description: Initial database schema for Arinar V2
-- Includes: tenants, workspaces, debates, participants, events, agents, memory fabric

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgcrypto for encryption functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- TENANT AND WORKSPACE SCHEMA
-- ============================================================================

-- Tenants table (top-level isolation boundary)
CREATE TABLE tenants (
    tenant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT tenants_status_check CHECK (status IN ('active', 'suspended', 'deleted'))
);

-- Workspaces table (projects/teams within tenant)
CREATE TABLE workspaces (
    workspace_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(tenant_id, slug)
);

-- ============================================================================
-- DEBATE AND PARTICIPANT SCHEMA
-- ============================================================================

-- Debates table (discussion sessions)
CREATE TABLE debates (
    debate_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    state VARCHAR(50) NOT NULL DEFAULT 'draft',
    timebox_minutes INTEGER,
    policy_config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    
    CONSTRAINT debates_state_check CHECK (state IN (
        'draft', 'preflight', 'live', 'paused', 'synthesis', 'closed', 'archived'
    ))
);

-- Participants table (agents and humans in debates)
CREATE TABLE participants (
    participant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    participant_type VARCHAR(50) NOT NULL,
    role_name VARCHAR(100) NOT NULL,
    agent_config JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT participants_type_check CHECK (participant_type IN ('agent', 'human'))
);

-- ============================================================================
-- EVENT LEDGER SCHEMA
-- ============================================================================

-- Events table (immutable event log for all debate activity)
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    sender_type VARCHAR(50) NOT NULL,
    sender_id UUID,
    mentions UUID[],
    thread_id UUID,
    content JSONB NOT NULL DEFAULT '{}',
    citation_refs JSONB DEFAULT '[]',
    priority INTEGER DEFAULT 2,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sequence_number BIGSERIAL,
    
    CONSTRAINT events_sender_type_check CHECK (sender_type IN ('agent', 'human', 'system')),
    CONSTRAINT events_priority_check CHECK (priority BETWEEN 0 AND 3)
);

-- ============================================================================
-- AGENT SCHEMA
-- ============================================================================

-- Agents table (persistent agent definitions)
CREATE TABLE agents (
    agent_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    role_description TEXT,
    system_prompt TEXT,
    model_config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Agent Knowledge Units (facts/learnings associated with agents)
CREATE TABLE agent_knowledge_units (
    knowledge_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
    source_debate_id UUID REFERENCES debates(debate_id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    confidence_score FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- MEMORY FABRIC SCHEMA
-- ============================================================================

-- Memory Events (raw memory capture from sessions)
CREATE TABLE memory_events (
    memory_event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(agent_id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Memory State (current/consolidated memory for agents)
CREATE TABLE memory_state (
    memory_state_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
    debate_id UUID REFERENCES debates(debate_id) ON DELETE SET NULL,
    state_type VARCHAR(100) NOT NULL,
    content JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Memory Chunks (searchable memory segments)
CREATE TABLE memory_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
    source_debate_id UUID REFERENCES debates(debate_id) ON DELETE SET NULL,
    chunk_text TEXT NOT NULL,
    chunk_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Memory Access Log (audit trail for memory retrieval)
CREATE TABLE memory_access_log (
    access_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    access_type VARCHAR(100) NOT NULL,
    query_text TEXT,
    results_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Tenant/Workspace filtering indexes
CREATE INDEX idx_workspaces_tenant_id ON workspaces(tenant_id);
CREATE INDEX idx_debates_workspace_id ON debates(workspace_id);
CREATE INDEX idx_debates_state ON debates(state);

-- Debate event retrieval indexes
CREATE INDEX idx_events_debate_id ON events(debate_id);
CREATE INDEX idx_events_debate_created ON events(debate_id, created_at DESC);
CREATE INDEX idx_events_sequence ON events(sequence_number);
CREATE INDEX idx_events_type ON events(event_type);

-- Participant lookup indexes
CREATE INDEX idx_participants_debate_id ON participants(debate_id);
CREATE INDEX idx_participants_type ON participants(participant_type);

-- Agent and knowledge indexes
CREATE INDEX idx_agents_workspace_id ON agents(workspace_id);
CREATE INDEX idx_agent_knowledge_agent_id ON agent_knowledge_units(agent_id);
CREATE INDEX idx_agent_knowledge_debate_id ON agent_knowledge_units(source_debate_id);

-- Memory fabric indexes
CREATE INDEX idx_memory_events_debate_id ON memory_events(debate_id);
CREATE INDEX idx_memory_events_agent_id ON memory_events(agent_id);
CREATE INDEX idx_memory_state_agent_id ON memory_state(agent_id);
CREATE INDEX idx_memory_chunks_agent_id ON memory_chunks(agent_id);
CREATE INDEX idx_memory_chunks_debate_id ON memory_chunks(source_debate_id);
CREATE INDEX idx_memory_access_log_agent_id ON memory_access_log(agent_id);
CREATE INDEX idx_memory_access_log_debate_id ON memory_access_log(debate_id);

-- ============================================================================
-- UPDATED_AT TRIGGER FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workspaces_updated_at BEFORE UPDATE ON workspaces
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_debates_updated_at BEFORE UPDATE ON debates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agent_knowledge_updated_at BEFORE UPDATE ON agent_knowledge_units
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memory_state_updated_at BEFORE UPDATE ON memory_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) - Prepared for future use
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE debates ENABLE ROW LEVEL SECURITY;
ALTER TABLE participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_knowledge_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_access_log ENABLE ROW LEVEL SECURITY;

-- Create policies (allow all for service_role initially, refine later)
CREATE POLICY "Enable all for service_role" ON tenants
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON workspaces
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON debates
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON participants
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON events
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON agents
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON agent_knowledge_units
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON memory_events
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON memory_state
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON memory_chunks
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for service_role" ON memory_access_log
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE tenants IS 'Top-level tenant isolation boundary';
COMMENT ON TABLE workspaces IS 'Projects or teams within a tenant';
COMMENT ON TABLE debates IS 'Discussion sessions with multi-agent participation';
COMMENT ON TABLE participants IS 'Agents and humans participating in debates';
COMMENT ON TABLE events IS 'Immutable event ledger for all debate activity';
COMMENT ON TABLE agents IS 'Persistent agent definitions with configuration';
COMMENT ON TABLE agent_knowledge_units IS 'Facts and learnings associated with agents';
COMMENT ON TABLE memory_events IS 'Raw memory capture from debate sessions';
COMMENT ON TABLE memory_state IS 'Consolidated current memory state for agents';
COMMENT ON TABLE memory_chunks IS 'Searchable memory segments for retrieval';
COMMENT ON TABLE memory_access_log IS 'Audit trail for memory retrieval operations';
