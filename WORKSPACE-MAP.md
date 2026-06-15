# Workspace Map and Import Boundaries

## Purpose
This document defines allowed and forbidden import patterns across the monorepo to maintain clean architecture and prevent circular dependencies.

## Visual Dependency Graph

```
┌─────────────────────────────────────────────────────┐
│                   apps/web                          │
│            (Next.js + BFF layer)                    │
│    ✓ Can import: contracts, ui, prompts            │
│    ✗ Cannot import: api, workers                   │
└──────────────┬──────────────────────────────────────┘
               │
               │ HTTP/REST
               ▼
┌─────────────────────────────────────────────────────┐
│                   apps/api                          │
│              (FastAPI backend)                      │
│    ✓ Can import: contracts, prompts                │
│    ✗ Cannot import: web, workers, ui               │
└──────────────┬──────────────────────────────────────┘
               │
               │ Job Queue
               ▼
┌─────────────────────────────────────────────────────┐
│                 apps/workers                        │
│           (Background processing)                   │
│    ✓ Can import: contracts, prompts                │
│    ✗ Cannot import: web, api, ui                   │
└─────────────────────────────────────────────────────┘

         ▲              ▲              ▲
         │              │              │
         └──────────────┴──────────────┘
                Shared Packages
    (contracts, ui, prompts, tooling)
```

## Detailed Import Rules

### apps/web (Next.js Frontend)

#### ✅ Allowed Imports
```typescript
// Packages
import { UserProfile } from '@arinar/contracts';
import { Button, Input } from '@arinar/ui';
import { getPrompt } from '@arinar/prompts';
import { formatDate } from '@arinar/tooling/utils';

// Internal (within apps/web)
import { Header } from '@/components/Header';
import { useAuth } from '@/hooks/useAuth';
```

#### ❌ Forbidden Imports
```typescript
// NEVER import from other apps
import { UserService } from '../../apps/api/services/user'; // ❌
import { processJob } from '../../apps/workers/jobs'; // ❌

// NEVER access database directly
import { prisma } from '@/lib/db'; // ❌
```

#### Communication Pattern
- Use HTTP calls to `apps/api` endpoints
- All backend communication through BFF API routes
- No direct service imports

---

### apps/api (FastAPI Backend)

#### ✅ Allowed Imports
```python
# Packages
from contracts.generated.python import UserProfile
from prompts import get_prompt, compile_prompt

# Internal (within apps/api)
from services.user_service import UserService
from models.user import User
```

#### ❌ Forbidden Imports
```python
# NEVER import from other apps
from apps.web.components import Header  # ❌
from apps.workers.jobs import process_data  # ❌

# NEVER import UI packages
from packages.ui import Button  # ❌
```

#### Communication Pattern
- Exposes REST APIs consumed by `apps/web`
- Enqueues jobs for `apps/workers` via job queue
- No direct imports from other apps

---

### apps/workers (Background Jobs)

#### ✅ Allowed Imports
```python
# Packages
from contracts.generated.python import JobPayload
from prompts import get_prompt

# Internal (within apps/workers)
from jobs.ingestion import IngestJob
from utils.logging import logger
```

#### ❌ Forbidden Imports
```python
# NEVER import from other apps
from apps.api.services import UserService  # ❌
from apps.web.utils import format_date  # ❌

# NEVER import UI packages
from packages.ui import Button  # ❌
```

#### Communication Pattern
- Consumes jobs from queue
- May call `apps/api` via HTTP if needed
- No direct imports from other apps

---

### packages/contracts

#### ✅ Allowed Imports
```typescript
// Standard libraries and dev dependencies only
import { z } from 'zod';
import type { OpenAPIV3 } from 'openapi-types';
```

#### ❌ Forbidden Imports
```typescript
// NEVER import from apps
import { something } from '../../apps/web'; // ❌

// NEVER import from other packages (keep contracts pure)
import { Button } from '../ui'; // ❌
```

#### Usage
- Imported by all apps
- Contains zero business logic
- Only types, schemas, and validators

---

### packages/ui

#### ✅ Allowed Imports
```typescript
// Standard libraries and peer dependencies
import React from 'react';
import { cn } from '@/lib/utils';

// Other UI utilities within the package
import { tokens } from './tokens';
```

#### ❌ Forbidden Imports
```typescript
// NEVER import from apps
import { UserService } from '../../apps/api'; // ❌

// NEVER import contracts or business logic
import { UserProfile } from '../contracts'; // ❌

// Keep UI pure - no business logic
```

#### Usage
- Only imported by `apps/web`
- Presentational components only
- No business logic or data fetching

---

### packages/prompts

#### ✅ Allowed Imports
```python
# Template engines and utilities
from jinja2 import Template
import json
```

```typescript
// TypeScript version
import Handlebars from 'handlebars';
```

#### ❌ Forbidden Imports
```python
# NEVER import from apps
from apps.api.services import UserService  # ❌

# NEVER include LLM client code
from openai import OpenAI  # ❌ (belongs in services)
```

