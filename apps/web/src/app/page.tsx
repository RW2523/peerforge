'use client';

import Link from 'next/link';
import AppNav from '@/components/layout/AppNav';
import styles from './home.module.css';

export default function HomePage() {
  return (
    <>
      <AppNav />
      <main className={styles.main}>

        {/* ── Hero ─────────────────────────────────────────────────── */}
        <section className={styles.hero}>
          <div className={styles.heroInner}>
            <div className={styles.badge}>Academic Review & Research Feedback Platform</div>
            <h1 className={styles.heroHeadline}>
              Strengthen your research
              <br />
              <span className={styles.gradient}>with AI-powered academic review.</span>
            </h1>
            <p className={styles.heroSub}>
              Upload your research, discover weak areas, practice Q&amp;A with an AI review panel,
              and receive structured, actionable feedback on your own work.
            </p>
            <div className={styles.heroCtas}>
              <Link href="/setup" className={styles.btnPrimary}>
                Start a Review Session
              </Link>
              <a href="#how-it-works" className={styles.btnGhost}>
                See how it works
              </a>
            </div>
            <p className={styles.heroDisclaimer}>
              PeerForge helps you strengthen your own work — it does not write it for you.
            </p>
          </div>
        </section>

        {/* ── Problem ──────────────────────────────────────────────── */}
        <section className={styles.section}>
          <div className={styles.sectionInner}>
            <div className={styles.sectionBadge}>The Problem</div>
            <h2 className={styles.sectionHeadline}>
              Most researchers present their work without rigorous practice.
            </h2>
            <div className={styles.problemGrid}>
              <div className={styles.problemCard}>
                <div className={styles.problemIcon}>⚠️</div>
                <h3>No realistic rehearsal</h3>
                <p>Practicing with friends or advisors rarely captures the depth and rigour of real academic questioning.</p>
              </div>
              <div className={styles.problemCard}>
                <div className={styles.problemIcon}>🔍</div>
                <h3>Unknown weak areas</h3>
                <p>It is hard to see your own methodology gaps, unsupported claims, or missing evidence until a reviewer flags them — live.</p>
              </div>
              <div className={styles.problemCard}>
                <div className={styles.problemIcon}>📋</div>
                <h3>No structured feedback loop</h3>
                <p>Generic notes don&apos;t tell you which questions to practice, which answers were weak, or whether you improved between sessions.</p>
              </div>
            </div>
          </div>
        </section>

        {/* ── How It Works ─────────────────────────────────────────── */}
        <section id="how-it-works" className={`${styles.section} ${styles.sectionAlt}`}>
          <div className={styles.sectionInner}>
            <div className={styles.sectionBadge}>How It Works</div>
            <h2 className={styles.sectionHeadline}>
              From uploaded research to actionable feedback in one structured loop.
            </h2>
            <div className={styles.stepsGrid}>
              {STEPS.map((s, i) => (
                <div key={i} className={styles.stepCard}>
                  <div className={styles.stepNum}>{i + 1}</div>
                  <div>
                    <h3 className={styles.stepTitle}>{s.title}</h3>
                    <p className={styles.stepDesc}>{s.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Core Features ─────────────────────────────────────────── */}
        <section className={styles.section}>
          <div className={styles.sectionInner}>
            <div className={styles.sectionBadge}>Core Features</div>
            <h2 className={styles.sectionHeadline}>
              Every tool a researcher needs to present with confidence.
            </h2>
            <div className={styles.featureGrid}>
              {FEATURES.map((f, i) => (
                <div key={i} className={styles.featureCard}>
                  <span className={styles.featureIcon}>{f.icon}</span>
                  <h3>{f.title}</h3>
                  <p>{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Review Session Preview ────────────────────────────────── */}
        <section className={`${styles.section} ${styles.sectionAlt}`}>
          <div className={styles.sectionInner}>
            <div className={styles.sectionBadge}>Practice Q&amp;A Room</div>
            <h2 className={styles.sectionHeadline}>
              Face AI reviewers that question every weak point.
            </h2>
            <p className={styles.sectionSub}>
              Each AI reviewer plays a distinct academic role — from a skeptical reviewer
              who challenges unsupported claims, to a methodology professor who drills your research design.
            </p>
            <div className={styles.previewCard}>
              <div className={styles.previewHeader}>
                <span className={styles.previewTitle}>Review Session</span>
                <span className={styles.previewBadge}>LIVE</span>
              </div>
              <div className={styles.chatLines}>
                {PREVIEW_CHAT.map((line, i) => (
                  <div key={i} className={`${styles.chatLine} ${line.role === 'student' ? styles.chatStudent : styles.chatCommittee}`}>
                    <span className={styles.chatSender}>{line.sender}</span>
                    <span className={styles.chatMsg}>{line.msg}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Feedback Report Preview ───────────────────────────────── */}
        <section className={styles.section}>
          <div className={styles.sectionInner}>
            <div className={styles.sectionBadge}>Feedback Report</div>
            <h2 className={styles.sectionHeadline}>
              Structured feedback that tells you exactly what to strengthen next.
            </h2>
            <p className={styles.sectionSub}>
              After each session, PeerForge generates a qualitative report — no marks, no grades —
              with your strongest answers, the areas that need work, and a prioritised improvement plan.
            </p>
            <div className={styles.reportPreview}>
              <div className={styles.reportHeader}>
                <span className={styles.reportTitle}>Session Feedback Report</span>
              </div>
              <div className={styles.problemGrid}>
                {REPORT_HIGHLIGHTS.map((h, i) => (
                  <div key={i} className={styles.problemCard}>
                    <div className={styles.problemIcon}>{h.icon}</div>
                    <h3>{h.title}</h3>
                    <p>{h.desc}</p>
                  </div>
                ))}
              </div>
              <div className={styles.reportNext}>
                <span className={styles.reportNextLabel}>Next recommended action:</span>
                <span className={styles.reportNextText}>
                  Your methodology answers lacked baseline comparisons. Practice five methodology questions with the Methodology Professor persona.
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* ── University Value ─────────────────────────────────────── */}
        <section className={`${styles.section} ${styles.sectionAlt}`}>
          <div className={styles.sectionInner}>
            <div className={styles.sectionBadge}>For Universities</div>
            <h2 className={styles.sectionHeadline}>
              A responsible academic preparation tool universities can trust.
            </h2>
            <div className={styles.pillars}>
              {PILLARS.map((p, i) => (
                <div key={i} className={styles.pillar}>
                  <span className={styles.pillarIcon}>{p.icon}</span>
                  <h3>{p.title}</h3>
                  <p>{p.desc}</p>
                </div>
              ))}
            </div>
            <div className={styles.integrityBox}>
              <strong>Academic Integrity First.</strong> PeerForge never writes your thesis, generates your results, or invents citations.
              It only helps you strengthen and present your own work — more clearly, more completely, and with confidence.
            </div>
          </div>
        </section>

        {/* ── Pricing / Waitlist ───────────────────────────────────── */}
        <section className={styles.section} id="waitlist">
          <div className={styles.sectionInner}>
            <div className={styles.sectionBadge}>Early Access</div>
            <h2 className={styles.sectionHeadline}>
              Currently in early access for research institutions.
            </h2>
            <p className={styles.sectionSub}>
              PeerForge is being piloted with graduate programs. Institutional and individual plans
              will be announced soon. Start practicing now with your own OpenRouter API key.
            </p>
            <div className={styles.pricingCards}>
              <div className={styles.pricingCard}>
                <h3>Student</h3>
                <div className={styles.pricingPrice}>Free Beta</div>
                <ul className={styles.pricingList}>
                  <li>1 research workspace</li>
                  <li>Research analysis</li>
                  <li>Question bank</li>
                  <li>Practice review sessions</li>
                  <li>Qualitative feedback reports</li>
                  <li>Bring your own OpenRouter key</li>
                </ul>
                <Link href="/setup" className={styles.btnPrimary}>
                  Start Free
                </Link>
              </div>
              <div className={`${styles.pricingCard} ${styles.pricingCardFeatured}`}>
                <div className={styles.pricingFeaturedBadge}>Coming Soon</div>
                <h3>Institution</h3>
                <div className={styles.pricingPrice}>Contact Us</div>
                <ul className={styles.pricingList}>
                  <li>Unlimited student seats</li>
                  <li>Advisor review mode</li>
                  <li>Department guideline alignment</li>
                  <li>Cohort-level insights</li>
                  <li>Audit logs &amp; compliance controls</li>
                  <li>SSO &amp; LMS integration</li>
                </ul>
                <button className={styles.btnOutline} disabled>
                  Join Waitlist
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* ── Final CTA ───────────────────────────────────────────── */}
        <section className={`${styles.section} ${styles.ctaSection}`}>
          <div className={styles.sectionInner}>
            <h2 className={styles.ctaHeadline}>
              Your presentation date is approaching. Start practicing now.
            </h2>
            <p className={styles.ctaSub}>
              Upload your thesis or research paper and get your first AI review session in minutes.
            </p>
            <Link href="/setup" className={styles.btnPrimaryLg}>
              Start a Review Session
            </Link>
          </div>
        </section>

        {/* ── Footer ──────────────────────────────────────────────── */}
        <footer className={styles.footer}>
          <p>PeerForge — AI Academic Review &amp; Research Feedback Platform</p>
          <p className={styles.footerSub}>
            A responsible tool for academic preparation. PeerForge does not write thesis content, generate results, or invent citations.
          </p>
        </footer>

      </main>
    </>
  );
}

// ── Static data ───────────────────────────────────────────────────────────

const STEPS = [
  {
    title: 'Create your research workspace',
    desc: 'Enter your research title, domain, project type (thesis, dissertation, proposal, paper), and research stage.',
  },
  {
    title: 'Upload your research materials',
    desc: 'Upload your draft, proposal, slides, advisor notes, and related papers. PeerForge extracts, chunks, and indexes everything.',
  },
  {
    title: 'Analyze your research',
    desc: 'The AI identifies your research problem, methodology, contribution, evidence, limitations, and weak areas — all grounded in your uploaded documents.',
  },
  {
    title: 'Generate your question bank',
    desc: 'Source-grounded review questions are generated across 10 categories: problem statement, methodology, novelty, evidence, limitations, results, and more.',
  },
  {
    title: 'Run a practice review session',
    desc: 'AI reviewers with different roles — Methodology Professor, Skeptical Reviewer, Domain Expert, Independent Reviewer — take turns questioning you.',
  },
  {
    title: 'Receive your feedback report',
    desc: 'Each answer receives qualitative feedback. Your report shows strong areas, answers to revisit, repeated issues, and a prioritised improvement plan.',
  },
];

const FEATURES = [
  {
    icon: '🔬',
    title: 'Research Analysis Engine',
    desc: 'Extracts your research problem, gap, methodology, contribution, and weak areas from uploaded documents.',
  },
  {
    icon: '❓',
    title: 'Review Question Bank',
    desc: 'Generates grounded questions across 10 categories with source citations, difficulty levels, and follow-up rules.',
  },
  {
    icon: '🎭',
    title: 'AI Reviewer Personas',
    desc: 'Distinct academic roles including Advisor, Methodology Professor, Skeptical Reviewer, Independent Reviewer, and Domain Expert.',
  },
  {
    icon: '💬',
    title: 'Structured Answer Feedback',
    desc: 'Every answer receives specific, qualitative feedback: what worked, what was missing, and one concrete improvement.',
  },
  {
    icon: '🔄',
    title: 'Follow-Up Question Engine',
    desc: 'Weak answers trigger targeted follow-ups: ask for evidence, demand baseline comparison, or require limitation explanation.',
  },
  {
    icon: '📋',
    title: 'Feedback Report',
    desc: 'Aggregated qualitative report with strong answers, answers to revisit, repeated issues, and a prioritised improvement plan.',
  },
  {
    icon: '📈',
    title: 'Progress Tracking',
    desc: 'Track your sessions over time, identify repeated weak areas, and see how your answers improve with practice.',
  },
  {
    icon: '🛡️',
    title: 'Grounded Evidence Only',
    desc: 'Every AI question and critique is tied to your uploaded materials. No invented citations, no fabricated results.',
  },
];

const PREVIEW_CHAT = [
  {
    role: 'committee',
    sender: 'Methodology Professor',
    msg: 'Your paper states you used a mixed-methods approach, but Section 3.2 only describes the quantitative instrument. How did the qualitative component contribute to your findings?',
  },
  {
    role: 'student',
    sender: 'You',
    msg: 'The interviews in Chapter 4 were used to triangulate the survey results and explain unexpected patterns in the quantitative data.',
  },
  {
    role: 'committee',
    sender: 'Methodology Professor',
    msg: 'Your answer mentions triangulation, but does not specify how conflicts between the qualitative and quantitative data were resolved. Can you explain your reconciliation process?',
  },
];

const REPORT_HIGHLIGHTS = [
  {
    icon: '💪',
    title: 'What went well',
    desc: 'Your problem statement answers were clear and consistently grounded in Chapter 1 of your draft.',
  },
  {
    icon: '🔍',
    title: 'Areas to strengthen',
    desc: 'Methodology answers lacked baseline comparisons, and two novelty claims were not tied to evidence in your materials.',
  },
  {
    icon: '🗺️',
    title: 'Improvement plan',
    desc: 'A prioritised, step-by-step plan: which questions to re-practice, which sections to revise, and what evidence to add.',
  },
];

const PILLARS = [
  {
    icon: '🏛️',
    title: 'Academically responsible',
    desc: 'PeerForge is a preparation tool, not a writing tool. It supports students in strengthening their own work, not producing it.',
  },
  {
    icon: '🔒',
    title: 'Private and secure',
    desc: 'Student research materials are kept private. Data access is controlled, and audit logs are maintained for institutional compliance.',
  },
  {
    icon: '💬',
    title: 'Feedback, not grades',
    desc: 'PeerForge never assigns marks or scores. All feedback is qualitative, specific, and actionable — focused on improvement, not judgement.',
  },
  {
    icon: '📊',
    title: 'Department-level insights',
    desc: 'Aggregate, privacy-safe insights show common weak areas across your cohort so department programs can improve their preparation approach.',
  },
];
