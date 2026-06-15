# packages/prompts - AI Prompt Management

## Purpose
Centralized repository for AI prompt templates, versioning, and compilation utilities.

## Ownership
**Team**: AI/ML
**Primary Contact**: TBD

## Responsibilities
- Prompt template definitions
- Prompt versioning and changelog
- Template compilation and variable injection
- Prompt testing and validation utilities
- Performance tracking per prompt version

## Technology Stack
- Template engine (Jinja2 or similar)
- Python/TypeScript utilities
- Version control for prompts

## Structure
```
prompts/
├── templates/        # Prompt template files
│   ├── system/      # System prompts
│   ├── user/        # User prompts
│   └── examples/    # Few-shot examples
├── versions/        # Version history
├── compilers/       # Template compilation
└── validators/      # Prompt validation
```

## Boundaries

### ✅ Allowed
- Prompt template definitions
- Template compilation logic
- Variable injection utilities
- Prompt versioning tools

### ❌ Forbidden
- LLM inference execution (belongs in services)
- Business logic beyond prompts
- Direct API calls to LLM providers

## Usage

### From Python (apps/api)
```python
from prompts import get_prompt, compile_prompt

template = get_prompt('user_query_analysis', version='v1')
prompt = compile_prompt(template, context={'query': user_input})
```

### From TypeScript (apps/web)
```typescript
import { getPrompt, compilePrompt } from '@arinar/prompts';

const template = getPrompt('user_query_analysis', 'v1');
const prompt = compilePrompt(template, { query: userInput });
```

## Prompt Development Workflow
1. Define prompt template with variables
2. Test with sample inputs
3. Version and document changes
4. Deploy to staging for validation
5. Promote to production with A/B testing

## Versioning Strategy
- Semantic versioning for prompts
- Track performance metrics per version
- Maintain rollback capability
- Document prompt changes in changelog

## Development
```bash
# Validate prompts
pnpm validate:prompts

# Test prompt compilation
pnpm test

# Generate prompt documentation
pnpm docs
```

## Best Practices
- Keep prompts concise and focused
- Use clear variable names
- Document expected input/output formats
- Version prompts on any significant change
- Test with edge cases

## Related Docs
- Prompt engineering guidelines (TBD)
- WORKSPACE-MAP.md