#### Usage
- Imported by `apps/api` and `apps/workers`
- Template definitions only
- No LLM inference logic

---

### packages/tooling

#### ✅ Allowed Imports
```javascript
// Dev dependencies and utilities
const eslint = require('eslint');
const prettier = require('prettier');
```

#### ❌ Forbidden Imports
```javascript
// NEVER import from apps
const api = require('../../apps/api'); // ❌

// Keep tooling separate from runtime code
```

#### Usage
- Dev dependency only
- Not imported in production code
- Build and development scripts only

---

## Enforcement Strategies

### 1. Linting Rules
Configure ESLint/Ruff to prevent forbidden imports:

```json
// .eslintrc.js
{
  "rules": {
    "no-restricted-imports": [
      "error",
      {
        "patterns": [
          {
            "group": ["../../apps/*"],
            "message": "Cannot import from other apps. Use HTTP/REST APIs instead."
          }
        ]
      }
    ]
  }
}
```

### 2. CI Validation
```bash
# Check for boundary violations
./scripts/validate-boundaries.sh

# Example checks:
# - No imports from apps/api in apps/web
# - No database imports in apps/web
# - No UI imports in apps/api or apps/workers
```

### 3. Code Review Checklist
- [ ] Imports respect workspace boundaries
- [ ] No circular dependencies introduced
- [ ] Communication via defined interfaces (HTTP, job queue)
- [ ] Shared code moved to appropriate package

### 4. Architecture Tests
```typescript
// tests/architecture/boundaries.test.ts
describe('Workspace Boundaries', () => {
  it('apps/web should not import from apps/api', () => {
    // Test implementation
  });
  
  it('apps/api should not import UI components', () => {
    // Test implementation
  });
});
```

## Common Patterns

### Pattern 1: Sharing Code Between Apps
❌ **Wrong**: Direct import
```typescript
// apps/web/page.tsx
import { formatUser } from '../../apps/api/utils/format';
```

✅ **Correct**: Move to shared package
```typescript
// packages/tooling/utils/format.ts
export function formatUser(user) { ... }

// apps/web/page.tsx
import { formatUser } from '@arinar/tooling/utils';

// apps/api/routes.py
from tooling.utils import format_user
```

### Pattern 2: UI Components Needing Types
❌ **Wrong**: Business logic in UI
```typescript
// packages/ui/UserCard.tsx
import { UserProfile } from '@arinar/contracts';
import { fetchUser } from './api'; // ❌ no data fetching
```

✅ **Correct**: Pass data as props
```typescript
// packages/ui/UserCard.tsx
interface UserCardProps {
  name: string;
  email: string;
}
export function UserCard({ name, email }: UserCardProps) { ... }

// apps/web/components/UserCardContainer.tsx
import { UserCard } from '@arinar/ui';
const user = await fetchUser();
return <UserCard {...user} />;
```

### Pattern 3: Backend Business Logic
❌ **Wrong**: Logic in Next.js API route
```typescript
// apps/web/api/users/route.ts
export async function POST(req: Request) {
  const user = await db.users.create({ ... }); // ❌ DB access
  await sendEmail(user); // ❌ business logic
  return Response.json(user);
}
```

✅ **Correct**: Call FastAPI endpoint
```typescript
// apps/web/api/users/route.ts
export async function POST(req: Request) {
  const response = await fetch('http://api:8000/v1/users', {
    method: 'POST',
    body: JSON.stringify(await req.json()),
  });
  return Response.json(await response.json());
}

// apps/api/routes/user_routes.py
@router.post("/v1/users")
async def create_user(user: CreateUserRequest):
    user = user_service.create(user)
    await email_service.send_welcome(user)
    return user
```

## FAQ

### Q: Can apps/web call apps/api directly?
**A**: Only via HTTP/REST APIs, never direct imports.

### Q: Where should I put shared utilities?
**A**: 
- Type definitions → `packages/contracts`
- UI components → `packages/ui`
- Dev tools → `packages/tooling`
- Business logic → Keep in respective app

### Q: Can apps/api and apps/workers share code?
**A**: Only through `packages/*`. If code is truly shared, move it to a package.

### Q: What about database models?
**A**: Database models live in `apps/api` only. Workers access data via API calls if needed.

### Q: Can I create new packages?
**A**: Yes, but ensure they:
- Have clear, single responsibility
- Don't create circular dependencies
- Follow the same boundary rules
- Are documented in this file

## Related Documentation
- [ADR-0001: Repository Boundaries](./docs/architecture/ADR-0001-repo-boundaries.md)
- [ADR-0002: Service Boundaries](./docs/architecture/ADR-0002-service-boundaries.md)
- [Engineering Standards](/2026-goals-codex/15-engineering-standards-and-anti-chaos-rules.md)

## Updates
When modifying boundaries:
1. Update this document
2. Update relevant ADRs
3. Update lint rules
4. Notify team of changes
5. Update CI validation
