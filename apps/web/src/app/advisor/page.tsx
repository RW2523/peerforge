'use client';

/**
 * Advisor — multi-student readiness console (Phase 3 / M7 / B2).
 *
 * The view a supervisor or program coordinator uses: every student in the
 * department, their average readiness band, an at-risk flag for who needs
 * attention, the cohort's most common weak areas, and a drill-down into each
 * student's individual sessions (each links to its signed certificate).
 * Departments partition the cohort; invites bring members in with a role.
 */
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import {
  createDepartment,
  createInvite,
  Department,
  getStudentsOverview,
  InviteResult,
  listDepartments,
  setDebateDepartment,
  StudentsOverview,
} from '@/lib/api';
import { useMe } from '@/lib/workspace';
import styles from './advisor.module.css';

const WORKSPACE_ID = '00000000-0000-0000-0000-000000000101';

const BAND_CLASS: Record<string, string> = {
  Strong: 'bandStrong', Competent: 'bandCompetent',
  Developing: 'bandDeveloping', 'Under-prepared': 'bandUnder',
};

export default function AdvisorPage() {
  const router = useRouter();
  const { me } = useMe();
  const canDepartments = me?.plan?.features?.departments ?? true;
  const canInvites = me?.plan?.features?.invites ?? true;
  const [data, setData] = useState<StudentsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [deptFilter, setDeptFilter] = useState<string>('');
  const [newDept, setNewDept] = useState('');
  const [inviteRole, setInviteRole] = useState<'student' | 'advisor'>('student');
  const [invite, setInvite] = useState<InviteResult | null>(null);
  const [toolError, setToolError] = useState<string | null>(null);

  const load = useCallback(() => {
    getStudentsOverview(WORKSPACE_ID, deptFilter || undefined)
      .then(setData)
      .catch((e) => setError(String(e?.message || e)));
  }, [deptFilter]);

  const loadDepartments = useCallback(() => {
    listDepartments(WORKSPACE_ID)
      .then((r) => setDepartments(r.departments))
      .catch(() => setDepartments([]));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadDepartments(); }, [loadDepartments]);

  const handleCreateDept = async () => {
    const name = newDept.trim();
    if (!name) return;
    setToolError(null);
    try {
      await createDepartment(WORKSPACE_ID, name);
      setNewDept('');
      loadDepartments();
    } catch (e) {
      setToolError(String((e as Error)?.message || e));
    }
  };

  const handleInvite = async () => {
    setToolError(null);
    setInvite(null);
    try {
      setInvite(await createInvite(WORKSPACE_ID, inviteRole));
    } catch (e) {
      setToolError(String((e as Error)?.message || e));
    }
  };

  const handleAssignDept = async (debateId: string, departmentId: string) => {
    setToolError(null);
    try {
      await setDebateDepartment(debateId, departmentId || null);
      load();
      loadDepartments();
    } catch (e) {
      setToolError(String((e as Error)?.message || e));
    }
  };

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

        <div className={styles.toolbar}>
          <label className={styles.toolItem}>
            Department
            <select
              className={styles.toolSelect}
              value={deptFilter}
              onChange={(e) => setDeptFilter(e.target.value)}
            >
              <option value="">All departments</option>
              {departments.map((d) => (
                <option key={d.department_id} value={d.department_id}>
                  {d.name} ({d.session_count})
                </option>
              ))}
            </select>
          </label>
          {canDepartments ? (
            <div className={styles.toolItem}>
              <input
                className={styles.toolInput}
                placeholder="New department…"
                value={newDept}
                onChange={(e) => setNewDept(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleCreateDept(); }}
              />
              <button className={styles.toolBtn} onClick={handleCreateDept} disabled={!newDept.trim()}>
                Add
              </button>
            </div>
          ) : null}
          {canInvites ? (
            <div className={styles.toolItem}>
              <select
                className={styles.toolSelect}
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as 'student' | 'advisor')}
              >
                <option value="student">Invite a student</option>
                <option value="advisor">Invite an advisor</option>
              </select>
              <button className={styles.toolBtn} onClick={handleInvite}>Create invite</button>
            </div>
          ) : null}
          {(!canDepartments || !canInvites) && (
            <Link href="/billing" className={styles.upgradePill}>
              🔒 Departments &amp; invites are an Institution feature — upgrade
            </Link>
          )}
        </div>
        {toolError && <div className={styles.toolError}>{toolError}</div>}
        {invite && (
          <div className={styles.inviteBox}>
            <span className={styles.inviteLabel}>
              {invite.role} invite — expires {new Date(invite.expires_at).toLocaleDateString()}. Share this token; it is
              redeemed once via <code>POST /invites/&#123;token&#125;/accept</code>:
            </span>
            <input
              className={styles.inviteToken}
              readOnly
              value={invite.invite_token}
              onFocus={(e) => e.target.select()}
            />
          </div>
        )}

        {error ? (
          <div className={styles.state}>Could not load: {error}</div>
        ) : !data ? (
          <div className={styles.state}>Loading cohort…</div>
        ) : data.student_count === 0 ? (
          <div className={styles.state}>
            {deptFilter
              ? 'No assessed sessions in this department yet. Assign sessions to it from a student drill-down.'
              : 'No assessed students yet. Tag sessions with a student name and run an assessment to populate this view.'}
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
                            <select
                              className={styles.deptSelect}
                              value={ses.department_id ?? ''}
                              onChange={(e) => handleAssignDept(ses.debate_id, e.target.value)}
                              title="Department"
                            >
                              <option value="">No department</option>
                              {departments.map((d) => (
                                <option key={d.department_id} value={d.department_id}>{d.name}</option>
                              ))}
                            </select>
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
