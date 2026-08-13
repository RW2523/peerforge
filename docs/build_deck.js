// Build the PeerForge pitch deck (.pptx) from PITCH_DECK.md's content.
// Palette: Midnight Executive — navy dominant, ice-blue support, amber accent
// reserved for the numbers that matter. Motif: numbered navy discs.
const pptxgen = require("pptxgenjs");

const NAVY = "1E2761";
const NAVY_D = "141B44";
const ICE = "CADCFC";
const ICE_L = "EDF3FD";
const WHITE = "FFFFFF";
const INK = "1A1F2E";
const MUTED = "5B6470";
const AMBER = "C77D18";
const GREEN = "1E7A54";
const RED = "9E2B25";

const H = "Cambria";   // safe-list serif for headers
const B = "Calibri";   // safe-list sans for body

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";           // 13.3 x 7.5 — set BEFORE adding slides
pres.author = "PeerForge";
pres.title = "PeerForge — Pitch Deck";

const W = 13.3, PH = 7.5, M = 0.75;

// ── helpers ───────────────────────────────────────────────────────────────
const title = (s, text, opts = {}) =>
  s.addText(text, {
    x: M, y: opts.y ?? 0.52, w: W - 2 * M, h: 0.9,
    fontFace: H, fontSize: opts.size ?? 38, bold: true,
    color: opts.color ?? NAVY, align: "left", margin: 0,
  });

const kicker = (s, text, color = AMBER) =>
  s.addText(text.toUpperCase(), {
    x: M, y: 0.28, w: W - 2 * M, h: 0.3,
    fontFace: B, fontSize: 11, bold: true, color, charSpacing: 2, margin: 0,
  });

// The repeated motif: a numbered disc. Used on every content slide.
const disc = (s, n, x, y, d = 0.46, fill = NAVY, txt = WHITE) => {
  s.addShape(pres.ShapeType.ellipse, {
    x, y, w: d, h: d, fill: { color: fill },
  });
  s.addText(String(n), {
    x, y, w: d, h: d, fontFace: B, fontSize: d > 0.5 ? 15 : 12,
    bold: true, color: txt, align: "center", valign: "middle", margin: 0,
  });
};

const card = (s, x, y, w, h, fill = ICE_L) =>
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.08, fill: { color: fill },
    shadow: { type: "outer", angle: 90, offset: 1.5, blur: 6, color: "9AA5B5", opacity: 0.22 },
  });

const notes = (s, t) => s.addNotes(t);

// ── 1 · Title (dark) ──────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addText("PeerForge", {
    x: M, y: 2.25, w: 9.5, h: 1.25,
    fontFace: H, fontSize: 60, bold: true, color: WHITE, margin: 0,
  });
  s.addText("Face the panel before the panel faces you", {
    x: M, y: 3.5, w: 10, h: 0.6,
    fontFace: H, fontSize: 24, italic: true, color: ICE, margin: 0,
  });
  s.addText(
    "An AI peer-review panel that argues about your research — and checks its own work.",
    { x: M, y: 4.35, w: 9.6, h: 0.5, fontFace: B, fontSize: 15, color: "AAB8D6", margin: 0 });
  // motif echo, oversized
  s.addShape(pres.ShapeType.ellipse, {
    x: 11.0, y: 2.35, w: 1.5, h: 1.5, fill: { color: NAVY_D },
  });
  s.addText("PF", {
    x: 11.0, y: 2.35, w: 1.5, h: 1.5, fontFace: H, fontSize: 34,
    bold: true, color: ICE, align: "center", valign: "middle", margin: 0,
  });
  notes(s, "Open with the demo, not the slide. Upload a paper, run three turns, let them watch the reviewers disagree.");
}

