# PeerForge — Pitch Deck

*Speaker notes in italics. Every figure is measured against a running
instance, 2026-08-05.*

---

## 1 · Title

# PeerForge
### Face the panel before the panel faces you

An AI peer-review panel that argues about your research — and checks its own
work.

*Open with the demo, not the slide. Upload a paper, run three turns, let them
watch reviewers disagree.*

---

## 2 · The problem

**Serious criticism arrives too late to act on.**

- A PhD student waits weeks for supervisor comments, months for reviewer
  reports.
- By then the design is fixed, the data collected, the flaw unfixable.
- The single most useful sentence — *"you cannot claim causation with this
  allocation procedure"* — lands after it is any use.

Supervisors are stretched. Examiners see the work once. The gap between
*"I think it's ready"* and *"the panel thinks it's ready"* is where viva
failures and desk rejections live.

---

## 3 · Why the obvious fix fails

Ask a general AI to review your paper and you get:

> "This is a well-structured study. Consider expanding the literature review.
> As noted in Section 2.3 on page 12, the sampling approach…"

The paper has no Section 2.3. It has no page 12.

*This is the slide that lands. Everyone in the room has seen this output.*

Point five models at one paper and it gets worse: within two rounds you have
one opinion restated five times, everyone agreeing, and confident citations
to nothing.

---

## 4 · What we built

**A panel, not an assistant.**

Each reviewer has a remit and stays in it:

- **Methodologist** — allocation, power, controls, validity threats
- **Domain expert** — construct validity, related work, novelty
- **External examiner** — is this publishable, and what must change

They read your document, research the literature, **prepare privately**, then
disagree with each other in front of you.

Then the part nobody else does: **it checks itself.**

---

## 5 · The hard part

**Eleven integrity rules, every turn.**

Repetition · deference · self-contradiction · role drift · generic filler ·
fabricated citations · contradicted citations · session meta-commentary

Ten force regeneration. The retry is **re-checked** — a retry that fixes one
problem and introduces another is still a failure.

**Citations are verified against the document.**

| Situation | What happens |
|---|---|
| No document uploaded | Every page reference is fabrication → stripped |
| Document uploaded | Cited sections checked against what it *actually contains* |
| Section 9 of a 4-section paper | Caught |
| Section 2.1 that genuinely exists | Passes untouched |
| `(McKay et al., 2018)` | Never flagged — a reviewer may know it |

---

## 6 · The proof

*This is the slide to slow down on.*

| | Before | After |
|---|---|---|
| Fabricated citations reaching the transcript | **33** across 18 turns | **0** |
| Contradicted citations | **11** | **0** |
| Panel restatement rate | **1.00** | **0.20** |
| Reviewers opening by deferring | **0.80** | **0.00** |
| Retrieved sources actually cited | **0 of 5** | **3 of 5** |

The fabrication test was **adversarial**: three reviewers explicitly
instructed to cite pages, sections, tables and figures in every paragraph, on
a session with no document at all. Zero got through.

---

## 7 · What the user gets

1. **Transcript** — the argument as it happened
2. **Summary** — grounded in the real transcript; refuses to summarise a
   session that did not happen
3. **15 defence questions** — each tied to the excerpt from *your* document
   that prompted it
4. **Readiness assessment** — ten scored dimensions with a stated basis
5. **Signed certificate** — publicly verifiable, hash-bound to its evidence

*Show a real certificate verifying. Then change the evidence and show it
report `SUPERSEDED` — authentic but stale, not forged.*

---

## 8 · Market

> ⚠️ **Sizing figures below are placeholders — source them before you present
> this.** Every other number in this deck was measured against a running
> instance; these were not, and an investor will check them.

**Primary — doctoral candidates.** A viva is a single high-stakes event with
almost no rehearsal available. *[Insert enrolment figures for your target
geographies.]*

**Secondary — researchers pre-submission.** Desk rejection is common at
selective journals, and much of it is for reasons a panel would name in ten
minutes. *[Insert desk-rejection rates for your target venues.]*

**Institutional — departments and graduate schools.** Courses, roles, seats
and invitations are built in. A department buys seats; professors run
courses; students see their own sessions.

*Land-and-expand: one supervisor's cohort, then the department, then the
graduate school.*

---

## 9 · Business model

**Institutional seats.** Priced per billable student seat; staff seats are
free. Seats are reserved at invitation time, so a department knows its
committed spend before anyone accepts.

Built and working today: organisations, courses, roles, bulk invitation,
seat accounting, cohort progress views.

---

## 10 · Why it is defensible

Most AI review tools are a prompt. This is a system.

- **Three-stage pipeline per turn** — private reasoning, visible response,
  validation — so a reviewer works out what is *uniquely theirs* to say
  before saying it
- **Preparation before speaking** — a private memo per reviewer, with the
  outside literature they consulted
- **Cryptographic assurance** — the certificate id *is* a hash of scores and
  ordered evidence
- **Provenance** — which chunk a claim rests on, sha256 re-verified

**Scale:** 121 API operations · 39 tables · 440 backend tests · ~53,000 lines.

*The moat is not the prompt. It is the eleven rules and the measurement
harness — each one written after observing a specific failure in real output,
not anticipated in advance.*

---

## 11 · What does not work yet

*Do not skip this slide. It is why the rest is credible.*

- **Page citations are not verified** — 391 of 398 chunks in a real database
  carry no page number; checking pages would reject legitimate citations
- **Differentiation still degrades by round two** on short papers with few
  distinct flaws. The gates catch it; the fix is partial
- **Prep packs cite 3 of 5 sources**, not all five — forcing all five in
  produces padding rather than argument

We publish these in the product documentation, with numbers. A tool that
tells you it is uncertain is worth more than one that is confidently wrong.

---

## 12 · Roadmap

**Now** — the review panel, integrity enforcement, assessment, certificates,
the institution tier.

**Next** — record document structure at ingest so page and section citations
can be verified fully. Reviewer differentiation beyond round two. LMS
integration.

**Later** — longitudinal readiness across a cohort. Reviewer calibration
against real examiner outcomes.

---

## 13 · The ask

*Fill in for your audience: capital, a pilot department, a design partner.*

**What we want from a pilot:** one supervisor, one cohort, one term. We
measure whether students who rehearse with a panel answer their examiners
better than students who do not.

---

## 14 · Close

> Every researcher eventually faces a panel that has read their work
> carefully and is not being kind about it.
>
> There is no reason that should be the first time.

**Try it:** ten sessions across ten fields, each paper carrying real planted
flaws — unconcealed allocation, missing controls, thresholds tuned on the
reported data, train/test leakage.

Watch whether the panel finds them.
