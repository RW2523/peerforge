# packages/tooling - Shared Development Tools

## Purpose
Shared development scripts, linting configurations, testing utilities, and build tools.

## Ownership
**Team**: Platform
**Primary Contact**: TBD

## Responsibilities
- Shared lint configurations (ESLint, Prettier, Ruff)
- Testing utilities and helpers
- Build scripts and automation
- Code generation tools
- Development workflow scripts

## Technology Stack
- ESLint, Prettier (JavaScript/TypeScript)
- Ruff, Black (Python)
- Custom scripts (Node.js, Python)
- Testing utilities

## Structure
```
tooling/
├── configs/          # Shared configurations
│   ├── eslint/
│   ├── prettier/
│   ├── typescript/
│   └── python/
├── scripts/          # Build and dev scripts
├── generators/       # Code generators
└── testing/          # Test utilities
```

## Boundaries

### ✅ Allowed
- Linting and formatting configs
- Build and development scripts
- Testing utilities
- Code generation tools

### ❌ Forbidden
- Application-specific business logic
- Runtime dependencies in production apps
- Database access or API calls

## Usage

### ESLint Config (apps/web)
```json
{
  "extends": ["@arinar/tooling/eslint-config"]
}
```

### Python Lint Config (apps/api)
```toml
[tool.ruff]
extend = "../../packages/tooling/configs/python/ruff.toml"
```

### Testing Utilities
```typescript
import { createMockUser, setupTestDb } from '@arinar/tooling/testing';
```

## Provided Configurations

### TypeScript/JavaScript
- ESLint rules for React and Node.js
- Prettier configuration
- TypeScript compiler options
- Import order rules

### Python
- Ruff configuration
- Black formatting rules
- pytest configurations
- Type checking rules (mypy)

## Scripts
- `generate:types` - Generate types from contracts
- `validate:all` - Run all validation checks
- `test:all` - Run all test suites
- `format:all` - Format entire codebase

## Development
```bash
# Install dependencies
pnpm install

# Test tooling scripts
pnpm test

# Validate configurations
pnpm validate
```

## Standards Enforcement
This package enforces:
- File naming conventions
- File size limits
- Import boundary rules
- Code style consistency

See `/2026-goals-codex/15-engineering-standards-and-anti-chaos-rules.md`

## Related Docs
- Engineering Standards
- WORKSPACE-MAP.md