// ── 2 · The problem ───────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "The problem");
  title(s, "Serious criticism arrives too late to act on");
  const rows = [
    ["Weeks", "for supervisor comments. Months for reviewer reports."],
    ["By then", "the design is fixed, the data collected, the flaw unfixable."],
    ["The one useful sentence", "“you cannot claim causation with this allocation procedure” — lands after it is any use."],
  ];
  rows.forEach(([lead, rest], i) => {
    const y = 1.95 + i * 1.15;
    disc(s, i + 1, M, y + 0.06);
    s.addText(
      [{ text: lead + " — ", options: { bold: true, color: NAVY } },
       { text: rest, options: { color: INK } }],
      { x: M + 0.72, y, w: W - 2 * M - 0.9, h: 0.9, fontFace: B, fontSize: 16, margin: 0, valign: "top" });
  });
  s.addText(
    "The gap between “I think it’s ready” and “the panel thinks it’s ready” is where viva failures and desk rejections live.",
    { x: M, y: 5.75, w: W - 2 * M, h: 0.7, fontFace: H, fontSize: 17, italic: true, color: MUTED, margin: 0 });
  notes(s, "Supervisors are stretched. Examiners see the work once.");
}

// ── 3 · Why the obvious fix fails ─────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "Why the obvious fix fails", RED);
  title(s, "Ask a general AI, and it invents the evidence");
  card(s, M, 1.85, W - 2 * M, 1.75, "FBF0EF");
  s.addText(
    "“This is a well-structured study. Consider expanding the literature review. " +
    "As noted in Section 2.3 on page 12, the sampling approach…”",
    { x: M + 0.35, y: 2.05, w: W - 2 * M - 0.7, h: 1.35,
      fontFace: H, fontSize: 19, italic: true, color: "6B2F2A", margin: 0, valign: "middle" });
  s.addText("The paper has no Section 2.3. It has no page 12.", {
    x: M, y: 3.85, w: W - 2 * M, h: 0.5, fontFace: B, fontSize: 20, bold: true, color: RED, margin: 0 });
  s.addText(
    "Point five models at one paper and it gets worse: within two rounds you have one opinion " +
    "restated five times, everyone agreeing, and confident citations to nothing.",
    { x: M, y: 4.7, w: W - 2 * M, h: 1.0, fontFace: B, fontSize: 16, color: INK, margin: 0 });
  notes(s, "This is the slide that lands. Everyone in the room has seen this output.");
}

// ── 4 · What we built ─────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "What we built");
  title(s, "A panel, not an assistant");
  const lanes = [
    ["Methodologist", "Allocation, power, controls, validity threats"],
    ["Domain expert", "Construct validity, related work, novelty"],
    ["External examiner", "Is this publishable — and what must change"],
  ];
  const cw = (W - 2 * M - 0.8) / 3;
  lanes.forEach(([h, d], i) => {
    const x = M + i * (cw + 0.4);
    card(s, x, 1.9, cw, 2.15);
    disc(s, i + 1, x + 0.3, 2.15, 0.5);
    s.addText(h, { x: x + 0.3, y: 2.78, w: cw - 0.6, h: 0.5,
      fontFace: H, fontSize: 17, bold: true, color: NAVY, margin: 0, valign: "top" });
    s.addText(d, { x: x + 0.3, y: 3.3, w: cw - 0.6, h: 0.65,
      fontFace: B, fontSize: 13, color: INK, margin: 0, valign: "top" });
  });
  s.addText("They read your document, research the literature, prepare privately, then disagree with each other in front of you.",
    { x: M, y: 4.45, w: W - 2 * M, h: 0.6, fontFace: B, fontSize: 16, color: INK, margin: 0 });
  card(s, M, 5.3, W - 2 * M, 1.0, NAVY);
  s.addText("Then the part nobody else does:  it checks itself.", {
    x: M + 0.35, y: 5.3, w: W - 2 * M - 0.7, h: 1.0,
    fontFace: H, fontSize: 21, bold: true, color: WHITE, valign: "middle", margin: 0 });
}

