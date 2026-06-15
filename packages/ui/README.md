# packages/ui - Shared UI Components

## Purpose
Reusable React components and design system shared across frontend applications.

## Ownership
**Team**: Frontend
**Primary Contact**: TBD

## Responsibilities
- Reusable React components
- Design tokens (colors, spacing, typography)
- Component documentation
- Accessibility standards
- Theming utilities

## Technology Stack
- React 18+
- TypeScript
- Tailwind CSS (or design system TBD)
- Storybook (documentation)

## Structure
```
ui/
├── components/       # React components
│   ├── Button/
│   ├── Input/
│   └── ...
├── tokens/          # Design tokens
├── hooks/           # Shared React hooks
├── utils/           # UI utilities
└── styles/          # Global styles
```

## Boundaries

### ✅ Allowed
- Presentational React components
- Design tokens and theming
- UI-focused hooks and utilities
- Styling primitives

### ❌ Forbidden
- Business logic
- API calls or data fetching
- Application-specific state management
- Direct database access

## Component Guidelines
- All components must be fully typed
- Include Storybook stories for documentation
- Follow accessibility best practices (WCAG 2.1 AA)
- Keep components small and focused
- Maximum 300 lines per component file

## Usage

### From apps/web
```typescript
import { Button, Input, Card } from '@arinar/ui';

export function MyComponent() {
  return (
    <Card>
      <Input placeholder="Enter text" />
      <Button>Submit</Button>
    </Card>
  );
}
```

## Development
```bash
# Install dependencies
pnpm install

# Run Storybook
pnpm storybook

# Build components
pnpm build

# Run tests
pnpm test
```

## Design Principles
- Mobile-first responsive design
- Consistent spacing and typography
- Dark mode support
- Performance-optimized

## Related Docs
- Design system documentation (TBD)
- WORKSPACE-MAP.md
