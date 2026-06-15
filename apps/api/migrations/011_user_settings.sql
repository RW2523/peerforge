-- 011: Per-user settings — encrypted provider API keys
-- The OpenRouter key collected at sign-up (or in Settings) is stored
-- encrypted at rest and resolved server-side; it is never returned to
-- the client in full.

CREATE TABLE IF NOT EXISTS user_settings (
    user_id                  TEXT PRIMARY KEY,        -- Supabase auth UID ('test-user' in dev)
    openrouter_key_encrypted TEXT,
    openrouter_key_last4     TEXT,
    created_at               TIMESTAMPTZ DEFAULT NOW(),
    updated_at               TIMESTAMPTZ DEFAULT NOW()
);