// ── 5 · The hard part ─────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "The hard part");
  title(s, "Eleven integrity rules, every turn");
  s.addText(
    "Repetition  ·  deference  ·  self-contradiction  ·  role drift  ·  generic filler  ·  " +
    "fabricated citations  ·  contradicted citations  ·  session meta-commentary",
    { x: M, y: 1.85, w: W - 2 * M, h: 0.75, fontFace: B, fontSize: 15, color: NAVY, margin: 0 });
  s.addText("Ten force regeneration. The retry is re-checked — a retry that fixes one problem and introduces another is still a failure.",
    { x: M, y: 2.6, w: W - 2 * M, h: 0.55, fontFace: B, fontSize: 14, italic: true, color: MUTED, margin: 0 });

  const rows = [
    ["No document uploaded", "Every page reference is fabrication → stripped"],
    ["Document uploaded", "Cited sections checked against what it actually contains"],
    ["Section 9 of a 4-section paper", "Caught"],
    ["Section 2.1 that genuinely exists", "Passes untouched"],
    ["(McKay et al., 2018)", "Never flagged — a reviewer may know it"],
  ];
  s.addTable(
    [[{ text: "Situation", options: { bold: true, color: WHITE, fill: { color: NAVY } } },
      { text: "What happens", options: { bold: true, color: WHITE, fill: { color: NAVY } } }],
     ...rows.map(r => [r[0], r[1]])],
    { x: M, y: 3.35, w: W - 2 * M, colW: [4.6, 7.2],
      fontFace: B, fontSize: 13, color: INK, border: { pt: 0.5, color: "D6DAE0" },
      fill: { color: WHITE }, rowH: 0.42, valign: "middle", margin: 6 });
  notes(s, "Citations are verified against the document — not against plausibility.");
}

// ── 6 · The proof ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "The proof", GREEN);
  title(s, "Measured, before and after");
  const data = [
    ["Fabricated citations reaching the transcript", "33", "0"],
    ["Contradicted citations", "11", "0"],
    ["Panel restatement rate", "1.00", "0.20"],
    ["Reviewers opening by deferring", "0.80", "0.00"],
    ["Retrieved sources actually cited", "0 of 5", "3 of 5"],
  ];
  s.addTable(
    [[{ text: "", options: { fill: { color: WHITE } } },
      { text: "BEFORE", options: { bold: true, color: WHITE, fill: { color: RED }, align: "center" } },
      { text: "AFTER", options: { bold: true, color: WHITE, fill: { color: GREEN }, align: "center" } }],
     ...data.map(([k, a, b]) => [
       { text: k, options: { color: INK } },
       { text: a, options: { align: "center", color: RED, bold: true } },
       { text: b, options: { align: "center", color: GREEN, bold: true } }])],
    { x: M, y: 1.9, w: W - 2 * M, colW: [6.6, 2.6, 2.6],
      fontFace: B, fontSize: 15, border: { pt: 0.5, color: "D6DAE0" },
      fill: { color: WHITE }, rowH: 0.52, valign: "middle", margin: 7 });
  card(s, M, 5.35, W - 2 * M, 1.15, ICE_L);
  s.addText(
    [{ text: "The fabrication test was adversarial: ", options: { bold: true, color: NAVY } },
     { text: "three reviewers explicitly instructed to cite pages, sections, tables and figures in every paragraph, on a session with no document at all. Zero got through.", options: { color: INK } }],
    { x: M + 0.35, y: 5.35, w: W - 2 * M - 0.7, h: 1.15,
      fontFace: B, fontSize: 14.5, valign: "middle", margin: 0 });
  notes(s, "Slow down here. These are the numbers that separate this from a prompt.");
}

