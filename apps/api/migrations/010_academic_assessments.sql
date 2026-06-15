-- 010: Academic Assessment Matrix
-- Stores the 10-dimension formative assessment generated after session
-- activities (practice Q&A, panel discussion, voice practice).

CREATE TABLE IF NOT EXISTS academic_assessments (
    assessment_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id       UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    workspace_id    UUID,
    trigger_source  TEXT NOT NULL DEFAULT 'manual',
    -- [{"key": "research_readiness", "label": "Research Readiness",
    --   "score": 7.5, "comment": "..."}] — exactly 10 entries
    dimensions      JSONB NOT NULL,
    overall_score   NUMERIC(4,1),
    overall_remarks TEXT,
    basis           JSONB,            -- what evidence informed the assessment
    model_used      TEXT,
    generated_at    TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_academic_assessments_debate
    ON academic_assessments (debate_id, generated_at DESC);
