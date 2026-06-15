-- Migration: Materials Ingestion Phase 1
-- Date: 2026-02-09
-- Ticket: TICKET-12
-- Description: Enable real file uploads, processing pipeline, and chunk storage with provenance

-- ============================================================================
-- UPDATE meeting_materials FOR REAL FILE SUPPORT
-- ============================================================================

-- Drop old constraint and add new one to support 'file' kind
ALTER TABLE meeting_materials DROP CONSTRAINT IF EXISTS meeting_materials_kind_check;
ALTER TABLE meeting_materials ADD CONSTRAINT meeting_materials_kind_check 
    CHECK (kind IN ('text', 'link', 'file_placeholder', 'file'));

-- Add columns for file storage and processing
ALTER TABLE meeting_materials 
    ADD COLUMN IF NOT EXISTS file_key VARCHAR(500),
    ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT,
    ADD COLUMN IF NOT EXISTS file_mime_type VARCHAR(200),
    ADD COLUMN IF NOT EXISTS processed_status VARCHAR(50) DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS processing_metadata JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS processing_completed_at TIMESTAMPTZ;

-- Add constraint for processed_status
ALTER TABLE meeting_materials DROP CONSTRAINT IF EXISTS meeting_materials_status_check;
ALTER TABLE meeting_materials ADD CONSTRAINT meeting_materials_status_check
    CHECK (processed_status IN ('pending', 'processing', 'complete', 'failed', 'needs_ocr'));

-- Add index for processing status queries
CREATE INDEX IF NOT EXISTS idx_meeting_materials_status ON meeting_materials(processed_status);

-- Comments
COMMENT ON COLUMN meeting_materials.file_key IS 'MinIO object key for uploaded files';
COMMENT ON COLUMN meeting_materials.file_size_bytes IS 'File size in bytes';
COMMENT ON COLUMN meeting_materials.file_mime_type IS 'MIME type detected by magic bytes';
COMMENT ON COLUMN meeting_materials.processed_status IS 'Processing status: pending, processing, complete, failed, needs_ocr';
COMMENT ON COLUMN meeting_materials.processing_metadata IS 'Processing metadata: page_count, word_count, chunk_count, errors, durations';

-- ============================================================================
-- UPDATE memory_chunks TO SUPPORT MATERIAL CHUNKS (NOT AGENT-OWNED)
-- ============================================================================

-- Make agent_id nullable (material chunks don't belong to agents)
ALTER TABLE memory_chunks ALTER COLUMN agent_id DROP NOT NULL;

-- Add constraint: agent_id OR source_debate_id must be set
-- (a chunk is either agent-owned or material-sourced)
ALTER TABLE memory_chunks DROP CONSTRAINT IF EXISTS memory_chunks_ownership_check;
ALTER TABLE memory_chunks ADD CONSTRAINT memory_chunks_ownership_check
    CHECK (agent_id IS NOT NULL OR source_debate_id IS NOT NULL);

-- Add index for material chunks (source_debate_id when agent_id is null)
CREATE INDEX IF NOT EXISTS idx_memory_chunks_material ON memory_chunks(source_debate_id) 
    WHERE agent_id IS NULL;

-- Add index for chunk metadata queries (e.g., find by material_id)
CREATE INDEX IF NOT EXISTS idx_memory_chunks_metadata ON memory_chunks 
    USING GIN (chunk_metadata);

-- Comments
COMMENT ON COLUMN memory_chunks.agent_id IS 'Agent ID (nullable for material chunks)';
COMMENT ON COLUMN memory_chunks.chunk_metadata IS 'Provenance: material_id, chunk_index, page_num, offsets, sha256, category, extraction_method';

-- ============================================================================
-- UPDATE agent_knowledge_units TO SUPPORT KNOWLEDGE_TYPE
-- ============================================================================

-- Add knowledge_type column to support different types of knowledge
ALTER TABLE agent_knowledge_units 
    ADD COLUMN IF NOT EXISTS knowledge_type VARCHAR(100) DEFAULT 'general';

-- Add index for knowledge type queries
CREATE INDEX IF NOT EXISTS idx_agent_knowledge_type ON agent_knowledge_units(knowledge_type);

-- Comments
COMMENT ON COLUMN agent_knowledge_units.knowledge_type IS 'Type: general, artifact_section, prep_pack, research, etc.';

-- ============================================================================
-- CREATE MATERIAL_PROCESSING_JOBS TABLE (OPTIONAL: FOR TRACKING CELERY JOBS)
-- ============================================================================

-- This table tracks Celery job IDs for material processing
-- Useful for status polling and debugging
CREATE TABLE IF NOT EXISTS material_processing_jobs (
    job_id VARCHAR(100) PRIMARY KEY,
    material_id UUID NOT NULL REFERENCES meeting_materials(material_id) ON DELETE CASCADE,
    debate_id UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    
    CONSTRAINT material_jobs_type_check CHECK (job_type IN ('extract', 'chunk', 'embed', 'ocr')),
    CONSTRAINT material_jobs_status_check CHECK (status IN ('queued', 'running', 'success', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_material_jobs_material ON material_processing_jobs(material_id);
CREATE INDEX IF NOT EXISTS idx_material_jobs_debate ON material_processing_jobs(debate_id);
CREATE INDEX IF NOT EXISTS idx_material_jobs_status ON material_processing_jobs(status);

COMMENT ON TABLE material_processing_jobs IS 'Tracks Celery jobs for material processing';
COMMENT ON COLUMN material_processing_jobs.job_id IS 'Celery task ID';
COMMENT ON COLUMN material_processing_jobs.job_type IS 'Type of processing: extract, chunk, embed, ocr';
