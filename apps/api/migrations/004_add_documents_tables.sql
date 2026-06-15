-- Migration: Add documents tables
-- Version: 004
-- Description: Add support for collaborative document generation during debates

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    template_id VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'in_progress', 'completed', 'exported')),
    yjs_state_vector BYTEA,  -- Yjs document state for persistence
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT valid_metadata CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT valid_completion CHECK (
        (status = 'completed' AND completed_at IS NOT NULL) OR
        (status != 'completed' AND completed_at IS NULL)
    )
);

-- Document sections table
CREATE TABLE IF NOT EXISTS document_sections (
    section_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    section_key VARCHAR(100) NOT NULL,
    section_title VARCHAR(200) NOT NULL,
    section_type VARCHAR(50) DEFAULT 'text' CHECK (section_type IN ('text', 'list', 'diagram', 'table')),
    section_order INTEGER NOT NULL DEFAULT 0,
    
    -- Assignment
    assigned_agent_id UUID REFERENCES agents(agent_id) ON DELETE SET NULL,
    assigned_agent_name VARCHAR(200),
    assignment_strategy VARCHAR(50) CHECK (assignment_strategy IN ('host', 'role', 'manual', 'auto')),
    
    -- Progress tracking
    word_limit INTEGER CHECK (word_limit IS NULL OR word_limit > 0),
    word_count INTEGER DEFAULT 0 CHECK (word_count >= 0),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed', 'review')),
    
    -- Schema for structured content
    content_schema JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    UNIQUE(document_id, section_key),
    CONSTRAINT valid_word_count CHECK (word_limit IS NULL OR word_count <= word_limit * 1.2), -- Allow 20% overflow
    CONSTRAINT valid_schema CHECK (content_schema IS NULL OR jsonb_typeof(content_schema) = 'object'),
    CONSTRAINT valid_order CHECK (section_order >= 0)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_debate ON documents(debate_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sections_document ON document_sections(document_id);
CREATE INDEX IF NOT EXISTS idx_sections_status ON document_sections(status);
CREATE INDEX IF NOT EXISTS idx_sections_agent ON document_sections(assigned_agent_id) WHERE assigned_agent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sections_order ON document_sections(document_id, section_order);

-- Updated_at trigger for documents
CREATE OR REPLACE FUNCTION update_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_documents_updated_at();

-- Auto-complete document when all sections done
CREATE OR REPLACE FUNCTION check_document_completion()
RETURNS TRIGGER AS $$
DECLARE
    all_completed BOOLEAN;
    doc_status VARCHAR(50);
BEGIN
    -- Get document status
    SELECT status INTO doc_status FROM documents WHERE document_id = NEW.document_id;
    
    -- Only check if document is in_progress
    IF doc_status = 'in_progress' THEN
        -- Check if all sections are completed
        SELECT bool_and(status = 'completed') INTO all_completed
        FROM document_sections
        WHERE document_id = NEW.document_id;
        
        -- Update document if all sections complete
        IF all_completed THEN
            UPDATE documents
            SET status = 'completed', completed_at = NOW()
            WHERE document_id = NEW.document_id AND status = 'in_progress';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_check_document_completion
    AFTER UPDATE ON document_sections
    FOR EACH ROW
    WHEN (NEW.status = 'completed' AND OLD.status != 'completed')
    EXECUTE FUNCTION check_document_completion();

-- Comments for documentation
COMMENT ON TABLE documents IS 'Collaborative documents generated during debates';
COMMENT ON TABLE document_sections IS 'Individual sections within a document, assigned to agents';
COMMENT ON COLUMN documents.yjs_state_vector IS 'Persisted Yjs CRDT state for document recovery';
COMMENT ON COLUMN document_sections.content_schema IS 'JSON Schema for validating AI-generated structured content';
