# Arinar V2 Reports

## Purpose

This directory contains **report-only** documentation for tickets, demos, and milestones. All implementation details, command outputs, and verification evidence are recorded here, NOT in chat responses.

## Report-Only Discipline

### Chat Output Rule

When completing work, Cursor Agent outputs **ONLY**:

```
Report: /path/to/report.md
Status: PASS | FAIL | BLOCKED

Gates:
| Gate Item          | Status |
|--------------------|--------|
| Lint passes        | YES    |
| Tests pass         | YES    |
| Verify passes      | YES    |
| Build succeeds     | YES    |

Blockers: None / <specific blocker>
```

### Report File Rule

All details go into report files:
- **Tickets:** `reports/tickets/TICKET-XX-YYYY-MM-DD-vN.md`
- **Demos:** `reports/DEMO-XX-YYYY-MM-DD-vN.md`

Report files must include:
- Summary (ticket, date, author, status)
- What changed (files created/modified/deleted)
- Commands run (exact commands + outputs)
- Gate checklist (YES/NO table)
- Blockers (none or specific issues)
- Next steps

## Directory Structure

```
reports/
├── README.md                          # This file
├── tickets/
│   ├── TEMPLATE.md                    # Template for ticket reports
│   ├── INDEX.md                       # Ticket index (updated on PASS)
│   ├── TICKET-05-2026-02-05-v1.md    # M1 Debate-in-a-Box
│   ├── TICKET-05.1-2026-02-06-v1.md  # API Test Gates
│   └── TICKET-06-2026-02-06-v1.md    # M2 Realtime Controls
└── DEMO-01-2026-02-06-v1.md          # Full Stack Demo
```

## Report Naming

### Tickets
Format: `TICKET-XX-YYYY-MM-DD-vN.md`
- `XX` = Ticket number
- `YYYY-MM-DD` = Start date
- `vN` = Version (increment for major updates)

Example: `TICKET-06-2026-02-06-v1.md`

### Demos
Format: `DEMO-XX-YYYY-MM-DD-vN.md`
- `XX` = Demo sequence number
- `YYYY-MM-DD` = Demo date
- `vN` = Version

Example: `DEMO-01-2026-02-06-v1.md`

## Report Status Values

- **PASS** - All gates met, blockers resolved, ready for next phase
- **FAIL** - Critical gates failed, requires rework
- **BLOCKED** - External dependency or decision needed
- **IN PROGRESS** - Work ongoing (only during multi-phase tickets)

## Gate Checklist Standard

Every report must include a gate checklist with YES/NO status:

| Gate | Status | Evidence |
|------|--------|----------|
| Lint passes | YES/NO | Command output or file reference |
| Tests pass | YES/NO | Test suite results |
| Verify passes | YES/NO | `make verify` output |
| Build succeeds | YES/NO | Build command output |
| Contract valid | YES/NO | OpenAPI validation |

Additional gates may be added per ticket requirements.

## Index Maintenance

`tickets/INDEX.md` is updated **only** when a ticket reaches `PASS` status. This provides a canonical record of completed work.

## Best Practices

1. **One report per ticket** - Do not split tickets unless explicitly planned as phases
2. **Update existing reports** - For multi-phase tickets, keep updating the same file
3. **Evidence over narrative** - Include command outputs, not just descriptions
4. **Blockers are explicit** - State "None" or list specific issues, never "N/A"
5. **Chat stays minimal** - Detailed explanations belong in the report, not chat
6. **Version on major changes** - If reworking a ticket significantly, create v2

## Quality Standards

Reports must be:
- **Complete** - All sections filled, no "TODO" placeholders
- **Verifiable** - Commands can be re-run by anyone
- **Concise** - No redundant prose, focus on facts
- **Timestamped** - Commands show when they were run
- **Gated** - Clear YES/NO checklist, no ambiguity

## Example Workflow

1. Start ticket → Create `TICKET-XX-YYYY-MM-DD-v1.md`
2. Make changes → Update report with file list
3. Run commands → Paste exact commands + outputs into report
4. Check gates → Fill gate checklist with YES/NO
5. Resolve blockers → Document resolution in report
6. Mark PASS → Update `INDEX.md`, output minimal chat summary

## Anti-Patterns (Do Not Do)

❌ Long explanations in chat  
❌ Missing command outputs in reports  
❌ Vague gate status ("mostly works", "should be fine")  
❌ Updating INDEX.md before ticket is PASS  
❌ Creating new report for minor updates  
❌ Skipping blockers section  

## References

- [Engineering Standards](../2026-goals-codex/15-engineering-standards-and-anti-chaos-rules.md)
- [Milestone Gates](../2026-goals-codex/16-milestone-gates-and-evidence.md)
- [Decisions Log](../2026-goals-codex/17-decisions-log.md)