// ── 7 · What the user gets ────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "The output");
  title(s, "What the researcher walks away with");
  const items = [
    ["Transcript", "The argument as it happened, reviewer by reviewer"],
    ["Summary", "Grounded in the real transcript — refuses to summarise a session that did not happen"],
    ["15 defence questions", "Each tied to the excerpt from your document that prompted it"],
    ["Readiness assessment", "Ten scored dimensions, with a stated basis"],
    ["Signed certificate", "Publicly verifiable, hash-bound to its evidence"],
  ];
  items.forEach(([h, d], i) => {
    const y = 1.85 + i * 0.98;
    disc(s, i + 1, M, y + 0.08, 0.42);
    s.addText(h, { x: M + 0.68, y, w: 3.3, h: 0.42,
      fontFace: H, fontSize: 16, bold: true, color: NAVY, margin: 0 });
    s.addText(d, { x: M + 4.0, y, w: W - M - 4.0 - M, h: 0.55,
      fontFace: B, fontSize: 13.5, color: INK, margin: 0 });
  });
  notes(s, "Show a real certificate verifying. Then change the evidence and show it report SUPERSEDED — authentic but stale, not forged.");
}

// ── 8 · Market ────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "Market");
  title(s, "Individual pain, institutional budget");
  const segs = [
    ["Doctoral candidates", "A viva is a single high-stakes event with almost no rehearsal available."],
    ["Researchers pre-submission", "Desk rejection is common at selective venues — much of it for reasons a panel names in ten minutes."],
    ["Departments & graduate schools", "Courses, roles, seats and invitations are built in. A department buys seats; professors run courses."],
  ];
  const cw = (W - 2 * M - 0.8) / 3;
  segs.forEach(([h, d], i) => {
    const x = M + i * (cw + 0.4);
    card(s, x, 1.9, cw, 2.4);
    disc(s, i + 1, x + 0.3, 2.15, 0.5);
    s.addText(h, { x: x + 0.3, y: 2.78, w: cw - 0.6, h: 0.62,
      fontFace: H, fontSize: 15.5, bold: true, color: NAVY, margin: 0, valign: "top" });
    s.addText(d, { x: x + 0.3, y: 3.44, w: cw - 0.6, h: 0.8,
      fontFace: B, fontSize: 12.5, color: INK, margin: 0, valign: "top" });
  });
  card(s, M, 4.6, W - 2 * M, 0.95, "FDF4E3");
  s.addText(
    [{ text: "Sizing figures are placeholders. ", options: { bold: true, color: AMBER } },
     { text: "Every other number in this deck was measured against a running instance; these were not. Source them before presenting.", options: { color: INK } }],
    { x: M + 0.35, y: 4.6, w: W - 2 * M - 0.7, h: 0.95,
      fontFace: B, fontSize: 13.5, valign: "middle", margin: 0 });
  s.addText("Land and expand: one supervisor’s cohort → the department → the graduate school.",
    { x: M, y: 5.75, w: W - 2 * M, h: 0.5, fontFace: H, fontSize: 16, italic: true, color: MUTED, margin: 0 });
}

// ── 9 · Business model ────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "Business model");
  title(s, "Institutional seats");
  card(s, M, 1.95, 5.6, 2.85, NAVY);
  s.addText("Priced per billable student seat", {
    x: M + 0.4, y: 2.25, w: 4.8, h: 0.9, fontFace: H, fontSize: 22, bold: true, color: WHITE, margin: 0 });
  s.addText("Staff seats are free. Seats are reserved at invitation time, so a department knows its committed spend before anyone accepts.",
    { x: M + 0.4, y: 3.15, w: 4.8, h: 1.1, fontFace: B, fontSize: 13.5, color: ICE, margin: 0 });

  s.addText("Built and working today", {
    x: 7.0, y: 2.0, w: 5.5, h: 0.4, fontFace: H, fontSize: 17, bold: true, color: NAVY, margin: 0 });
  s.addText(
    ["Organisations and courses", "Four roles, two membership scopes",
     "Single and bulk invitation", "Seat accounting with pending reservations",
     "Cohort progress views"].map((t, i, a) => ({
      text: t, options: { bullet: true, breakLine: i < a.length - 1 } })),
    { x: 7.0, y: 2.5, w: 5.5, h: 2.3, fontFace: B, fontSize: 14,
      color: INK, paraSpaceAfter: 6, margin: 0, valign: "top" });
  card(s, M, 5.25, W - 2 * M, 1.0, ICE_L);
  s.addText("The institution tier is not a roadmap item — it is running in the demo today.", {
    x: M + 0.35, y: 5.25, w: W - 2 * M - 0.7, h: 1.0,
    fontFace: H, fontSize: 17, italic: true, color: NAVY, valign: "middle", margin: 0 });
  notes(s, "Seats reserved at invitation time means a department knows its committed spend before anyone accepts.");
}

