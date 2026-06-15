# apps/workers - Background Job Processing

## Purpose
Background job execution, data ingestion, scheduled tasks, and async processing.

## Ownership
**Team**: Backend
**Primary Contact**: TBD

## Responsibilities
- Asynchronous job execution
- Data ingestion pipelines
- Scheduled batch tasks
- Long-running computations
- Background processing workflows

## Technology Stack
- Temporal (workflow orchestration) - planned
- Python 3.11+
- Celery (alternative consideration)
- Redis (job queue)

## Boundaries

### ✅ Allowed
- Background job handlers
- Async task processing
- Scheduled workflows
- Batch data processing
- Import from `packages/contracts`

### ❌ Forbidden
- Synchronous HTTP endpoints
- Real-time user request handling
- UI concerns
- Direct imports from `apps/web`

## Job Types
Planned categories:
- Data ingestion workflows
- Document processing pipelines
- Scheduled report generation
- Cleanup and maintenance tasks
- AI model inference (async)

## Development
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run worker
python -m workers.main

# Run tests
pytest
```

## Related Docs
- ADR-0001: Repository Boundaries
- ADR-0002: Service Boundaries
- WORKSPACE-MAP.md
