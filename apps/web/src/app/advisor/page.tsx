'use client';

/**
 * Advisor — multi-student readiness console (Phase 3 / M7).
 *
 * The view a supervisor or program coordinator uses: every student in the
 * department, their average readiness band, an at-risk flag for who needs
 * attention, the cohort's most common weak areas, and a drill-down into each
 * student's individual sessions (each links to its signed certificate).
 */
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import { getStudentsOverview, StudentsOverview } from '@/lib/api';
import styles from './advisor.module.css';

const WORKSPACE_ID = '00000000-0000-0000-0000-000000000101';

const BAND_CLASS: Record<string, string> = {
  Strong: 'bandStrong', Competent: 'bandCompetent',
  Developing: 'bandDeveloping', 'Under-prepared': 'bandUnder',
};

export default function AdvisorPage() {
  const router = useRouter();
  const [data, setData] = useState<StudentsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    getStudentsOverview(WORKSPACE_ID)
      .then(setData)
      .catch((e) => setError(String(e?.message || e)));
  }, []);

  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <header className={styles.header}>
          <div>
            <h1 className={styles.title}>Advisor Console</h1>
            <p className={styles.subtitle}>
              Every student&apos;s readiness at a glance — who&apos;s on track, who needs attention, and
              what the whole cohort keeps struggling with.
            </p>
          </div>
        </header>

        {error ? (
          <div className={styles.state}>Could not load: {error}</div>
        ) : !data ? (
          <div className={styles.state}>Loading cohort…</div>
        ) : data.student_count === 0 ? (
          <div className={styles.state}>
            No assessed students yet. Tag sessions with a student name and run an assessment to populate this view.
          </div>
        ) : (
          <>
            <div className={styles.statRow}>
              <div className={styles.statCard}><span className={styles.statNum}>{data.student_count}</span><span className={styles.statLbl}>students</span></div>
              <div className={`${styles.statCard} ${data.at_risk_count > 0 ? styles.statAtRisk : ''}`}>
                <span className={styles.statNum}>{data.at_risk_count}</span><span className={styles.statLbl}>need attention</span>
              </div>
            </div>

            {data.common_weak_areas.length > 0 && (
              <div className={styles.weakBlock}>
                <div className={styles.weakTitle}>Most common weak areas across the cohort</div>
                <div className={styles.weakTags}>
                  {data.common_weak_areas.map((w) => (
                    <span key={w.area} className={styles.weakTag}>{w.area}<em>×{w.count}</em></span>
                  ))}
                </div>
              </div>
            )}

            <div className={styles.list}>
              {data.students.map((s) => (
                <div key={s.student} className={`${styles.studentCard} ${s.at_risk ? styles.atRiskCard : ''}`}>
                  <button className={styles.studentHead} onClick={() => setOpen(open === s.student ? null : s.student)}>
                    <div className={styles.studentName}>
                      {s.at_risk && <span className={styles.riskDot} title="Needs attention">●</span>}
                      {s.student}
                    </div>
                    <div className={styles.studentMeta}>
                      {s.band && <span className={`${styles.band} ${styles[BAND_CLASS[s.band] || 'bandDeveloping']}`}>{s.band}</span>}
                      <span className={styles.sessionCount}>{s.session_count} session(s)</span>
                      <span className={styles.chevron}>{open === s.student ? '▾' : '▸'}</span>
                    </div>
                  </button>
                  {open === s.student && (
                    <div className={styles.sessions}>
                      {s.sessions.map((ses) => (
                        <div key={ses.debate_id} className={styles.sessionRow}>
                          <span className={styles.sessionTitle}>{ses.title}</span>
                          <span className={styles.sessionRight}>
                            {ses.band && <span className={`${styles.bandMini} ${styles[BAND_CLASS[ses.band] || 'bandDeveloping']}`}>{ses.band}</span>}
                            <span className={styles.sessionAnswers}>{ses.answer_count} ans</span>
                            <button className={styles.openBtn} onClick={() => router.push(`/room?debate_id=${ses.debate_id}&tab=certificate`)}>Open</button>
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </>
  );
}
