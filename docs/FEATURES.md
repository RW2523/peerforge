# PeerForge — Features and Functionality

**Verified against a running instance, 2026-08-05.** Anything marked
*Partial* or *Known limit* is stated as such rather than rounded up.

---

## At a glance

| | |
|---|---|
| API surface | 107 paths, 121 operations |
| Data model | 39 tables, 11 migrations |
| Backend tests | 440 passing, 35 files |
| Reviewer lanes | 6 distinct roles |
| Integrity rules | 11 (10 enforcing, 1 advisory) |
| Frontend routes | 12 |

---

## 1. Institution, courses and people

A three-level hierarchy: **institution → course → session**.

| Feature | What it does | State |
|---|---|---|
| Organisations | An institution with a name, slug and seat plan | ✅ |
| Courses (workspaces) | Each course is its own workspace with its own sessions | ✅ |
| Roles | `org_admin`, `professor`, `ta`, `student` at institution level; the same vocabulary per course | ✅ |
| Seats | Purchased vs used, with only `student` billable; pending invitations reserve a seat at invitation time, not on acceptance | ✅ |
| Invitations | Single and bulk, email-delivered, token-accepted, revocable | ✅ |
| Cohort view | Per-course roster with progress, scoped to that course | ✅ |
| Last-admin guard | An organisation cannot be left without an admin, including via invitation acceptance | ✅ |

**Authorization.** Every debate-scoped request resolves the debate's
workspace and checks membership across *all* of the caller's workspaces. A
professor teaching four courses reaches sessions in all four, not just the
one currently selected.

---

## 2. Getting a session ready

| Feature | What it does | State |
|---|---|---|
| Document upload | PDF, DOCX, TXT and more; MIME validated before anything is written | ✅ |
| All-or-nothing uploads | A batch is validated in full before existing files are touched — an invalid file changes nothing | ✅ |
| Text extraction + OCR | Scanned documents are OCR'd | ✅ |
| Chunking | Paragraph-aware, 1000 chars with 200 overlap, sha256 per chunk | ✅ |
| Embedding | `text-embedding-3-small`, 1536 dimensions, into pgvector | ✅ |
| Conversational setup | Describe the panel you want in prose; the assistant proposes reviewers, roles and rounds, grounded in your uploaded document | ✅ |
| Manual panel building | Pick from 22 curated reviewer templates or define your own | ✅ |
| Action item extraction | Pulls actionable items from a transcript with priority and owner | ✅ |

**Conversational setup, concretely.** You type *"a statistician who won't let
a weak design pass, a clinical psychology expert, and an examiner who decides
publishability — two rounds"* and get a named panel with distinct role lanes,
retrieved passages from your own document informing the proposal. Editable
before you apply it.

---

## 3. Preflight — reviewers prepare before they speak

Each reviewer produces a **private preparation memo** before the session
opens. This is the feature that most distinguishes PeerForge from a group
chat with personas.

| Step | What happens |
|---|---|
| Retrieve | Semantic search over the session's chunks, plus any context granted from prior sessions |
| Research | Live web search on the problem statement (Tavily, 5 sources) |
| Compose | A role-specific memo: what the work claims, the biggest gap, the hardest questions this reviewer intends to ask |
| Cite | A required **External literature consulted** section, each bullet tying a source to the critique with its URL |

**Measured:** 3 of 5 retrieved sources cited, in 9 of 9 memos. Before the
citation requirement was made a required output section rather than a
trailing rule, it was 0 of 5.

When no web-search key is configured, the panel says so plainly and the
prompt explicitly forbids inventing URLs to fill the gap.

---

## 4. The review session

| Feature | What it does | State |
|---|---|---|
| Three-stage turns | Private reasoning → visible response → constitutional validation | ✅ |
| Six reviewer lanes | advisor · methodology professor · domain expert · skeptical reviewer · friendly professor · external examiner | ✅ |
| Live transcript | WebSocket-driven, with agent thinking steps visible | ✅ |
| Manual advance | Next Turn, or Ctrl/Cmd+Enter | ✅ |
| Autonomous mode | The panel runs itself with a configurable delay; pause and resume | ✅ |
| Human intervention | Interject mid-session as the researcher or moderator | ✅ |
| Session controls | Start · Pause · Resume · +2 Rounds · End | ✅ |
| Cross-instance broadcast | Redis pub/sub, so more than one API instance stays consistent | ✅ |

---

## 5. Integrity — the part that is actually hard

Language models playing reviewers converge. They restate each other, defer to
each other, and cite documents that do not exist. PeerForge measures and
resists all three.

### Eleven rules, checked every turn

