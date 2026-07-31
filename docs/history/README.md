# Historical notes

These files record how problems were investigated and fixed earlier in the
project's life. They are kept because that record has value — but they are
**not documentation of how the system works now**, and several describe code
that no longer exists.

Read them as a changelog, not a reference.

## Known to be superseded

| File | What it says | What is true now |
|---|---|---|
| `CONFLICT_TENSION_FIX.md` | A `_assign_debate_stance()` function assigns opposing stances | No such function exists anywhere in the codebase |
| `ACCOUNTABILITY_FIX.md` | Conduct rules live in `turn_orchestrator.py` | That prompt is built and then discarded on the default path; the live rule is one line in `agent_response_generator.py` |
| `ANTI_REPETITION_FIX.md` | A four-layer repetition guard, including a Stage-3 overlap check | The overlap check is unreachable — it returns before the comparison. Repetition was actually caused by a dictionary key that was never written (`description` vs `role_description`), fixed in the multi-tenancy work, and is now measured by `transcript_quality.py` rather than described in prose |
| `THINKING_*.md` (six files) | Six separate accounts of one feature | Superseded by the code and its tests |
| `PRE-LAUNCH-CHECKLIST.md`, `READY_TO_TEST.md` | Pre-launch readiness | Replaced by `GET /readiness`, which reports the real state at runtime, and by `GOING-LIVE.md` |

## Why they were moved

Thirteen of these were bug narratives written after finding a defect by hand.
That practice is what made the same defect recur: prose cannot fail a build.
The knowledge now lives in the test suite and in
`apps/api/src/services/transcript_quality.py`, which measures the specific
failure modes these documents describe.

If you are looking for how something works today, start with the root
`README.md` and `ARCHITECTURE.md`.
