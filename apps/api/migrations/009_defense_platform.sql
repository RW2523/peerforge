-- ============================================================
-- Migration 009: Academic Defense Readiness Platform tables
-- ============================================================

-- ── Research Profiles ─────────────────────────────────────────
-- One per debate/session; stores the structured analysis of
-- the student's uploaded research materials.
CREATE TABLE IF NOT EXISTS research_profiles (
    profile_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id           UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    workspace_id        UUID NOT NULL,

    -- Core extracted fields (NULL until analysis runs)
    research_problem    TEXT,
    research_gap        TEXT,
    research_questions  JSONB  DEFAULT '[]'::JSONB,   -- list of strings
    main_claim          TEXT,
    methodology         TEXT,
    dataset_details     TEXT,
    contribution        TEXT,
    evidence_summary    TEXT,
    limitations         TEXT,
    weak_areas          JSONB  DEFAULT '[]'::JSONB,   -- [{area, reason}]
    possible_questions  JSONB  DEFAULT '[]'::JSONB,   -- preliminary question seeds

    -- Full structured JSON returned by the LLM (for debugging)
    raw_analysis        JSONB  DEFAULT '{}'::JSONB,

    -- Chunk provenance
    chunks_used         UUID[] DEFAULT ARRAY[]::UUID[],
    chunk_count         INTEGER DEFAULT 0,

    model_used          TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',  -- pending|running|complete|failed
    error_message       TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(debate_id)
);
CREATE INDEX IF NOT EXISTS idx_research_profiles_debate ON research_profiles(debate_id);
CREATE INDEX IF NOT EXISTS idx_research_profiles_workspace ON research_profiles(workspace_id);

-- ── Defense Questions ──────────────────────────────────────────
-- Generated questions for a defense session, grounded in chunks.
CREATE TABLE IF NOT EXISTS defense_questions (
    question_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id       UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    profile_id      UUID REFERENCES research_profiles(profile_id) ON DELETE SET NULL,

    question_text   TEXT NOT NULL,
    category        TEXT NOT NULL,   -- see 10 categories below
    difficulty      TEXT NOT NULL DEFAULT 'medium',  -- easy|medium|hard
    persona         TEXT NOT NULL,   -- committee role
    expected_answer TEXT,            -- answer direction / rubric hint
    follow_up_rule  TEXT,            -- when to ask follow-up
    follow_up_q     TEXT,            -- the follow-up question itself

    -- Source grounding (must be set — never invented)
    source_document_id UUID REFERENCES meeting_materials(material_id) ON DELETE SET NULL,
    source_chunk_id    UUID,         -- FK to memory_chunks (no hard FK for flexibility)
    source_excerpt     TEXT,         -- short quote from the chunk

    -- Runtime state
    asked           BOOLEAN DEFAULT FALSE,
    asked_at        TIMESTAMP WITH TIME ZONE,
    answer_id       UUID,            -- FK to session_answers once answered

    seq_order       INTEGER DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_defense_questions_debate  ON defense_questions(debate_id);
CREATE INDEX IF NOT EXISTS idx_defense_questions_profile ON defense_questions(profile_id);
CREATE INDEX IF NOT EXISTS idx_defense_questions_category ON defense_questions(category);

-- ── Session Answers ────────────────────────────────────────────
-- Student answers with 6-axis AI evaluation.
CREATE TABLE IF NOT EXISTS session_answers (
    answer_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id       UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    question_id     UUID REFERENCES defense_questions(question_id) ON DELETE SET NULL,

    -- Student input
    answer_text     TEXT NOT NULL,
    answered_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 6-axis scores (0-10 each)
    score_relevance            FLOAT,
    score_evidence             FLOAT,
    score_clarity              FLOAT,
    score_completeness         FLOAT,
    score_methodology          FLOAT,
    score_critical_thinking    FLOAT,
    overall_score              FLOAT,   -- average of the 6

    -- Evaluation narrative
    strength            TEXT,
    weakness            TEXT,
    missing_evidence    TEXT,
    suggested_improvement TEXT,
    follow_up_needed    BOOLEAN DEFAULT FALSE,
    follow_up_question  TEXT,

    -- Full evaluation JSON
    evaluation_json JSONB DEFAULT '{}'::JSONB,

    model_used      TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_session_answers_debate   ON session_answers(debate_id);
CREATE INDEX IF NOT EXISTS idx_session_answers_question ON session_answers(question_id);

-- ── Readiness Reports ──────────────────────────────────────────
-- One final report per session, aggregated from session_answers.
CREATE TABLE IF NOT EXISTS readiness_reports (
    report_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id       UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    workspace_id    UUID NOT NULL,

    -- Aggregate scores (0-100)
    overall_readiness   FLOAT,
    research_clarity    FLOAT,
    methodology_score   FLOAT,
    evidence_score      FLOAT,
    critical_thinking   FLOAT,
    communication       FLOAT,

    -- Narrative sections
    strong_answers      JSONB DEFAULT '[]'::JSONB,   -- [{question, score, summary}]
    weak_answers        JSONB DEFAULT '[]'::JSONB,
    repeated_issues     JSONB DEFAULT '[]'::JSONB,   -- [{issue, frequency}]
    likely_questions    JSONB DEFAULT '[]'::JSONB,   -- predicted committee questions
    improvement_plan    JSONB DEFAULT '[]'::JSONB,   -- [{area, action, priority}]
    next_recommendation TEXT,

    -- Full report JSON (for export)
    full_report_json JSONB DEFAULT '{}'::JSONB,

    answers_evaluated INTEGER DEFAULT 0,
    model_used        TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',
    generated_at      TIMESTAMP WITH TIME ZONE,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(debate_id)
);
CREATE INDEX IF NOT EXISTS idx_readiness_reports_debate    ON readiness_reports(debate_id);
CREATE INDEX IF NOT EXISTS idx_readiness_reports_workspace ON readiness_reports(workspace_id);

-- ── Audit Logs ─────────────────────────────────────────────────
-- Lightweight immutable audit trail (no secrets ever stored here).
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id   UUID REFERENCES debates(debate_id) ON DELETE SET NULL,
    workspace_id UUID,
    action      TEXT NOT NULL,         -- e.g. "analyze_research", "generate_questions"
    actor       TEXT,                  -- user_id or "system"
    metadata    JSONB DEFAULT '{}'::JSONB,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_debate ON audit_logs(debate_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
