-- PeerForge migration: add 'literature' kind to meeting_materials

-- Extend the kind constraint to include 'literature'
ALTER TABLE meeting_materials DROP CONSTRAINT IF EXISTS meeting_materials_kind_check;
ALTER TABLE meeting_materials ADD CONSTRAINT meeting_materials_kind_check
    CHECK (kind IN ('text', 'link', 'file_placeholder', 'file', 'literature'));

COMMENT ON CONSTRAINT meeting_materials_kind_check ON meeting_materials
    IS 'literature: academic paper saved from arXiv/Semantic Scholar/PubMed/Crossref/OpenAlex';

-- Note: literature papers reuse existing columns:
--   title            → paper title
--   body_text        → full paper chunk text (TITLE + AUTHORS + ABSTRACT) for RAG
--   url              → paper URL / DOI link
--   processing_metadata → { source, doi, year, authors, venue, citation_count, label }
--   processed_status → 'complete' (already processed inline, no Celery job needed)
