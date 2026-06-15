-- Live Artifacts V1 Schema
-- Date: 2026-02-10
-- Reference: docs/design/LIVE-ARTIFACTS-TECHNICAL-SPEC.md
--
-- Strategy: Minimal new tables, reuse existing (agent_knowledge_units for sections, events for deltas)
-- OpenRouter-only, BYOK, provenance-first

-- 1. Artifact Templates (built-in + custom)
CREATE TABLE IF NOT EXISTS artifact_templates (
    template_id VARCHAR(100) PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    sections JSONB NOT NULL, -- Array of {section_id, title, description, required, default_block_type}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE artifact_templates IS 'Built-in and custom artifact templates with section definitions';
COMMENT ON COLUMN artifact_templates.sections IS 'Array of section metadata: [{section_id, title, description, required, default_block_type}]';

-- Built-in templates (V1)
INSERT INTO artifact_templates (template_id, title, description, sections) VALUES
('prd', 'Product Requirements Document', 'Structured PRD with goals, non-goals, and technical approach', 
 '[
   {"section_id": "goals", "title": "Goals", "description": "What we are building and why", "required": true, "default_block_type": "rich_text"},
   {"section_id": "non_goals", "title": "Non-Goals", "description": "What is explicitly out of scope", "required": true, "default_block_type": "rich_text"},
   {"section_id": "user_stories", "title": "User Stories", "description": "Key user flows and personas", "required": false, "default_block_type": "rich_text"},
   {"section_id": "technical_approach", "title": "Technical Approach", "description": "Implementation strategy and architecture", "required": false, "default_block_type": "rich_text"},
   {"section_id": "risks", "title": "Risks & Mitigations", "description": "Known risks and mitigation plans", "required": false, "default_block_type": "rich_text"},
   {"section_id": "timeline", "title": "Timeline", "description": "Milestones and delivery schedule", "required": false, "default_block_type": "table"}
 ]'::jsonb),
('brief', 'Executive Brief', 'Board-ready executive summary', 
 '[
   {"section_id": "summary", "title": "Executive Summary", "description": "High-level overview", "required": true, "default_block_type": "rich_text"},
   {"section_id": "situation", "title": "Situation", "description": "Current state and context", "required": true, "default_block_type": "rich_text"},
   {"section_id": "options", "title": "Options", "description": "Available choices and tradeoffs", "required": true, "default_block_type": "table"},
   {"section_id": "recommendation", "title": "Recommendation", "description": "Proposed course of action", "required": true, "default_block_type": "rich_text"},
   {"section_id": "financial", "title": "Financial Impact", "description": "Cost and ROI analysis", "required": false, "default_block_type": "chart"}
 ]'::jsonb),
('memo', 'Legal/Policy Memo', 'Formal memo with analysis and recommendations', 
 '[
   {"section_id": "background", "title": "Background", "description": "Context and relevant facts", "required": true, "default_block_type": "rich_text"},
   {"section_id": "analysis", "title": "Analysis", "description": "Legal or policy analysis", "required": true, "default_block_type": "rich_text"},
   {"section_id": "conclusion", "title": "Conclusion", "description": "Summary and recommendations", "required": true, "default_block_type": "rich_text"}
 ]'::jsonb),
('plan', 'Action Plan', 'Structured plan with timeline and owners', 
 '[
   {"section_id": "objective", "title": "Objective", "description": "What we are trying to achieve", "required": true, "default_block_type": "rich_text"},
   {"section_id": "approach", "title": "Approach", "description": "How we will execute", "required": true, "default_block_type": "rich_text"},
   {"section_id": "action_items", "title": "Action Items", "description": "Concrete tasks with owners", "required": true, "default_block_type": "table"},
   {"section_id": "milestones", "title": "Milestones", "description": "Key checkpoints and deadlines", "required": false, "default_block_type": "table"}
 ]'::jsonb)
ON CONFLICT (template_id) DO NOTHING;

-- 2. Artifacts (metadata + overall status)
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    template_id VARCHAR(100) NOT NULL REFERENCES artifact_templates(template_id),
    title TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(50) NOT NULL DEFAULT 'drafting', -- drafting, review, final
    quality_report JSONB, -- Deterministic quality checks result
    coherence_version_id UUID, -- Links to polished version artifact_id if coherence pass ran
    created_by_participant_id UUID, -- who initiated (usually host)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    finalized_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    UNIQUE(debate_id, version)
);

COMMENT ON TABLE artifacts IS 'Artifact metadata. Sections stored in agent_knowledge_units with metadata.type=artifact_section';
COMMENT ON COLUMN artifacts.status IS 'drafting (agents writing), review (human reviewing), final (locked)';
COMMENT ON COLUMN artifacts.coherence_version_id IS 'If coherence pass ran, points to polished artifact version';
COMMENT ON COLUMN artifacts.quality_report IS 'Automated checks: required_sections, citations_present, outcome_addressed, etc';

CREATE INDEX IF NOT EXISTS idx_artifacts_debate ON artifacts(debate_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(status);
CREATE INDEX IF NOT EXISTS idx_artifacts_template ON artifacts(template_id);

-- 3. Leverage existing tables for sections and events
-- Sections: stored in agent_knowledge_units with metadata:
--   {
--     "type": "artifact_section",
--     "artifact_id": "uuid",
--     "section_id": "goals",
--     "section_title": "Goals",
--     "owner_participant_id": "uuid",
--     "status": "drafting|committed|locked",
--     "block_type": "rich_text|chart|table|diagram_mermaid",
--     "citations": [...],
--     "word_count": 240
--   }
--
-- Events: stored in events table with event_type:
--   - artifact_init
--   - artifact_section_started
--   - artifact_section_delta (streaming updates)
--   - artifact_section_committed
--   - artifact_coherence_started
--   - artifact_coherence_completed
--   - artifact_finalized

-- Add indexes for efficient artifact section queries
CREATE INDEX IF NOT EXISTS idx_agent_knowledge_units_artifact_section 
    ON agent_knowledge_units((metadata->>'artifact_id')) 
    WHERE metadata->>'type' = 'artifact_section';

-- Add index for artifact events
CREATE INDEX IF NOT EXISTS idx_events_artifact 
    ON events((content->>'artifact_id')) 
    WHERE event_type LIKE 'artifact_%';

-- Grant permissions (align with existing conventions)
GRANT SELECT ON artifact_templates TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON artifacts TO authenticated;
