'use client';

/**
 * Progress — cohort readiness dashboard (Phase 3).
 *
 * One table an advisor or program coordinator can scan: every session with an
 * assessment trajectory, its current band, how much it moved, how much
 * evidence sits behind it, and whether a signed certificate has been issued
 * (with a one-click jump to public verification).
 */
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import { getReadinessOverview, ReadinessOverviewSession } from '@/lib/api';
import styles from './progress.module.css';

const WORKSPACE_ID = '00000000-0000-0000-0000-000000000101';

const BAND_CLASS: Record<string, string> = {
  Strong: 'bandStrong',
  Competent: 'bandCompetent',
  Developing: 'bandDeveloping',
  'Under-prepared': 'bandUnder',
};

export default function ProgressPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<ReadinessOverviewSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReadinessOverview(WORKSPACE_ID)
      .then((r) => setSessions(r.sessions))
      .catch((e) => setError(String(e?.message || e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <header className={styles.header}>
          <div>
            <h1 className={styles.title}>Readiness Progress</h1>
            <p className={styles.subtitle}>
              Every session with an assessment trajectory — where each piece of research stands,
              how it has moved, and which sessions carry a signed, publicly verifiable certificate.
            </p>
          </div>
        </header>

        {loading ? (
          <div className={styles.state}>Loading readiness overview…</div>
        ) : error ? (
          <div className={styles.state}>Could not load overview: {error}</div>
        ) : sessions.length === 0 ? (
          <div className={styles.state}>
            No assessed sessions yet. Run a Practice Q&amp;A or a panel session — the 10-dimension
            assessment generates automatically and shows up here.
          </div>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Readiness</th>
                  <th>Trajectory</th>
                  <th>Evidence</th>
                  <th>Certificate</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.debate_id}>
                    <td className={styles.cellTitle}>
                      <div className={styles.sessionTitle}>{s.title}</div>
                      <div className={styles.sessionMeta}>
                        {s.last_assessed_at && `assessed ${new Date(s.last_assessed_at).toLocaleDateString()}`}
                      </div>
                    </td>
                    <td>
                      {s.band && (
                        <span className={`${styles.band} ${styles[BAND_CLASS[s.band] || 'bandDeveloping']}`}>
                          {s.band}
                        </span>
                      )}
                    </td>
                    <td className={styles.cellTraj}>
                      {s.first_score?.toFixed(1)} → <strong>{s.latest_score?.toFixed(1)}</strong>
                      {s.delta != null && s.delta !== 0 && (
                        <span className={s.delta > 0 ? styles.up : styles.down}>
                          {s.delta > 0 ? ` ▲+${s.delta.toFixed(1)}` : ` ▼${s.delta.toFixed(1)}`}
                        </span>
                      )}
                      <div className={styles.sessionMeta}>{s.assessment_count} assessment(s)</div>
                    </td>
                    <td className={styles.cellEvidence}>{s.answer_count} answer(s)</td>
                    <td>
                      {s.certificate_id ? (
                        <a className={styles.certLink} href={`/verify/${s.certificate_id}`} target="_blank" rel="noreferrer">
                          🔏 {s.certificate_id}
                        </a>
                      ) : (
                        <span className={styles.noCert}>not issued</span>
                      )}
                    </td>
                    <td>
                      <button
                        className={styles.openBtn}
                        onClick={() => router.push(`/room?debate_id=${s.debate_id}&tab=certificate`)}
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </>
  );
}
