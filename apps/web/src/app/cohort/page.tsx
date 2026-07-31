'use client';

/**
 * Cohort view.
 *
 * Answers the question a professor actually has: who is progressing, who has
 * started and stalled, and who has never turned up. People with no sessions
 * are listed first, because they are the ones needing action.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import AppNav from '@/components/layout/AppNav';
import {
  Cohort,
  CohortPerson,
  Course,
  Organization,
  getCohort,
  listCourses,
  listMyOrganizations,
} from '@/lib/organizations';
import styles from './cohort.module.css';

const SUPERVISORY = ['org_admin', 'professor', 'ta'];

export default function CohortPage() {
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [orgId, setOrgId] = useState<string | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [courseId, setCourseId] = useState<string>('');
  const [cohort, setCohort] = useState<Cohort | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const myRole = orgs.find((o) => o.org_id === orgId)?.org_role ?? null;
  const supervises = myRole ? SUPERVISORY.includes(myRole) : false;

  useEffect(() => {
    listMyOrganizations()
      .then((d) => {
        const supervising = d.organizations.filter((o) => SUPERVISORY.includes(o.org_role));
        setOrgs(d.organizations);
        setOrgId(supervising[0]?.org_id ?? d.organizations[0]?.org_id ?? null);
      })
      .catch((e: any) => setError(e?.message ?? 'Could not load your organizations'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!orgId) return;
    listCourses(orgId).then((d) => setCourses(d.courses)).catch(() => setCourses([]));
  }, [orgId]);

  const load = useCallback(async () => {
    if (!orgId) return;
    setError(null);
    try {
      setCohort(await getCohort(orgId, courseId || null));
    } catch (e: any) {
      setError(e?.message ?? 'Could not load the cohort');
      setCohort(null);
    }
  }, [orgId, courseId]);

  useEffect(() => {
    load();
  }, [load]);

  // Those needing attention first; the rest by activity.
  const people = useMemo(() => {
    if (!cohort) return [];
    return [...cohort.people].sort((a, b) => {
      if (a.not_started !== b.not_started) return a.not_started ? -1 : 1;
      return b.sessions - a.sessions;
    });
  }, [cohort]);

  if (loading) {
    return (
      <>
        <AppNav />
        <main className={styles.wrap}><p role="status">Loading…</p></main>
      </>
    );
  }

  if (!supervises) {
    return (
      <>
        <AppNav />
        <main className={styles.wrap}>
          <div className={styles.card}>
            <h1 className={styles.h1}>Cohort</h1>
            <p className={styles.muted}>
              Only professors, teaching assistants and administrators can see cohort
              progress. Your own sessions are under History.
            </p>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <AppNav />
      <main className={styles.wrap}>
        <header className={styles.head}>
          <div>
            <h1 className={styles.h1}>Cohort</h1>
            <p className={styles.muted}>Who is progressing, and who has not begun.</p>
          </div>
          <div className={styles.filters}>
            {orgs.length > 1 && (
              <label className={styles.field}>
                <span className={styles.label}>Organization</span>
                <select
                  className={styles.select}
                  value={orgId ?? ''}
                  onChange={(e) => setOrgId(e.target.value)}
                >
                  {orgs.map((o) => (
                    <option key={o.org_id} value={o.org_id}>{o.name}</option>
                  ))}
                </select>
              </label>
            )}
            <label className={styles.field}>
              <span className={styles.label}>Course</span>
              <select
                className={styles.select}
                value={courseId}
                onChange={(e) => setCourseId(e.target.value)}
              >
                <option value="">All courses</option>
                {courses.map((c) => (
                  <option key={c.workspace_id} value={c.workspace_id}>{c.name}</option>
                ))}
              </select>
            </label>
          </div>
        </header>

        {error && <div className={styles.error} role="alert">{error}</div>}

        {cohort && (
          <>
            <div className={styles.stats}>
              <Stat label="Students" value={cohort.summary.students} />
              <Stat
                label="Not started"
                value={cohort.summary.students_not_started}
                tone={cohort.summary.students_not_started > 0 ? 'warn' : 'ok'}
              />
              <Stat label="Invited, not joined" value={cohort.summary.invited_not_joined} />
              <Stat label="Sessions run" value={cohort.summary.sessions_total} />
            </div>

            <div className={styles.card}>
              {people.length === 0 ? (
                <p className={styles.muted}>Nobody here yet. Invite your class to begin.</p>
              ) : (
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Person</th>
                        <th>Role</th>
                        <th className={styles.num}>Sessions</th>
                        <th className={styles.num}>Score</th>
                        <th className={styles.num}>Change</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {people.map((p, i) => (
                        <Row key={p.user_id ?? `${p.email}-${i}`} person={p} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: 'ok' | 'warn' }) {
  return (
    <div className={styles.stat}>
      <span className={`${styles.statValue} ${tone === 'warn' ? styles.warn : ''}`}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  );
}

function Row({ person }: { person: CohortPerson }) {
  const status = person.invite_state
    ? person.invite_state === 'expired'
      ? 'Invitation expired'
      : 'Invited, not joined'
    : person.not_started
      ? 'Joined, no sessions'
      : 'Active';

  return (
    <tr className={person.not_started ? styles.attention : undefined}>
      <td>
        <div className={styles.name}>{person.display_name || person.email || '—'}</div>
        {person.email && person.display_name && (
          <div className={styles.sub}>{person.email}</div>
        )}
      </td>
      <td className={styles.sub}>{person.role.replace('_', ' ')}</td>
      <td className={styles.num}>{person.sessions}</td>
      <td className={styles.num}>{person.latest_score ?? '—'}</td>
      <td className={styles.num}>
        {person.score_delta === null || person.score_delta === undefined ? (
          '—'
        ) : (
          <span className={person.score_delta >= 0 ? styles.up : styles.down}>
            {person.score_delta >= 0 ? '+' : ''}
            {person.score_delta}
          </span>
        )}
      </td>
      <td className={styles.sub}>{status}</td>
    </tr>
  );
}
