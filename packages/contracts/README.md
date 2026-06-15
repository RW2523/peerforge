# packages/contracts - API Contracts and Shared Types

## Purpose
Single source of truth for API contracts, schemas, and types shared across all applications.

## Ownership
**Team**: Platform
**Primary Contact**: TBD

## Responsibilities
- OpenAPI specifications for all APIs
- JSON schemas for data validation
- Type definitions (TypeScript and Python)
- API versioning and changelog
- Contract validation utilities

## Technology Stack
- OpenAPI 3.1
- JSON Schema
- TypeScript type generation
- Python Pydantic model generation

## Structure
```
contracts/
├── openapi/           # OpenAPI specifications
│   ├── v1/           # API version 1
│   └── v2/           # API version 2 (future)
├── schemas/          # Reusable JSON schemas
├── generated/        # Auto-generated types
│   ├── typescript/   # Generated TS types
│   └── python/       # Generated Python models
└── validators/       # Validation utilities
```

## Boundaries

### ✅ Allowed
- OpenAPI specs and JSON schemas
- Type generation scripts
- Validation utilities
- Schema migration tools

### ❌ Forbidden
- Business logic implementation
- Database access
- HTTP client/server code (except validators)

## Usage

### Adding a New Contract
1. Define OpenAPI spec in `openapi/v1/`
2. Run type generation: `pnpm generate:types`
3. Import generated types in apps

### From TypeScript (apps/web)
```typescript
import type { UserProfile, CreateUserRequest } from '@arinar/contracts';
```

### From Python (apps/api)
```python
from contracts.generated.python import UserProfile, CreateUserRequest
```

## Contract-First Workflow
1. Design API contract in OpenAPI format
2. Review contract with stakeholders
3. Generate types for all languages
4. Implement endpoints using generated types
5. Validate implementation against contract

## Development
```bash
# Generate types from OpenAPI specs
pnpm generate:types

# Validate contracts
pnpm validate:contracts

# Run contract tests
pnpm test
```

## Versioning
- Use semantic versioning for contracts
- Breaking changes require new API version
- Maintain compatibility matrices in docs

## Related Docs
- ADR-0002: Service Boundaries and Communication Patterns
- WORKSPACE-MAP.md
