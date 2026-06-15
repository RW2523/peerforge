# ADR-0002: Service Boundaries and Communication Patterns

## Status
Accepted

## Context
With a hybrid architecture using Next.js (TypeScript) and FastAPI (Python), we need clear rules about:
- When to use Next.js vs Python services
- How services communicate
- Data flow and ownership
- API contract management

## Decision

### Service Responsibilities

#### Next.js App (`apps/web`)
**Primary Role**: UI layer and Backend-for-Frontend (BFF)

**Allowed Responsibilities**:
- Server-side rendering and client-side hydration
- UI state management
- Client-side routing
- BFF API routes that:
  - Aggregate data from multiple backend APIs
  - Transform backend data for UI consumption
  - Handle UI-specific session/auth state
  - Proxy requests with UI-specific error handling

**Forbidden Responsibilities**:
- Direct database writes
- Business logic implementation
- Policy enforcement
- Long-running computations
- Direct secret/key management

#### FastAPI App (`apps/api`)
**Primary Role**: Domain APIs and business logic

**Allowed Responsibilities**:
- CRUD operations on domain entities
- Business rule enforcement
- Policy evaluation and guardrails
- Data validation and transformation
- Orchestration of complex operations
- Direct database access
- Integration with external services

**Forbidden Responsibilities**:
- UI rendering or serving HTML
- Frontend-specific state management
- Direct user interface concerns

#### Workers (`apps/workers`)
**Primary Role**: Asynchronous processing

**Allowed Responsibilities**:
- Background job execution
- Data ingestion pipelines
- Scheduled tasks
- Long-running computations
- Batch processing

**Forbidden Responsibilities**:
- Synchronous request handling
- Real-time user interactions
- Direct UI concerns

### Communication Patterns

#### Frontend → Backend
```
User Browser → Next.js BFF → FastAPI → Database
            ↓
    Next.js Server Routes
```

- Frontend calls Next.js API routes (BFF)
- BFF routes aggregate/transform and call FastAPI domain APIs
- FastAPI performs business logic and returns structured data
- BFF transforms response for UI and returns to frontend

#### Service → Service
- Use HTTP/REST for synchronous communication
- Use message queues (future) for async events
- All APIs must be contract-first (OpenAPI/JSON Schema)

#### Shared Types
- All request/response types defined in `packages/contracts`
- Generate TypeScript types from OpenAPI specs
- Generate Python types from same specs
- Version all contracts explicitly

### Data Ownership

#### Database Access
- **Only** `apps/api` and `apps/workers` access the database directly
- `apps/web` **never** makes direct DB calls
- All data access goes through FastAPI domain APIs

#### Caching Strategy
- Frontend caching: React Query in `apps/web`
- API caching: Redis (future) in `apps/api`
- No cross-service cache invalidation initially

### API Contract Enforcement

#### Contract-First Development
1. Define OpenAPI schema in `packages/contracts`
2. Generate types for TypeScript and Python
3. Implement endpoint using generated types
4. Write tests that validate against schema

#### Versioning
- API versions in URL path: `/api/v1/...`
- Contracts package includes version history
- Breaking changes require new version

## Consequences

### Positive
- Clear separation prevents "spaghetti architecture"
- Frontend can work independently once contracts are defined
- Backend can evolve without breaking frontend
- Multiple teams/agents can work in parallel
- Type safety across language boundaries
- Easier to test in isolation

### Negative
- Initial overhead in defining contracts
- Potential over-fetching if BFF layer is not optimized
- Two-tier API structure may add latency

## Implementation Guidelines

### When to Use Next.js API Routes
✅ Aggregating multiple backend calls for a single UI view
✅ Transforming backend data shape for frontend convenience
✅ Handling UI-specific auth flows (OAuth callbacks)
✅ Rate limiting on a per-UI-user basis

❌ CRUD operations on domain entities
❌ Business logic or policy enforcement
❌ Direct database operations

### When to Use FastAPI
✅ All CRUD operations
✅ Business rule enforcement
✅ Policy guardrails and validation
✅ Data transformations for storage
✅ Integration with external domain services

❌ Serving HTML or frontend assets
❌ UI-specific data transformation

### When to Use Workers
✅ Long-running imports or processing
✅ Scheduled batch jobs
✅ Event-driven background tasks

❌ Anything that needs immediate user feedback
❌ Synchronous request-response patterns

## Enforcement

### CI/CD Checks
- Lint rules prevent direct DB imports in `apps/web`
- Contract validation in pipeline
- Type generation runs before build

### Code Review
- PR template includes boundary checklist
- Cross-boundary violations require architect approval

## Related
- ADR-0001: Repository Boundaries and Monorepo Structure
- WORKSPACE-MAP.md: Detailed import rules
