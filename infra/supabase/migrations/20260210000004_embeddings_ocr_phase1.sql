-- Migration: Embeddings + OCR Phase 1
-- Date: 2026-02-10
-- Ticket: TICKET-12.1
-- Description: Add embeddings and OCR support for materials (OpenRouter BYOK, client-driven)

-- ============================================================================
-- ADD EMBEDDING SUPPORT TO memory_chunks
-- ============================================================================

-- Add embedding columns
ALTER TABLE memory_chunks
    ADD COLUMN IF NOT EXISTS embedding_model_id VARCHAR(200),
    ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(50) DEFAULT 'not_started',
    ADD COLUMN IF NOT EXISTS embedding_vector JSONB,  -- Float array, pgvector migration later
    ADD COLUMN IF NOT EXISTS embedding_generated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS embedding_error TEXT;

-- Add constraint for embedding_status
ALTER TABLE memory_chunks DROP CONSTRAINT IF EXISTS memory_chunks_embedding_status_check;
ALTER TABLE memory_chunks ADD CONSTRAINT memory_chunks_embedding_status_check
    CHECK (embedding_status IN ('not_started', 'queued', 'running', 'complete', 'failed'));

-- Add index for embedding queries
CREATE INDEX IF NOT EXISTS idx_memory_chunks_embedding_status ON memory_chunks(embedding_status);

-- Add index for chunks ready for retrieval (complete embeddings)
CREATE INDEX IF NOT EXISTS idx_memory_chunks_embedded ON memory_chunks(source_debate_id, embedding_status)
    WHERE embedding_status = 'complete';

-- Comments
COMMENT ON COLUMN memory_chunks.embedding_model_id IS 'OpenRouter model ID used for embeddings (e.g., text-embedding-3-small via OpenRouter)';
COMMENT ON COLUMN memory_chunks.embedding_status IS 'Embedding generation status: not_started, queued, running, complete, failed';
COMMENT ON COLUMN memory_chunks.embedding_vector IS 'Embedding vector as JSONB float array (migrate to pgvector in Phase 2)';
COMMENT ON COLUMN memory_chunks.embedding_generated_at IS 'When embedding was generated';
COMMENT ON COLUMN memory_chunks.embedding_error IS 'Error message if embedding generation failed';

-- ============================================================================
-- ADD WORKSPACE SETTINGS FOR EMBEDDINGS MODEL DEFAULT
-- ============================================================================

-- Workspaces table should have settings JSONB column (created in earlier migration)
-- Add comment to clarify embeddings model storage
COMMENT ON COLUMN workspaces.settings IS 'Workspace settings JSONB: embeddings_model_id, default policies, etc.';

-- Example settings structure (documentation):
-- {
--   "embeddings_model_id": "openai/text-embedding-3-small",
--   "default_chunk_size": 400,
--   "ocr_enabled": true
-- }

-- ============================================================================
-- UPDATE material_processing_jobs TO TRACK EMBEDDING/OCR JOBS
-- ============================================================================

-- Job types 'embed' and 'ocr' already exist in constraint from Phase 1
-- Verify constraint includes them
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'material_jobs_type_check'
        AND contype = 'c'
        AND pg_get_constraintdef(oid) LIKE '%embed%'
    ) THEN
        ALTER TABLE material_processing_jobs DROP CONSTRAINT IF EXISTS material_jobs_type_check;
        ALTER TABLE material_processing_jobs ADD CONSTRAINT material_jobs_type_check 
            CHECK (job_type IN ('extract', 'chunk', 'embed', 'ocr'));
    END IF;
END $$;

-- Add index for embedding job queries
CREATE INDEX IF NOT EXISTS idx_material_jobs_embed ON material_processing_jobs(material_id, job_type)
    WHERE job_type = 'embed';

-- Add index for OCR job queries  
CREATE INDEX IF NOT EXISTS idx_material_jobs_ocr ON material_processing_jobs(material_id, job_type)
    WHERE job_type = 'ocr';

-- ============================================================================
-- UPDATE meeting_materials OCR METADATA
-- ============================================================================

-- Add OCR-specific metadata fields to processing_metadata JSONB
-- Example structure:
-- {
--   "ocr_required": true,
--   "ocr_completed": false,
--   "ocr_page_count": 10,
--   "ocr_confidence_avg": 0.95,
--   "ocr_tool": "tesseract",
--   "ocr_duration_ms": 12500
-- }

COMMENT ON COLUMN meeting_materials.processing_metadata IS 'Processing metadata: page_count, word_count, chunk_count, ocr_required, ocr_completed, ocr_confidence_avg, errors, durations';

-- Add index for materials needing OCR
CREATE INDEX IF NOT EXISTS idx_meeting_materials_needs_ocr ON meeting_materials(debate_id, processed_status)
    WHERE processed_status = 'needs_ocr';

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================

-- Grant read on workspaces settings for embedding model defaults
GRANT SELECT ON workspaces TO authenticated;
GRANT UPDATE (settings) ON workspaces TO authenticated;

-- Grant read/write on embedding columns
-- (No specific grants needed; already covered by existing table permissions)