Ten force a constrained regeneration; one is advisory. The full table is in
[ARCHITECTURE.md](ARCHITECTURE.md#44-the-constitutional-rules).

### Citation integrity

| Situation | Behaviour |
|---|---|
| No document submitted | Any page or section reference is fabrication by definition — regenerate, and replace any survivor with `[source not provided]` |
| Document submitted | Cited sections and tables are checked against what the document *actually contains* |
| Section exists | Passes silently |
| Section absent, family present | Flagged — the document has sections 1–4, the reviewer cited 9 |
| No locators of that family at all | **Unverifiable, not fabricated** — extraction may have dropped the structure |
| External literature | `(McKay et al., 2018)` is never flagged; a reviewer may legitimately know it |

**Measured:** with three reviewers instructed to cite pages, sections, tables
and figures in every paragraph, **0 fabricated locators reached the
transcript**.

### Retry re-validation

A regenerated message is re-checked and gets at most one further attempt,
kept only if it clears more violations than it introduces. This exists
because the same class of bug appeared three times: a retry introducing
"Figure 3", a retry re-citing a missing section, and a retry opening with
deference — each time the rule worked and the output was wrong anyway.

---

## 6. Assurance and output

| Feature | What it does | State |
|---|---|---|
| Transcript | Complete, ordered, append-only | ✅ |
| Summary | Grounded in the real transcript; **refuses to run on an empty one** | ✅ |
| Research profile | Problem, claim, methodology, dataset, contribution, limitations, extracted from the materials | ✅ |
| Defence questions | 15 viva-style questions, each with a source excerpt from the document | ✅ |
| Answer evaluation | Submit answers; the assessment updates and records its basis | ✅ |
| Readiness assessment | 10 scored dimensions with a stated basis (`has_profile`, `has_summary`, `answer_count`, `message_count`) | ✅ |
| Signed certificate | sha256 over scores plus ordered evidence, signed; publicly verifiable | ✅ |
| Three-valued verification | `VALID` · `SUPERSEDED` · `INVALID` | ✅ |
| Glass-Box provenance | Which chunk a claim rests on, with sha256 re-verified | ✅ |
| Quality report | Restatement and opener-template rates, gated | ✅ |

**Why `SUPERSEDED` matters.** A certificate whose session has moved on is
*authentic but stale* — not a forgery. A two-valued verdict called it
`INVALID`, which is a different and much more serious accusation.

---

## 7. Interface

Twelve routes: `/` · `/setup` · `/setup/chat` · `/room` · `/history` ·
`/organization` · `/cohort` · `/progress` · `/settings` · `/operator` ·
`/onboarding` · `/invite` · `/verify/[id]` · `/architecture`.

| Aspect | State |
|---|---|
| Accessibility linting in CI | ✅ |
| Keyboard navigation and screen-reader labels | ✅ |
| Dark mode | ✅ |
| In-app messaging (no `alert()`) | ✅ |
| Never asks for an API key when the server holds one | ✅ enforced by a build-time check |

That last one is enforced, not merely intended: `scripts/check-key-gates.js`
fails the build if any generation gate depends on a browser-held key. It
binds the key to whatever name it is given and flags boolean use on either
side of `&&` and `||` — it was rewritten after an earlier version passed
while nine real gates existed.

---

## 8. Operations

| Feature | State |
|---|---|
| Structured logging with request correlation ids | ✅ |
| Database connection pooling | ✅ |
| Background workers on three queues | ✅ |
| Deployment readiness check | ✅ |
| Migration runner covering both migration directories | ✅ |
| CORS allowlist | ✅ |
| Fail-fast on a placeholder JWT secret when auth is on | ✅ |

---

## 9. Known limits

| Limit | Detail |
|---|---|
| Page citations are not verified | 391 of 398 live chunks carry no `page_num`; checking pages would reject legitimate citations |
| Differentiation degrades by round two | On short papers with few distinct flaws. The gates catch it; the fix is partial |
| Prep packs cite 3 of 5 sources | Capped deliberately at two or three bullets — forcing all five produces padding |
| Tests share the demo database | The suite leaves fixtures behind; seed after testing |
| Tunnel URLs are ephemeral | The API URL is inlined at build time, so a new one needs a rebuild |

---

## 10. What is deliberately not built

- **No plagiarism detection.** Different problem, different tooling.
- **No reference-manager integration.** No Zotero or Mendeley sync.
- **No LMS integration.** No Canvas, Moodle or Blackboard connector.
- **No mobile app.** The web app is responsive; there is no native client.
- **No multi-language review.** Prompts and rules are English-only.
