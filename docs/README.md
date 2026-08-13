# PeerForge Documentation

| Document | For | What it covers |
|---|---|---|
| [USER_MANUAL.md](USER_MANUAL.md) | Users, QA, evaluators | How to run a review session, and how to test that the system works — including adversarial checks |
| [FEATURES.md](FEATURES.md) | Product, sales, evaluation | Every capability, its state, and what is deliberately not built |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Engineers | Stack, data model, the three-stage pipeline, end-to-end data flow, security posture |
| [MARKETING.md](MARKETING.md) | Marketing, positioning | The problem, the differentiator, proof points, competitive framing |
| [PITCH_DECK.md](PITCH_DECK.md) | Fundraising, partnerships | 14 slides with speaker notes |

## A note on the numbers

Every figure in these documents was measured against a running instance on
2026-08-05 — endpoint counts from the live OpenAPI schema, table counts from
the database, test counts from a real run, and quality figures from actual
transcripts.

Two exceptions are marked in place:

- **Market sizing in the pitch deck** is a placeholder. Source it before
  presenting.
- **Known limitations** are stated in every document rather than omitted.
  `ARCHITECTURE.md §9` and `FEATURES.md §9` list them with numbers.

## Reproducing the measurements

```bash
# API surface
curl -s http://localhost:8000/openapi.json | python3 -c "
import sys,json; d=json.load(sys.stdin)['paths']
print(len(d), 'paths', sum(1 for p in d for m in d[p] if m in ('get','post','patch','put','delete')), 'operations')"

# tests
cd apps/api && source venv/bin/activate && python -m pytest tests/ -q

# key gates
cd apps/web && node scripts/check-key-gates.js
```

> ⚠️ The backend test suite writes to the same database as the application.
> Run it **before** seeding demo data, not after.
