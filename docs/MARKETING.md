# PeerForge — Marketing Document

---

## The one-liner

**Face the panel before the panel faces you.**

PeerForge runs a real peer-review session against your research — several
reviewers, distinct remits, arguing about your work in front of you — and
hands you the transcript, the questions you will be asked, and a signed
readiness certificate.

---

## The problem

Serious feedback on research arrives too late and too rarely.

A PhD student waits weeks for supervisor comments and months for reviewer
reports. By the time the criticism lands, the study is finished, the data are
collected, the design cannot be changed. The single most useful sentence a
reviewer will write — *"you cannot claim causation with this allocation
procedure"* — arrives after the thing that would have fixed it is out of
reach.

Meanwhile supervisors are stretched, examiners see the work once, and the
gap between "I think this is ready" and "the panel thinks this is ready" is
where most viva failures and desk rejections live.

The obvious response — asking a general-purpose AI to review your paper —
produces a paragraph of encouragement, three vague suggestions, and a
confident reference to a page that does not exist.

---

## What PeerForge does instead

It runs a **panel**, not an assistant.

Each reviewer has a remit and stays in it. The methodologist interrogates
allocation and power. The domain expert argues about construct validity and
related work. The external examiner decides whether the thing is publishable
and says what must change. They read your document, research the literature,
prepare privately, then disagree with each other in front of you.

Then it does the part nobody else does: **it checks itself.**

---

## Why this is hard, and why that matters

Point five language models at one short paper and they converge. Within two
rounds you have one reviewer's opinion restated five times in different
words, everyone politely agreeing, and — reliably — citations to "Section
2.3, page 12" of a document that has no Section 2.3 and no page numbers.

That is the actual engineering problem, and PeerForge is built around it:

**Eleven integrity rules run on every turn.** Repetition, deference,
self-contradiction, drifting out of role, generic filler that any reviewer
could have written. Ten of them force the turn to be regenerated. The retry
is then re-checked — because a retry that fixes one problem and introduces
another is still a failure.

**Citations are verified against the document.** If you uploaded nothing,
every page reference is fabrication by definition and is stripped. If you did
upload something, cited sections are checked against what the document
actually contains — a reviewer citing Section 9 of a four-section paper is
caught, while a legitimate citation to Section 2.1 passes untouched. External
literature a reviewer genuinely knows is never flagged.

**Quality is measured, not asserted.** Every transcript is scored for how
much reviewers restate each other and how often they open by deferring rather
than leading. Both gate.

The honest test: with three reviewers explicitly instructed to cite pages,
sections, tables and figures in every paragraph of a session with no document
at all — **zero fabricated citations reached the transcript**.

---

## What you get

| | |
|---|---|
| **A transcript** | The argument as it happened, reviewer by reviewer |
| **A summary** | Grounded in the real transcript; it refuses to summarise a session that did not happen |
| **15 defence questions** | Viva-style, each tied to the excerpt from *your* document that prompted it |
| **A readiness assessment** | Ten scored dimensions, with a stated basis for what it had to work with |
| **A signed certificate** | Publicly verifiable, bound by hash to the evidence it rested on |

---

## Who it is for

**Doctoral candidates preparing for a viva.** Rehearse the defence. Find out
which three questions you cannot answer while there is still time to answer
them.

**Researchers before submission.** Get the desk-reject reasons before the
desk rejects you.

**Supervisors and departments.** Give every student a panel, not just the
ones who ask. Track cohort readiness across a course.

**Institutions.** Courses, roles, seats and invitations are built in. A
department runs its own space; professors run their courses; students see
their own sessions.

---

## What makes it defensible

Most AI review tools are a prompt. This is a system.

- **A three-stage pipeline per turn** — private reasoning, then the visible
  response, then validation — so a reviewer decides what is *uniquely theirs*
  to say before saying it.
- **Preparation before speaking.** Each reviewer produces a private memo
  first: what the work claims, the biggest gap, the hardest questions they
  intend to ask, and the outside literature they consulted. Measured: 3 of 5
  retrieved sources cited in every memo.
- **Cryptographic assurance.** The certificate's identifier *is* a hash of
  the scores and evidence. Change the evidence and it does not verify as
  current — it verifies as `SUPERSEDED`, which is a different and more honest
  statement than "invalid".
- **Provenance.** Which chunk of your document a claim rests on, with the
  chunk's sha256 re-verified at citation time.

---

## The honesty policy

We publish what does not work, in the product documentation, with numbers.

- Page citations are not verified, because 391 of 398 chunks in a real
  database carry no page number and checking pages would reject legitimate
  citations.
- Reviewer differentiation still degrades by the second round on short papers
  with few distinct flaws. The quality gates catch it; the fix is partial.
- Prep packs cite three of five retrieved sources, not all five — forcing all
  five in produces padding rather than argument.

A tool that tells you it is uncertain is worth more than one that is
confidently wrong. That principle runs through the product: when the panel
has no document, it says so and refuses to invent one; when a certificate is
stale, it says stale rather than forged; when web research is unavailable, it
names the reason instead of inventing a setting for you to toggle.

---

## Proof points

| Claim | Measurement |
|---|---|
| Fabricated citations blocked | 33 fabricated locators across 18 turns → **0**, under adversarial prompting |
| Contradicted citations blocked | 11 reaching the transcript → **0**, legitimate citations preserved |
| Panel convergence caught | Restatement 1.00 → **0.20**; opener templates 0.80 → **0.00** |
| Sources actually used | Prep pack citations 0 of 5 → **3 of 5**, in 9 of 9 memos |
| Engineering rigour | 440 backend tests · 121 API operations · 39 tables |

---

## Positioning

|  | General AI assistant | Human peer review | **PeerForge** |
|---|---|---|---|
| Turnaround | Seconds | Weeks to months | Minutes |
| Multiple perspectives | One voice | Yes | Yes, with enforced separation |
| Cites your document | Sometimes, often wrongly | Yes | Verified against the document |
| Fabrication risk | High | None | Detected and stripped |
| Rehearsable | No | No | Yes, unlimited |
| Auditable output | No | Reviewer reports | Signed, hash-bound certificate |

We are not a replacement for peer review. We are the rehearsal before it —
and the thing that catches the errors reviewers would have spent their
attention on, so they can spend it on the science instead.

---

## Try it

The demo institution — Northgate University — carries four courses and ten
review sessions across genuinely different fields: mindfulness trials, CRISPR
off-target effects, clinical retrieval-augmented generation, minimum-wage
econometrics, peer instruction, wearable sepsis detection, urban tree canopy,
remote-work loneliness, microplastic photocatalysis, hedging detection.

Every paper has real methodological flaws planted in it — unconcealed
allocation, missing active controls, thresholds tuned on the reported data,
train/test leakage. Watch whether the panel finds them.
