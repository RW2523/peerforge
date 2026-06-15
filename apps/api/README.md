# apps/api - FastAPI Domain Service

## Purpose
FastAPI application providing domain APIs, business logic, and data orchestration.

## Ownership
**Team**: Backend
**Primary Contact**: TBD

## Responsibilities
- Domain entity CRUD operations
- Business rule enforcement
- Policy evaluation and guardrails
- Data validation and transformation
- Direct database access
- Integration with external services
- Orchestration of complex business operations

## Technology Stack
- FastAPI
- Python 3.11+
- SQLAlchemy (ORM)
- Pydantic (validation)
- PostgreSQL

## Boundaries

### ✅ Allowed
- Domain service implementation
- Database models and migrations
- Business logic and policy enforcement
- External API integrations
- Import from `packages/contracts`

### ❌ Forbidden
- UI rendering or HTML serving
- Frontend-specific concerns
- Direct imports from `apps/web`

## API Design Principles
- API-first: Define OpenAPI schema before implementation
- Contract-driven: All endpoints validated against `packages/contracts`
- Version all breaking changes: `/api/v1/...`
- Include request/response schemas for all endpoints

## Development
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run dev server
uvicorn main:app --reload

# Run tests
pytest

# Run migrations
alembic upgrade head
```

## Key Endpoints
TBD - will be populated as features are implemented

## Related Docs
- ADR-0001: Repository Boundaries
- ADR-0002: Service Boundaries
- WORKSPACE-MAP.md
