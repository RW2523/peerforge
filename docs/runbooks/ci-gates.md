# CI Quality Gates Runbook

## Purpose
This runbook explains each CI quality gate, common failure scenarios, and how to fix them.

## Quick Reference

Run all gates locally before pushing:
```bash
make verify
```

Individual gates:
```bash
make lint          # Linting and format checks
make typecheck     # Type validation
make test          # Contract tests (packages/contracts)
make api-test      # API tests (apps/api)
```

**Note:** `make verify` runs all gates including `api-test`. If API tests fail, the entire verification fails.

## Quality Gates

---

### 1. File Size Limits

**Gate**: `check_file_sizes.sh`

**Purpose**: Enforce file size constraints to prevent "god files" and maintain readability.

**Limits**:
- UI components (`.tsx`, `.jsx`): **300 lines max**
- Service files (`*_service.py`, `*Service.ts`): **400 lines max**
- Route/controller files (`*_routes.py`, `*.routes.ts`): **500 lines max**

**Exception**: Generated files in `*/generated/*` paths are excluded.

#### Common Failures

**Problem**: File exceeds size limit
```
❌ apps/web/components/Dashboard.tsx: 350 lines (max 300)
```

**Fix**:
1. **Extract components**: Break large components into smaller, focused ones
   ```typescript
   // Before: 350 lines
   Dashboard.tsx
   
   // After: Multiple smaller files
   Dashboard.tsx           (100 lines - composition)
   DashboardHeader.tsx     (80 lines)
   DashboardMetrics.tsx    (90 lines)
   DashboardCharts.tsx     (80 lines)
   ```

2. **Extract logic to hooks**: Move complex logic to custom hooks
   ```typescript
   // Before: Logic mixed in component
   export function Dashboard() {
     // 200 lines of state and logic
     // 150 lines of rendering
   }
   
   // After: Logic in hook
   export function useDashboardData() {
     // State and logic here
   }
   
   export function Dashboard() {
     const data = useDashboardData();
     // Only rendering logic
   }
   ```

3. **Split services**: Break large services into focused domain services
   ```python
   # Before: user_service.py (500 lines)
   
   # After:
   user_service.py         (200 lines - core CRUD)
   user_auth_service.py    (150 lines - authentication)
   user_profile_service.py (150 lines - profile management)
   ```

**Prevention**: Design components/services with single responsibility principle.

---

### 2. Duplicate Detection

**Gate**: `check_duplicates.sh`

