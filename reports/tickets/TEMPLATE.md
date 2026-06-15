# Ticket Report Template

## Summary
- **Ticket(s):** TICKET-XX
- **Date:** YYYY-MM-DD
- **Author:** Cursor Agent
- **Status:** `PASS` | `FAIL` | `BLOCKED`

## What Changed

### Files Created
- `path/to/new/file.ext` - Brief description

### Files Modified
- `path/to/modified/file.ext` - What changed

### Files Deleted
- `path/to/deleted/file.ext` - Why deleted

## Commands Run

```bash
# Command 1: Description
command --with --flags
# Exit code: 0
# Output: <key lines>

# Command 2: Description
another-command
# Exit code: 0
# Output: <key lines>
```

## Gate Checklist

| Gate | Status | Evidence |
|------|--------|----------|
| Lint passes | YES/NO | `make lint` output |
| Tests pass | YES/NO | `make api-test` output |
| Verify passes | YES/NO | `make verify` output |
| Build succeeds | YES/NO | `npm run build` output |
| Contract valid | YES/NO | OpenAPI validation output |

## Blockers

None / List specific blockers requiring resolution before PASS.

## Next Steps

1. Next action item
2. Follow-up ticket
3. Handoff to user/team
