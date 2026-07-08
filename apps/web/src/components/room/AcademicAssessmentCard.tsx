'use client';

/**
 * AcademicAssessmentCard
 * ─────────────────────────────────────────────────────────────────────────
 * The ten-dimension Academic Assessment Matrix. Synthesised by an AI
 * examiner from all session evidence — research profile, practice answers,
 * panel discussion, and summary — each dimension is rated /10 with a
 * one-sentence comment grounded in what the researcher actually said.
 *
 * Regenerate after any activity (practice answer, panel discussion, voice
 * session) to see progress.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  generateAcademicAssessment,
  getAcademicAssessment,
  type AcademicAssessment,
} from '@/lib/api';
import { keyStore } from '@/lib/openrouterKeyStore';
import styles from './AcademicAssessmentCard.module.css';

interface Props {
  debateId: string;
  /** Where the regeneration was initiated from (analytics/history context). */
  triggerSource?: string;
  /** Generate a first assessment automatically when none exists yet, so the
   *  readiness trajectory accumulates without a manual click. */
  autoGenerate?: boolean;
}

function bandClass(score: number): string {
  if (score >= 8) return styles.bandStrong;
  if (score >= 6) return styles.bandCompetent;
  if (score >= 4) return styles.bandDeveloping;
  return styles.bandUnderPrepared;
}

function bandLabel(score: number): string {
  if (score >= 8) return 'Strong';
  if (score >= 6) return 'Competent';
  if (score >= 4) return 'Developing';
  return 'Under-prepared';
}

export default function AcademicAssessmentCard({ debateId, triggerSource = 'manual', autoGenerate = false }: Props) {
  const [assessment, setAssessment] = useState<AcademicAssessment | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const autoGenRanRef = useRef(false);

  const handleGenerate = useCallback(async () => {
    const key = keyStore.getKey();
    if (!key) {
      setError('Add your OpenRouter API key in Settings to generate the assessment.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const a = await generateAcademicAssessment(debateId, key, triggerSource);
      setAssessment(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Assessment generation failed');
    } finally {
      setLoading(false);
    }
  }, [debateId, triggerSource]);

  useEffect(() => {
    let cancelled = false;
    getAcademicAssessment(debateId)
      .then(a => { if (!cancelled) setAssessment(a); })
      .catch(() => {
        // None yet — kick off a first assessment when auto-generation is on,
        // otherwise show the manual generate state.
        if (!cancelled && autoGenerate && !autoGenRanRef.current && keyStore.getKey()) {
          autoGenRanRef.current = true;
          handleGenerate();
        }
      });
    return () => { cancelled = true; };
  }, [debateId, autoGenerate, handleGenerate]);

  const basisText = assessment?.basis
    ? [
        assessment.basis.has_profile ? 'research profile' : null,
        assessment.basis.answer_count
          ? `${assessment.basis.answer_count} practice answer${assessment.basis.answer_count === 1 ? '' : 's'}`
          : null,
        assessment.basis.message_count
          ? `${assessment.basis.message_count} panel contributions`
          : null,
        assessment.basis.has_summary ? 'session summary' : null,
      ].filter(Boolean).join(' · ')
    : '';

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div>
          <h3 className={styles.title}>Academic Assessment Matrix</h3>
          <p className={styles.subtitle}>
            Ten dimensions of research preparedness, assessed by an AI examiner
            from all session evidence.
          </p>
        </div>
        {assessment && (
          <div className={`${styles.overallBadge} ${bandClass(assessment.overall_score)}`}>
            <span className={styles.overallScore}>{assessment.overall_score.toFixed(1)}</span>
            <span className={styles.overallDenominator}>/10</span>
            <span className={styles.overallBand}>{bandLabel(assessment.overall_score)}</span>
          </div>
        )}
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {!assessment && !loading && (
        <div className={styles.emptyState}>
          <p>
            No assessment yet. Generate one after a practice answer, a panel
            discussion, or a voice session — the examiner rates ten dimensions
            from the evidence available so far.
          </p>
        </div>
      )}

      {loading && (
        <div className={styles.loadingState}>
          <div className={styles.spinner} />
          <p>Assessing ten dimensions against the session evidence…</p>
        </div>
      )}

      {assessment && !loading && (
        <>
          <div className={styles.matrix}>
            {assessment.dimensions.map((d, i) => (
              <button
                key={d.key}
                className={`${styles.dimensionRow} ${expanded === d.key ? styles.dimensionRowOpen : ''}`}
                onClick={() => setExpanded(expanded === d.key ? null : d.key)}
                title="Click for the examiner's comment"
              >
                <span className={styles.dimensionIndex}>{i + 1}</span>
                <span className={styles.dimensionLabel}>{d.label}</span>
                <span className={styles.dimensionBarTrack}>
                  <span
                    className={`${styles.dimensionBarFill} ${bandClass(d.score)}`}
                    style={{ width: `${(d.score / 10) * 100}%` }}
                  />
                </span>
                <span className={`${styles.dimensionScore} ${bandClass(d.score)}`}>
                  {d.score.toFixed(1)}
                </span>
                {expanded === d.key && (
                  <span className={styles.dimensionComment}>{d.comment}</span>
                )}
              </button>
            ))}
          </div>

          {assessment.overall_remarks && (
            <div className={styles.remarks}>
              <h4>Examiner&apos;s Remarks</h4>
              <p>{assessment.overall_remarks}</p>
            </div>
          )}

          {basisText && (
            <p className={styles.basis}>
              Assessed from: {basisText}
              {assessment.generated_at &&
                ` · ${new Date(assessment.generated_at).toLocaleString()}`}
            </p>
          )}
        </>
      )}

      <div className={styles.actions}>
        <button className={styles.generateBtn} onClick={handleGenerate} disabled={loading}>
          {loading
            ? 'Assessing…'
            : assessment
              ? '↻ Reassess (after new activity)'
              : 'Generate Assessment'}
        </button>
        <span className={styles.note}>
          Formative assessment — regenerate after each activity to track progress.
        </span>
      </div>
    </div>
  );
}