// ── 10 · Defensibility ────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "Why it is defensible");
  title(s, "Most AI review tools are a prompt. This is a system.");
  const pts = [
    ["Three-stage pipeline", "Private reasoning, visible response, validation — a reviewer works out what is uniquely theirs to say before saying it"],
    ["Preparation before speaking", "A private memo per reviewer, with the outside literature they consulted"],
    ["Cryptographic assurance", "The certificate id is a hash of scores and ordered evidence"],
    ["Provenance", "Which chunk a claim rests on, sha256 re-verified"],
  ];
  pts.forEach(([h, d], i) => {
    const y = 1.9 + i * 0.92;
    disc(s, i + 1, M, y + 0.05, 0.42);
    s.addText(h, { x: M + 0.68, y, w: 3.5, h: 0.42,
      fontFace: H, fontSize: 15.5, bold: true, color: NAVY, margin: 0 });
    s.addText(d, { x: M + 4.2, y, w: W - M - 4.2 - M, h: 0.6,
      fontFace: B, fontSize: 13, color: INK, margin: 0 });
  });
  card(s, M, 5.7, W - 2 * M, 0.95, ICE_L);
  s.addText("121 API operations   ·   39 tables   ·   440 backend tests   ·   ~53,000 lines", {
    x: M, y: 5.7, w: W - 2 * M, h: 0.95, fontFace: H, fontSize: 18, bold: true,
    color: NAVY, align: "center", valign: "middle", margin: 0 });
  notes(s, "The moat is not the prompt. It is the eleven rules and the measurement harness — each written after observing a specific failure in real output.");
}

// ── 11 · What does not work yet ───────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "What does not work yet", AMBER);
  title(s, "The limits, stated plainly");
  const lims = [
    ["Page citations are not verified", "391 of 398 chunks in a real database carry no page number; checking pages would reject legitimate citations"],
    ["Differentiation degrades by round two", "On short papers with few distinct flaws. The gates catch it; the fix is partial"],
    ["Prep packs cite 3 of 5 sources", "Forcing all five in produces padding rather than argument"],
  ];
  lims.forEach(([h, d], i) => {
    const y = 1.95 + i * 1.25;
    card(s, M, y, W - 2 * M, 1.05, "FDF4E3");
    s.addText(h, { x: M + 0.35, y: y + 0.12, w: W - 2 * M - 0.7, h: 0.4,
      fontFace: H, fontSize: 16, bold: true, color: "8A5A10", margin: 0 });
    s.addText(d, { x: M + 0.35, y: y + 0.52, w: W - 2 * M - 0.7, h: 0.45,
      fontFace: B, fontSize: 13, color: INK, margin: 0 });
  });
  s.addText("We publish these in the product documentation, with numbers. A tool that tells you it is uncertain is worth more than one that is confidently wrong.",
    { x: M, y: 5.9, w: W - 2 * M, h: 0.7, fontFace: H, fontSize: 16, italic: true, color: MUTED, margin: 0 });
  notes(s, "Do not skip this slide. It is why the rest is credible.");
}