**Purpose**: Prevent code duplication and maintain DRY (Don't Repeat Yourself) principle.

**Checks**:
- Duplicate API endpoint definitions
- Suspicious file patterns (`*_v2.py`, `temp_*.py`, `copy_of_*`)
- Duplicate exported symbols across modules
- Duplicate FastAPI route decorators

#### Common Failures

**Problem**: Duplicate API endpoint
```
❌ Found duplicate API paths in OpenAPI spec:
    /debates:
```

**Fix**: Consolidate duplicate endpoints into a single definition
```yaml
# Bad: Duplicate path
paths:
  /debates:
    post: ...
  /debates:  # Duplicate!
    get: ...

# Good: Single path with multiple methods
paths:
  /debates:
    get: ...
    post: ...
```

**Problem**: Suspicious file pattern
```
❌ Found suspicious duplicate file pattern: *_service2.py
    apps/api/services/user_service2.py
```

**Fix**: Remove the duplicate and extend the original
```python
# Instead of creating user_service2.py, extend user_service.py
# Or refactor into focused services with clear names
```

**Problem**: Duplicate route definitions
```
❌ Found duplicate route definitions:
    2 post "/debates"
```

**Fix**: Remove duplicate route decorators
```python
# Bad: Duplicate routes
@router.post("/debates")
async def create_debate_v1(): ...

@router.post("/debates")  # Duplicate!
async def create_debate_v2(): ...

# Good: Single route
@router.post("/debates")
async def create_debate(): ...
```

**Prevention**:
- Search for existing endpoints before adding new ones: `rg "@router.post" apps/api`
- Use clear, descriptive names without version suffixes
- Follow naming conventions from engineering standards

---

### 3. Forbidden Patterns

**Gate**: `check_forbidden_patterns.sh`

**Purpose**: Enforce coding standards, security practices, and architectural policies.

**Checks**:
- Direct provider SDK usage (OpenRouter policy)
- Hardcoded secrets
- Temporary hacks without issue links
- Silent error handling
- Undocumented environment variables

#### Common Failures

**Problem**: Direct OpenAI SDK usage
```
❌ Found direct OpenAI SDK imports (use OpenRouter instead):
    apps/api/services/llm_service.py:3: from openai import OpenAI
```

**Fix**: Use OpenRouter gateway instead
```python
# Bad: Direct OpenAI SDK
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Good: OpenRouter gateway
import requests

def call_llm(prompt: str, model: str) -> str:
    """Call LLM via OpenRouter gateway"""
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
            "HTTP-Referer": os.getenv("SITE_URL"),
        },
        json={
            "model": model,  # e.g., "openai/gpt-4"
            "messages": [{"role": "user", "content": prompt}]
        }
    )
    return response.json()["choices"][0]["message"]["content"]
```

**Problem**: Hardcoded secret
```
❌ Found potential hardcoded secret:
    apps/api/config.py:5: OPENAI_API_KEY = "sk-abc123xyz"
```

**Fix**: Use environment variables
```python
# Bad: Hardcoded
OPENAI_API_KEY = "sk-abc123xyz"

# Good: Environment variable
import os
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY must be set")
```

**Problem**: TODO without issue reference
```
⚠️  Found TODO/FIXME/HACK without issue reference:
    apps/api/services/user_service.py:42: # TODO: Add validation
```

**Fix**: Link to issue or remove
```python
# Bad: Untracked TODO
# TODO: Add validation

# Good: Linked to issue
# TODO(#123): Add email validation for user registration

# Better: Just do it now if it's small
def validate_email(email: str) -> bool:
    return "@" in email and "." in email
```

**Problem**: Bare except clause
```
❌ Found bare except clauses (silent error handling):
    apps/api/routes/debate_routes.py:25: except:
```

**Fix**: Catch specific exceptions and log
```python
# Bad: Silent failure
try:
    result = some_operation()
except:
    pass  # Error swallowed!

# Good: Specific exception with logging
import logging
logger = logging.getLogger(__name__)

try:
    result = some_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    raise
```

**Problem**: Empty catch block
```
❌ Found empty catch blocks:
    apps/web/utils/api.ts:15: catch(error) {}
```

**Fix**: Handle or re-throw errors
```typescript
// Bad: Empty catch
try {
  await fetchData();
} catch(error) {}  // Silent failure!

// Good: Log and handle
try {
  await fetchData();
} catch(error) {
  console.error('Failed to fetch data:', error);
  throw error; // Or handle gracefully
}
```

**Prevention**:
- Always use OpenRouter gateway for LLM calls
- Store all secrets in environment variables
- Create GitHub issues for TODOs before committing
- Never swallow errors silently
- Document all environment variables in `.env.example`

---

### 4. Contract Validation

**Gate**: `validate:openapi` and `validate:schemas`

**Purpose**: Ensure API contracts are valid and consistent.

#### Common Failures

**Problem**: Invalid OpenAPI schema
```
❌ OpenAPI validation failed:
  #/paths/debates must have required property 'get'
```

**Fix**: Add missing required properties
```yaml
paths:
  /debates:
    get:  # Add missing method
      operationId: listDebates
      responses:
        '200':
          description: Success
    post:
      # ... existing definition
```

**Problem**: Invalid JSON Schema
```
❌ Event schema validation failed:
  agent-message.schema.json: Missing $schema property
```

**Fix**: Add required JSON Schema properties
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://arinar.com/schemas/events/agent-message.json",
  "title": "Agent Message Event",
  "type": "object"
}
```

**Prevention**:
- Validate contracts before committing: `npm run validate:all`
- Use schema validation in your editor/IDE
- Follow OpenAPI 3.1 specification

---

### 5. Type Generation Consistency

**Gate**: Contract drift check in CI

**Purpose**: Ensure generated types stay in sync with API contracts.

#### Common Failures

**Problem**: Generated types out of sync
```
❌ Generated types are out of sync with OpenAPI spec
```

**Fix**: Regenerate types
```bash
cd packages/contracts
npm run generate:types
git add src/generated/api-types.ts
git commit -m "Update generated types"
```

**Problem**: Types generation fails
```
❌ Type generation failed:
  Error parsing OpenAPI spec
```

**Fix**: Validate and fix OpenAPI spec first
```bash
npm run validate:openapi  # Fix any errors
npm run generate:types    # Then regenerate
```

**Prevention**:
- Run `npm run build` in contracts package before committing
- Add pre-commit hook to regenerate types
- Include generated files in version control

---

### 6. Test Suite

**Gate**: `npm test` in contracts package

**Purpose**: Ensure all contract tests pass.

#### Common Failures

**Problem**: Test assertion failure
```
❌ OpenAPI documentation references OpenRouter policy
  AssertionError: OpenAPI should reference OpenRouter
```

**Fix**: Update OpenAPI spec to mention policy
```yaml
info:
  description: |
    Arinar V2 API - AI-native knowledge platform.
    
    **Model Provider Policy**: This system uses OpenRouter for LLM access,
    not direct OpenAI/Anthropic integrations.
```

**Problem**: Schema validation test failure
```
❌ Event schemas include all required event types
  Missing event type: voice_transcript_final
