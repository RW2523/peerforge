-- 012: Signed, publicly-verifiable Review-Readiness Certificates (Pillar 3 hardening)
--
-- issued_certificates: immutable record of every issued certificate — the
-- signed anchor payload snapshot lets anyone re-verify the signature and hash
-- later, and compare against a live recomputation of the session's evidence.
--
-- signing_keys: Ed25519 keypair used to sign certificates. Dev stores the
-- private key in the database; production should supply it via the
-- CERT_SIGNING_KEY_PEM environment variable (the loader prefers env).

CREATE TABLE IF NOT EXISTS signing_keys (
    key_id      VARCHAR(16) PRIMARY KEY,
    private_key TEXT NOT NULL,
    public_key  TEXT NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS issued_certificates (
    certificate_id VARCHAR(24) PRIMARY KEY,
    debate_id      UUID NOT NULL REFERENCES debates(debate_id) ON DELETE CASCADE,
    workspace_id   UUID NOT NULL,
    anchor_hash    VARCHAR(64) NOT NULL,
    algorithm      VARCHAR(32) NOT NULL DEFAULT 'ed25519+sha256',
    signature      TEXT NOT NULL,
    key_id         VARCHAR(16) NOT NULL REFERENCES signing_keys(key_id),
    payload        JSONB NOT NULL,
    summary        JSONB NOT NULL,
    issued_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_issued_certs_debate
    ON issued_certificates (debate_id, issued_at DESC);
