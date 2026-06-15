# TICKET-12: Materials Ingestion (Phase 1: Upload + Extract + Chunk + Provenance)

Status: Ready
Owner: Engineering
Last updated: 2026-02-09

## Goal
Implement the materials ingestion pipeline so users can upload real files and agents can reliably cite ingested content.

Phase 1 is about correctness, provenance, and debuggability:
- Upload -> store -> extract -> chunk -> persist -> status/progress
- No duplicate systems (reuse existing DB tables where possible)
- Retrieval can be “simple” in Phase 1 (concatenate top chunks) as long as citations work end-to-end

## References
- Decisions: `arinar-v2/docs/design/DECISIONS-SOURCE-OF-TRUTH-2026-02-09.md`
- Product flow: `arinar-v2/docs/product/MEETING-FLOW-MEMORY-ARTIFACTS.md`
- Architecture: `arinar-v2/docs/design/AGENT-PREPARATION-ARCHITECTURE.md`

## Non-negotiables
- OpenRouter-only. No provider SDKs.
- BYOK: never store OpenRouter keys server-side.
- Provenance-first: every chunk must be traceable to a source (file/url/text) + offsets/pages.
- No duplicate chunk stores:
  - store chunks in `memory_chunks` with `chunk_metadata` provenance
  - store material metadata in `meeting_materials`
- Celery + Redis from day 1 (durable background processing).
- Security baseline:
  - strict allowlist of file types
  - magic-byte sniffing (don’t trust extension)
  - size limits
  - quarantine/validation before processing

## Scope

### 1) Storage (MinIO) + Upload Endpoint
Implement:
- `POST /debates/{debate_id}/materials/upload` (multipart upload)
  - Accept multiple files
  - Create `meeting_materials` rows (`kind=file`) and store `file_key`, `file_size_bytes`, `processed_status=pending`
  - Return `material_ids[]` and `job_id`

Notes:
- Current DB has `meeting_materials.kind` limited to `text|link|file_placeholder`.
  - Update schema to support real files (e.g. `file`), without breaking existing behavior.

### 2) Background Processing (Celery)
Create Celery tasks to process each material:
- Validate file type + size + magic bytes
- Extract text:
  - PDF (text layer)
  - DOCX
  - TXT/MD
- If scanned PDF detected:
  - mark as `needs_ocr`
  - do not OCR in Phase 1 unless explicitly enabled per material (API flag)
- Chunk text:
  - simple paragraph-aware chunking with overlap
  - chunk IDs must be stable per material+index
- Persist chunks:
  - store in `memory_chunks`
  - `agent_id` must be nullable (material chunks aren’t agent-owned)
  - `source_debate_id` = debate_id
  - `chunk_metadata` includes: material_id, chunk_index, page_num/offsets, sha256, category (optional), extraction_method

Update `meeting_materials`:
- `processed_status`: pending|processing|complete|failed|needs_ocr
- `processing_metadata`: page_count, word_count, chunk_count, durations, errors

### 3) Status + Progress Endpoints
Implement:
- `GET /debates/{debate_id}/materials/status`
  - totals + per-material status and progress
- (Optional Phase 1) `POST /debates/{debate_id}/materials/retry/{material_id}`

### 4) UI Integration (Minimal)
Enable file upload in setup Materials step:
- remove “Soon” disable
- upload files to the new endpoint
- show progress statuses and errors

### 5) Citations (Phase 1 baseline)
During debate turns (or at least in summary/artifact generation later), the system must be able to reference chunk IDs and show provenance.
For Phase 1:
- It is acceptable to inject top-N chunks into context instead of vector search, as long as:
  - chunk IDs and provenance exist
  - responses can cite chunk IDs

## Testing
- Unit tests for:
  - file validation
  - text extraction
  - chunking correctness
- Integration tests for:
  - upload -> material row created
  - Celery task processes material -> chunks created
  - status endpoint reflects updates

Tests must not require real OpenRouter calls.

## Gates (Definition of Done)
From `arinar-v2`:
1. `make verify` PASS
2. DB migration(s) added and applied locally via `make db-migrate`
3. A PDF upload produces:
  - `meeting_materials.processed_status=complete`
  - `memory_chunks` rows with provenance metadata
4. UI shows upload progress and final state

## Report
Write:
- `arinar-v2/reports/tickets/TICKET-12-2026-02-09-v1.md`

Include:
- changed files list
- schema changes summary
- commands run (summarized)
- gates table (YES/NO)

