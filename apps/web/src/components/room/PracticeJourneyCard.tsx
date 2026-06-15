'use client';

/**
 * PracticeJourneyCard
 * ─────────────────────────────────────────────────────────────────────────
 * Shown alongside the session report so finishing a review session is not a
 * dead end. It tracks the user's preparation journey (session → practice
 * Q&A → feedback report), shows a *qualitative* readiness outlook (a band,
 * never a mark), and funnels the user into the Practice Q&A room.
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  getDefenseQuestions,
  getAnswers,
  getReadinessReport,
} from '@/lib/api';
import styles from './PracticeJourneyCard.module.css';

type Outlook = 'strong' | 'almost' | 'practice';

interface JourneyState {
  loaded: boolean;
  questionCount: number;
  answeredCount: number;
  hasReport: boolean;
  outlook: Outlook | null;
  nextStep: string | null;
}

const OUTLOOK_META: Record<Outlook, { label: string; hint: string; className: string }> = {
  strong: {
    label: 'On track',
    hint: 'Your practice answers were consistently well grounded. Keep your momentum with a final run-through.',
    className: 'outlookStrong',
  },
  almost: {
    label: 'Almost there',
    hint: 'Most answers held up, but a few areas still need work. Revisit the improvement plan in your feedback report.',
    className: 'outlookAlmost',
  },
  practice: {
    label: 'Needs more practice',
    hint: 'Several answers had gaps. Work through the improvement plan, then run another practice session.',
    className: 'outlookPractice',
  },
};

interface Props {
  debateId: string;
  /** Called when the user clicks "Continue to Practice Q&A". Falls back to navigating to the room. */
  onStartPractice?: () => void;
}

export default function PracticeJourneyCard({ debateId, onStartPractice }: Props) {
  const router = useRouter();
  const [journey, setJourney] = useState<JourneyState>({
    loaded: false,
    questionCount: 0,
    answeredCount: 0,
    hasReport: false,
    outlook: null,
    nextStep: null,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const next: JourneyState = {
        loaded: true,
        questionCount: 0,
        answeredCount: 0,
        hasReport: false,
        outlook: null,
        nextStep: null,
      };
      try {
        const q = await getDefenseQuestions(debateId);
        next.questionCount = q.count ?? q.questions?.length ?? 0;
      } catch { /* no questions yet */ }
      try {
        const a = await getAnswers(debateId);
        next.answeredCount = a.count ?? a.answers?.length ?? 0;
      } catch { /* no answers yet */ }
      try {
        const r = await getReadinessReport(debateId);
        next.hasReport = !!(r && (r.status === 'complete' || r.generated_at));
        // Numbers stay internal — only a qualitative band is ever shown.
        const v = r?.overall_readiness;
        if (next.hasReport && typeof v === 'number') {
          next.outlook = v >= 75 ? 'strong' : v >= 50 ? 'almost' : 'practice';
        }
        next.nextStep = r?.next_recommendation ?? null;
      } catch { /* no report yet */ }
      if (!cancelled) setJourney(next);
    })();
    return () => { cancelled = true; };
  }, [debateId]);

  const handleStartPractice = () => {
    if (onStartPractice) {
      onStartPractice();
    } else {
      router.push(`/room?debate_id=${debateId}&tab=defense`);
    }
  };

  if (!journey.loaded) return null;

  const { questionCount, answeredCount, hasReport, outlook, nextStep } = journey;
  const practiceStarted = answeredCount > 0;
  const practiceDone = questionCount > 0 && answeredCount >= questionCount;
  const outlookMeta = outlook ? OUTLOOK_META[outlook] : null;

  const steps = [
    {
      done: true,
      title: 'Review session',
      detail: 'Completed — your panel has discussed the work.',
    },
    {
      done: practiceDone,
      active: !practiceDone,
      title: 'Practice Q&A',
      detail: questionCount === 0
        ? 'Not started — answer panel questions about your own work.'
        : `${answeredCount} of ${questionCount} questions answered.`,
    },
    {
      done: hasReport,
      active: practiceStarted && !hasReport,
      title: 'Feedback report',
      detail: hasReport
        ? 'Generated — see your strengths and improvement plan.'
        : 'Generate it after practicing to see what to strengthen next.',
    },
  ];

  return (
    <div className={styles.card}>
      <div className={styles.headerRow}>
        <h3 className={styles.title}>🎯 Your Preparation Journey</h3>
        {outlookMeta && (
          <span className={`${styles.outlookChip} ${styles[outlookMeta.className]}`}>
            {outlookMeta.label}
          </span>
        )}
      </div>

      <p className={styles.intro}>
        {practiceStarted
          ? 'The session report is one part of your preparation — your practice answers tell the rest of the story.'
          : 'The session report shows what your panel thinks. The next step is checking whether you can answer their questions yourself.'}
      </p>

      <ol className={styles.steps}>
        {steps.map((s, i) => (
          <li
            key={i}
            className={`${styles.step} ${s.done ? styles.stepDone : ''} ${s.active ? styles.stepActive : ''}`}
          >
            <span className={styles.stepMarker}>{s.done ? '✓' : i + 1}</span>
            <span className={styles.stepBody}>
              <span className={styles.stepTitle}>{s.title}</span>
              <span className={styles.stepDetail}>{s.detail}</span>
            </span>
          </li>
        ))}
      </ol>

      {outlookMeta && (
        <div className={styles.outlookBox}>
          <p className={styles.outlookHint}>{outlookMeta.hint}</p>
          {nextStep && <p className={styles.nextStep}><strong>Next step:</strong> {nextStep}</p>}
          <p className={styles.outlookNote}>
            Qualitative outlook based on your practice answers — not a grade.
          </p>
        </div>
      )}

      <div className={styles.ctaRow}>
        <button className={styles.ctaBtn} onClick={handleStartPractice}>
          {practiceStarted ? 'Continue Practice Q&A →' : 'Start Practice Q&A →'}
        </button>
        {practiceStarted && !hasReport && (
          <span className={styles.ctaHint}>
            Then generate your feedback report from the Practice Q&A tab.
          </span>
        )}
      </div>
    </div>
  );
}
