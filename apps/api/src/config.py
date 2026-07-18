"""Application configuration"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database (5433 to avoid conflict with system Postgres; set DATABASE_URL env var to override)
    database_url: str = "postgresql://postgres:postgres@localhost:5433/peerforge_local"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = True
    
    # OpenRouter
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout: int = 120
    openrouter_max_retries: int = 2
    # Optional server-side key used by Celery workers for embedding generation.
    # Set OPENROUTER_API_KEY in .env — users can still override with their BYOK key.
    openrouter_api_key: str = ""
    # Secret used to encrypt user-stored provider keys at rest (Fernet).
    key_encryption_secret: str = ""

    # Object storage backend: 'minio' (default, local/Railway) or 's3'
    # (boto3 — Supabase Storage / R2 / AWS for free-tier deployments).
    storage_backend: str = "minio"
    s3_endpoint_url: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "peerforge-materials"
    s3_region: str = ""
    
    # Supabase Auth
    supabase_jwt_secret: str = "your-jwt-secret-here"
    supabase_url: str = "http://localhost:54321"
    supabase_project_ref: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    require_auth: bool = True

    # Billing (Track C): default plan for workspaces with no explicit plan
    # (community | professional | institution). Per-workspace plans live in
    # workspaces.plan. See services/plans.py and docs/INSTITUTIONAL.md.
    plan: str = "institution"

    # Payment (optional). When stripe_secret_key is set, paid upgrades go
    # through Stripe Checkout; otherwise the owner plan-switch is self-serve.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Map plan key → Stripe price id, e.g. {"professional": "price_...",
    # "institution": "price_..."}. Read from STRIPE_PRICE_IDS as JSON.
    stripe_price_ids: dict = {}

    # Public site URL the frontend is served from — used for Stripe return
    # URLs (checkout success/cancel, billing portal). Set in production.
    public_base_url: str = "http://localhost:3000"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "peerforge-materials"
    minio_secure: bool = False

    # Research / web-search integrations
    jina_api_key: str = ""
    semantic_scholar_api_key: str = ""
    tavily_api_key: str = ""


settings = Settings()
