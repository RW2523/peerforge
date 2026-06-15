# ADR-0001: Repository Boundaries and Monorepo Structure

## Status
Accepted

## Context
As we rebuild Arinar V2, we need a clear organizational structure that:
- Prevents codebase drift and chaos
- Supports multiple AI coding agents working in parallel
- Enforces strict separation of concerns
- Enables independent deployment of services
- Maintains clear ownership and responsibilities

## Decision
We adopt a monorepo structure with strict folder boundaries:

### Top-Level Structure
```
arinar-v2/
├── apps/          # Deployable applications
├── packages/      # Shared libraries and contracts
├── infra/         # Infrastructure as code
├── tests/         # Cross-cutting test suites
└── docs/          # Architecture and operational docs
```

### Apps Folder (`apps/`)
Contains independently deployable applications:

- `apps/web/`: Next.js application
  - **Responsibility**: UI rendering, client-side logic, BFF (Backend-for-Frontend) endpoints only
  - **Allowed**: React components, Next.js API routes for UI state, client utilities
  - **Forbidden**: Direct database access, business logic, policy enforcement

- `apps/api/`: FastAPI application
  - **Responsibility**: Domain APIs, orchestration, business logic, policy enforcement
  - **Allowed**: Domain services, database access, orchestration logic
  - **Forbidden**: UI rendering, frontend-specific logic

- `apps/workers/`: Background processing
  - **Responsibility**: Async jobs, data ingestion, scheduled tasks
  - **Allowed**: Temporal workers, background job handlers, batch processing
  - **Forbidden**: Synchronous HTTP endpoints, UI logic

### Packages Folder (`packages/`)
Contains shared, reusable libraries:

- `packages/contracts/`: Type definitions and API schemas
  - **Purpose**: Single source of truth for types shared across apps
  - **Contents**: OpenAPI specs, JSON schemas, TypeScript types, Python types

- `packages/ui/`: Reusable UI components
  - **Purpose**: Consistent design system across frontend
  - **Contents**: React components, design tokens, styling utilities

- `packages/prompts/`: AI prompt management
  - **Purpose**: Centralized prompt templates and utilities
  - **Contents**: Prompt templates, compilation utilities, versioning

- `packages/tooling/`: Development tooling
  - **Purpose**: Shared dev scripts, linting, testing utilities
  - **Contents**: Build scripts, lint configs, test helpers

### Infrastructure Folder (`infra/`)
- `infra/migrations/`: Database migrations
- `infra/docker/`: Local development infrastructure configs

### Tests Folder (`tests/`)
- `tests/e2e/`: End-to-end tests spanning multiple services
- `tests/integration/`: Cross-service integration tests

## Consequences

### Positive
- Clear ownership and responsibility for each folder
- Prevents "god services" that do everything
- Enables parallel development by multiple teams/agents
- Simplifies deployment and scaling strategies
- Enforces API-first development through contracts package
- Reduces merge conflicts through clear boundaries

### Negative
- Requires discipline to respect boundaries
- May require refactoring if boundaries are violated
- Additional overhead in defining contracts upfront

## Enforcement

### CI Checks
- Lint rules to prevent forbidden imports
- Dependency graph validation
- File size limits per module type

### Documentation
- `WORKSPACE-MAP.md` provides detailed import rules
- Each app/package includes README with boundaries
- Engineering standards doc mandates boundary respect

### Code Review
- PRs that violate boundaries must be rejected
- Cross-boundary changes require architectural review

## Related
- ADR-0002: Service Boundaries and Communication Patterns
- Engineering Standards: `/2026-goals-codex/15-engineering-standards-and-anti-chaos-rules.md`
