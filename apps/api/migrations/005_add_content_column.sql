-- Migration: Add content column to document_sections
-- Version: 005
-- Description: Add TEXT column to store actual section content

-- Add content column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'document_sections' 
        AND column_name = 'content'
    ) THEN
        ALTER TABLE document_sections 
        ADD COLUMN content TEXT;
        
        COMMENT ON COLUMN document_sections.content IS 'The actual text/markdown content of the section';
    END IF;
END $$;

-- Add updated_at column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'document_sections' 
        AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE document_sections 
        ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
END $$;

-- Add trigger for updated_at
CREATE OR REPLACE FUNCTION update_document_sections_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_document_sections_updated_at ON document_sections;
CREATE TRIGGER trigger_document_sections_updated_at
    BEFORE UPDATE ON document_sections
    FOR EACH ROW
    EXECUTE FUNCTION update_document_sections_updated_at();