```

**Fix**: Add missing event schema
```bash
# Create the missing schema file
touch packages/contracts/schemas/events/voice-transcript-final.schema.json
# Follow the schema structure from other event types
```

**Prevention**:
- Run tests locally before pushing: `make test`
- Add tests for new features
- Keep test data in sync with schemas

---

## CI Workflow

### Local Development

1. **Before starting work**:
   ```bash
   make install
   ```

2. **During development**:
   ```bash
   # Run specific checks
   make lint
   make typecheck
   make test
   ```

3. **Before committing**:
   ```bash
   make verify  # Runs all gates
   ```

4. **If gates fail**:
   - Read the error message carefully
   - Refer to this runbook for common fixes
   - Fix the issue and re-run `make verify`

### Pull Request Process

1. **Create PR**: Push your branch and open a pull request
2. **CI runs automatically**: All gates run on GitHub Actions
3. **Review results**: Check the Actions tab for detailed logs
4. **Fix failures**: If any gate fails, fix locally and push again
5. **Merge**: Only merge when all gates pass

### CI Job Structure

The CI workflow runs 4 parallel jobs:

1. **Lint & Type Checks**
   - OpenAPI validation
   - Schema validation
   - Type generation
   - Contract drift detection

2. **Tests**
   - Contract test suite
   - Coverage reporting

3. **Quality Gates**
   - File size checks
   - Duplicate detection
   - Forbidden pattern scanning
   - OpenRouter policy verification

4. **Summary**
   - Aggregates results
   - Reports overall status

---

## Troubleshooting

### All Gates Failing

**Symptom**: Every gate fails with permission errors

**Fix**: Make scripts executable
```bash
chmod +x scripts/*.sh
git add scripts/
git commit -m "Make scripts executable"
```

### Scripts Not Found

**Symptom**: `scripts/check_*.sh: No such file or directory`

**Fix**: Run from repository root
```bash
cd arinar-v2/
make verify
```

### npm ci Fails

**Symptom**: `npm ci` fails in CI

**Fix**: Ensure `package-lock.json` is committed
```bash
cd packages/contracts
npm install  # Generates package-lock.json
git add package-lock.json
git commit -m "Add package-lock.json"
```

### False Positives

**Symptom**: Gate flags valid code as violation

**Fix**: Add exception comment
```python
from openai import OpenAI  # OpenRouter gateway wrapper
```

Or adjust the pattern in the check script.

---

## Maintenance

### Adding New Checks

1. Create new script in `scripts/`
2. Add to `make verify` target in Makefile
3. Add to `.github/workflows/ci.yml`
4. Document in this runbook

### Modifying Limits

File size limits are defined in:
- `scripts/check_file_sizes.sh` (local)
- Engineering standards doc (reference)

Update both when changing limits.

### Disabling a Gate

**Not recommended**, but if necessary:

1. Comment out in Makefile temporarily
2. Create issue to re-enable
3. Document reason in commit message

---

## Resources

- [Engineering Standards](/Users/pv/Downloads/arinar-6-IPSS-V5/2026-goals-codex/15-engineering-standards-and-anti-chaos-rules.md)
- [Workspace Boundaries](../WORKSPACE-MAP.md)
- [ADR-0001: Repository Boundaries](../docs/architecture/ADR-0001-repo-boundaries.md)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

---

---

### 7. API Tests

**Gate**: `make api-test` (runs `pytest` in `apps/api/`)

**Purpose**: Validate API endpoints and core debate orchestration logic (M1 protection).

**What it tests**:
- `POST /debates/run` endpoint functionality
- 5-turn round-robin orchestration
- OpenRouter BYOK integration
- Database persistence
- Error handling (invalid keys, wrong agent counts)
- Turn order determinism

**Setup (first time)**:
```bash
# Python 3.8+ required
python3 --version

# Makefile handles venv creation automatically
make api-test
```

**Manual setup**:
```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

#### Common Failures

**Problem**: Python not found
```
❌ python3 not found. Install Python 3.8+ first.
```

**Fix**:
- **macOS**: `brew install python@3.11`
- **Ubuntu**: `sudo apt install python3 python3-venv python3-pip`
- **Windows**: Download from https://python.org

**Problem**: Import errors in tests
```
ModuleNotFoundError: No module named 'fastapi'
```

**Fix**:
```bash
cd apps/api
rm -rf .venv  # Clean slate
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

**Problem**: Test failures after API changes
```
FAILED tests/test_debate_run.py::test_debate_run_happy_path
```

**Fix**:
1. Review test file: `apps/api/tests/test_debate_run.py`
2. Update mocks if API behavior changed intentionally
3. Fix API implementation if test expectations are correct
4. Run single test for debugging:
   ```bash
   cd apps/api
   .venv/bin/pytest tests/test_debate_run.py::test_debate_run_happy_path -v
   ```

**Prevention**: Run `make api-test` before every commit touching `apps/api/`.

---

## Quick Fixes Cheatsheet

| Gate | Common Fix |
|------|-----------|
| File size | Extract components/services into smaller modules |
| Duplicates | Remove duplicate files, consolidate endpoints |
| OpenRouter policy | Use OpenRouter gateway, not direct SDK |
| Hardcoded secrets | Move to environment variables |
| TODO without issue | Create issue and link or remove |
| Silent errors | Add logging and specific exception handling |
| Contract drift | Run `npm run generate:types` |
| Test failures | Update schemas/specs to match requirements |

---

**Last Updated**: 2026-02-05  
**Maintained By**: Platform Team