// ── 12 · Roadmap ──────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "Roadmap");
  title(s, "Where this goes");
  const phases = [
    ["Now", NAVY, ["Review panel", "Integrity enforcement", "Assessment & certificates", "Institution tier"]],
    ["Next", "2E5A8C", ["Document structure at ingest", "Full page/section verification", "Differentiation past round two", "LMS integration"]],
    ["Later", "6E8BB5", ["Longitudinal cohort readiness", "Reviewer calibration against real examiner outcomes"]],
  ];
  const cw = (W - 2 * M - 0.8) / 3;
  phases.forEach(([h, col, items], i) => {
    const x = M + i * (cw + 0.4);
    card(s, x, 1.95, cw, 2.55, ICE_L);
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 1.95, w: cw, h: 0.7, rectRadius: 0.08, fill: { color: col } });
    s.addText(h, { x, y: 1.95, w: cw, h: 0.7, fontFace: H, fontSize: 19,
      bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(items.map((t, j, a) => ({
      text: t, options: { bullet: true, breakLine: j < a.length - 1 } })),
      { x: x + 0.3, y: 2.82, w: cw - 0.6, h: 1.6, fontFace: B, fontSize: 13,
        color: INK, paraSpaceAfter: 7, margin: 0, valign: "top" });
  });
  card(s, M, 4.9, W - 2 * M, 1.15, NAVY);
  s.addText(
    "Everything under “Now” is running in the demo today — not a roadmap promise.",
    { x: M + 0.4, y: 4.9, w: W - 2 * M - 0.8, h: 1.15,
      fontFace: H, fontSize: 19, color: WHITE, valign: "middle", margin: 0 });
  notes(s, "The split matters: Now is demonstrable, Next is scoped, Later is honest about being unscoped.");
}

// ── 13 · The ask ──────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  kicker(s, "The ask");
  title(s, "One supervisor. One cohort. One term.");
  card(s, M, 2.1, W - 2 * M, 2.2, NAVY);
  s.addText(
    "We measure whether students who rehearse with a panel answer their examiners better than students who do not.",
    { x: M + 0.5, y: 2.1, w: W - 2 * M - 1.0, h: 2.2,
      fontFace: H, fontSize: 24, color: WHITE, valign: "middle", margin: 0 });
  s.addText("What we need to run it:", {
    x: M, y: 4.6, w: 5.0, h: 0.4, fontFace: H, fontSize: 17, bold: true, color: NAVY, margin: 0 });
  s.addText(
    ["A department willing to pilot", "A cohort with vivas this year",
     "Access to outcomes, so the claim is testable"].map((t, i, a) => ({
      text: t, options: { bullet: true, breakLine: i < a.length - 1 } })),
    { x: M, y: 5.1, w: 6.0, h: 1.5, fontFace: B, fontSize: 14.5,
      color: INK, paraSpaceAfter: 6, margin: 0, valign: "top" });
  notes(s, "Fill in for your audience: capital, a pilot department, or a design partner.");
}

// ── 14 · Close (dark) ─────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addText(
    "Every researcher eventually faces a panel that has read their work carefully and is not being kind about it.",
    { x: M, y: 2.0, w: W - 2 * M - 0.5, h: 1.5,
      fontFace: H, fontSize: 28, color: WHITE, margin: 0 });
  s.addText("There is no reason that should be the first time.", {
    x: M, y: 3.6, w: W - 2 * M, h: 0.7,
    fontFace: H, fontSize: 28, bold: true, italic: true, color: ICE, margin: 0 });
  s.addText(
    "Ten sessions across ten fields, each paper carrying real planted flaws — unconcealed allocation, " +
    "missing controls, thresholds tuned on the reported data, train/test leakage.",
    { x: M, y: 4.75, w: W - 2 * M - 0.5, h: 0.9, fontFace: B, fontSize: 14, color: "AAB8D6", margin: 0 });
  s.addText("Watch whether the panel finds them.", {
    x: M, y: 5.7, w: W - 2 * M, h: 0.5, fontFace: B, fontSize: 16, bold: true, color: AMBER, margin: 0 });
}

pres.writeFile({ fileName: "pptx/PeerForge-Pitch-Deck.pptx" })
  .then(f => console.log(`  wrote ${f}`));
