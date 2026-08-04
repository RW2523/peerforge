'use client';

import { useCallback, useEffect, useState } from 'react';
import AppNav from '@/components/layout/AppNav';
import { useWorkspace } from '@/components/WorkspaceProvider';
import {
  Course,
  CreatedInvitation,
  Invitation,
  OrgMember,
  OrgRole,
  Organization,
  Seats,
  createCourse,
  createInvitation,
  inviteBulk,
  getSeats,
  listCourses,
  listInvitations,
  listMembers,
  listMyOrganizations,
  removeMember,
  revokeInvitation,
  updateMemberRole,
  updateSeats,
} from '@/lib/organizations';
import styles from './organization.module.css';

const ROLE_LABEL: Record<OrgRole, string> = {
  org_admin: 'Administrator',
  professor: 'Professor',
  ta: 'Teaching assistant',
  student: 'Student',
};

export default function OrganizationPage() {
  const { switchWorkspace } = useWorkspace();

  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [orgId, setOrgId] = useState<string | null>(null);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [seats, setSeats] = useState<Seats | null>(null);
  // Mirrors the server value so the input always opens on the current
  // allocation, including after switching organization.
  const [seatInput, setSeatInput] = useState(0);

  useEffect(() => {
    if (seats) setSeatInput(seats.seats_purchased);
  }, [seats]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastInvite, setLastInvite] = useState<CreatedInvitation | null>(null);

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<OrgRole>('student');
  const [inviteCourse, setInviteCourse] = useState<string>('');
  const [courseName, setCourseName] = useState('');
  const [bulkEmails, setBulkEmails] = useState('');

  const myRole = orgs.find((o) => o.org_id === orgId)?.org_role ?? null;
  const isAdmin = myRole === 'org_admin';
  const canInvite = isAdmin || myRole === 'professor';

  const loadOrgs = useCallback(async () => {
    try {
      const data = await listMyOrganizations();
      setOrgs(data.organizations);
      setOrgId((current) => current ?? data.organizations[0]?.org_id ?? null);
    } catch (err: any) {
      setError(err?.message ?? 'Could not load your organizations');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOrgDetail = useCallback(async (id: string) => {
    setError(null);
    // Fetched together so one failing section doesn't blank the others.
    const [m, c, i, s] = await Promise.allSettled([
      listMembers(id),
      listCourses(id),
      listInvitations(id),
      getSeats(id),
    ]);
    if (m.status === 'fulfilled') setMembers(m.value.members);
    if (c.status === 'fulfilled') setCourses(c.value.courses);
    if (i.status === 'fulfilled') setInvites(i.value.invitations);
    if (s.status === 'fulfilled') setSeats(s.value);

    const failed = [m, c, i, s].find((r) => r.status === 'rejected');
    if (failed && failed.status === 'rejected') {
      setError(String(failed.reason?.message ?? failed.reason));
    }
  }, []);

  useEffect(() => {
    loadOrgs();
  }, [loadOrgs]);

  useEffect(() => {
    if (orgId) loadOrgDetail(orgId);
  }, [orgId, loadOrgDetail]);

  const act = async (fn: () => Promise<unknown>, success: string) => {
    setError(null);
    setNotice(null);
    try {
      await fn();
      setNotice(success);
      if (orgId) await loadOrgDetail(orgId);
    } catch (err: any) {
      setError(err?.message ?? 'That did not work');
    }
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgId || !inviteEmail.trim()) return;
    setError(null);
    setNotice(null);
    try {
      const created = await createInvitation(
        orgId,
        inviteEmail.trim(),
        inviteRole,
        inviteCourse || null
      );
      setLastInvite(created);
      setInviteEmail('');
      setNotice(
        created.email_delivered
          ? `Invitation emailed to ${created.email}.`
          : `Invitation created. Email isn't configured, so send them the link below.`
      );
      await loadOrgDetail(orgId);
    } catch (err: any) {
      setError(err?.message ?? 'Could not create the invitation');
    }
  };

  if (loading) {
    return (
      <>
        <AppNav />
        <main className={styles.wrap}>
          <p role="status" aria-live="polite">Loading your organizations…</p>
        </main>
      </>
    );
  }

  if (!orgs.length) {
    return (
      <>
        <AppNav />
        <main className={styles.wrap}>
          <div className={styles.empty}>
            <h1 className={styles.h1}>No organization yet</h1>
            <p className={styles.muted}>
              Organizations let a university run courses, enrol students, and see
              cohort progress. Ask an administrator for an invitation, or create one.
            </p>
            <CreateOrgForm onCreated={loadOrgs} />
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
            <h1 className={styles.h1}>
              {orgs.find((o) => o.org_id === orgId)?.name ?? 'Organization'}
            </h1>
            <p className={styles.muted}>
              You are {ROLE_LABEL[myRole ?? 'student'].toLowerCase()} here.
            </p>
          </div>
          {orgs.length > 1 && (
            <label className={styles.field}>
              <span className={styles.label}>Organization</span>
              <select
                value={orgId ?? ''}
                onChange={(e) => setOrgId(e.target.value)}
                className={styles.select}
              >
                {orgs.map((o) => (
                  <option key={o.org_id} value={o.org_id}>{o.name}</option>
                ))}
              </select>
            </label>
          )}
        </header>

        {error && <div className={styles.error} role="alert">{error}</div>}
        {notice && <div className={styles.notice} role="status">{notice}</div>}

        {seats && (
          <section className={styles.card}>
            <h2 className={styles.h2}>Seats</h2>
            <p className={styles.seatLine}>
              <strong>{seats.seats_used}</strong> in use
              {/* Outstanding invitations hold seats too. Showing only
                  seats_used advertised capacity the next invite would refuse. */}
              {(seats.seats_pending ?? 0) > 0 && (
                <>, <strong>{seats.seats_pending}</strong> awaiting acceptance</>
              )}
              {seats.seats_purchased > 0
                ? <> of <strong>{seats.seats_purchased}</strong> on the {seats.plan} plan</>
                : <> — unlimited while on {seats.plan}</>}
            </p>
            {seats.billable_roles && seats.billable_roles.length > 0 && (
              <p className={styles.muted}>
                Only {seats.billable_roles.join(' and ')} accounts use a seat —
                professors, TAs and administrators are free.
              </p>
            )}
            {isAdmin && (
              <form
                className={styles.inline}
                onSubmit={(e) => {
                  e.preventDefault();
                  act(() => updateSeats(orgId!, seatInput), `Seat allocation set to ${seatInput}.`);
                }}
              >
                <label className={styles.field}>
                  <span className={styles.label}>Seats</span>
                  {/* Controlled, and synced when the organization changes.
                      defaultValue only applies on first mount, so switching
                      organization left the previous number in the box — and
                      before seats had loaded it showed 0, one Update click
                      away from wiping the allocation. */}
                  <input
                    name="seats"
                    type="number"
                    min={0}
                    value={seatInput}
                    onChange={(e) => setSeatInput(Number(e.target.value) || 0)}
                    className={styles.input}
                  />
                </label>
                <button
                  className={styles.button}
                  type="submit"
                  disabled={seatInput === seats.seats_purchased}
                >
                  Update
                </button>
              </form>
            )}
          </section>
        )}

        <section className={styles.card}>
          <h2 className={styles.h2}>Courses</h2>
          {courses.length === 0 ? (
            <p className={styles.muted}>No courses yet.</p>
          ) : (
            <ul className={styles.list}>
              {courses.map((c) => (
                <li key={c.workspace_id} className={styles.row}>
                  <div>
                    <div className={styles.rowTitle}>{c.name}</div>
                    {c.description && <div className={styles.muted}>{c.description}</div>}
                  </div>
                  <button
                    className={styles.buttonGhost}
                    onClick={() => {
                      switchWorkspace(c.workspace_id);
                      setNotice(`Now working in ${c.name}.`);
                    }}
                  >
                    Switch to this course
                  </button>
                </li>
              ))}
            </ul>
          )}

          {canInvite && (
            <form
              className={styles.inline}
              onSubmit={(e) => {
                e.preventDefault();
                if (!courseName.trim()) return;
                act(
                  () => createCourse(orgId!, courseName.trim()),
                  `Created ${courseName.trim()}.`
                ).then(() => setCourseName(''));
              }}
            >
              <label className={styles.field}>
                <span className={styles.label}>New course name</span>
                <input
                  value={courseName}
                  onChange={(e) => setCourseName(e.target.value)}
                  placeholder="Research Methods"
                  className={styles.input}
                />
              </label>
              <button className={styles.button} type="submit">Create course</button>
            </form>
          )}
        </section>

        {canInvite && (
          <section className={styles.card}>
            <h2 className={styles.h2}>Invite someone</h2>
            <form className={styles.inline} onSubmit={handleInvite}>
              <label className={styles.field}>
                <span className={styles.label}>Email</span>
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="student@university.edu"
                  className={styles.input}
                />
              </label>
              <label className={styles.field}>
                <span className={styles.label}>Role</span>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as OrgRole)}
                  className={styles.select}
                >
                  <option value="student">Student</option>
                  <option value="ta">Teaching assistant</option>
                  {isAdmin && <option value="professor">Professor</option>}
                  {isAdmin && <option value="org_admin">Administrator</option>}
                </select>
              </label>
              <label className={styles.field}>
                <span className={styles.label}>Course (optional)</span>
                <select
                  value={inviteCourse}
                  onChange={(e) => setInviteCourse(e.target.value)}
                  className={styles.select}
                >
                  <option value="">Organization only</option>
                  {courses.map((c) => (
                    <option key={c.workspace_id} value={c.workspace_id}>{c.name}</option>
                  ))}
                </select>
              </label>
              <button className={styles.button} type="submit">Send invitation</button>
            </form>

            <details className={styles.details}>
              <summary className={styles.summary}>Invite a whole class</summary>
              <form
                className={styles.bulkForm}
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (!orgId || !bulkEmails.trim()) return;
                  setError(null);
                  setNotice(null);
                  try {
                    const res = await inviteBulk(orgId, bulkEmails, inviteRole, inviteCourse || null);
                    const parts = Object.entries(res.counts)
                      .map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`)
                      .join(', ');
                    setNotice(`${res.submitted} address(es) processed — ${parts}.`);
                    setBulkEmails('');
                    await loadOrgDetail(orgId);
                  } catch (err: any) {
                    setError(err?.message ?? 'Bulk invitation failed');
                  }
                }}
              >
                <label className={styles.field}>
                  <span className={styles.label}>
                    Paste addresses — commas, semicolons or one per line
                  </span>
                  <textarea
                    className={styles.textarea}
                    rows={4}
                    value={bulkEmails}
                    onChange={(e) => setBulkEmails(e.target.value)}
                    placeholder={'alice@university.edu\nbob@university.edu'}
                  />
                </label>
                <p className={styles.muted}>
                  Uses the role and course selected above. Duplicates and existing
                  members are skipped.
                </p>
                <button className={styles.button} type="submit">Invite everyone</button>
              </form>
            </details>

            {lastInvite && !lastInvite.email_delivered && (
              <div className={styles.linkBox}>
                <span className={styles.label}>Share this link</span>
                <code className={styles.code}>{lastInvite.invite_url}</code>
                <button
                  className={styles.buttonGhost}
                  onClick={() => navigator.clipboard?.writeText(lastInvite.invite_url)}
                >
                  Copy
                </button>
              </div>
            )}

            {invites.length > 0 && (
              <ul className={styles.list}>
                {invites.slice(0, 12).map((i) => (
                  <li key={i.invite_id} className={styles.row}>
                    <div>
                      <div className={styles.rowTitle}>{i.email}</div>
                      <div className={styles.muted}>
                        {ROLE_LABEL[i.role]} · <span className={styles[i.state]}>{i.state}</span>
                      </div>
                    </div>
                    {i.state === 'pending' && (
                      <button
                        className={styles.buttonGhost}
                        onClick={() =>
                          act(() => revokeInvitation(orgId!, i.invite_id), 'Invitation revoked.')
                        }
                      >
                        Revoke
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        <section className={styles.card}>
          <h2 className={styles.h2}>People ({members.length})</h2>
          <ul className={styles.list}>
            {members.map((m) => (
              <li key={m.user_id} className={styles.row}>
                <div>
                  <div className={styles.rowTitle}>
                    {m.display_name || m.email || 'Unnamed member'}
                  </div>
                  <div className={styles.muted}>
                    {m.email ? `${m.email} · ` : ''}{ROLE_LABEL[m.role]}
                  </div>
                </div>
                {isAdmin && (
                  <div className={styles.rowActions}>
                    <select
                      value={m.role}
                      onChange={(e) =>
                        act(
                          () => updateMemberRole(orgId!, m.user_id, e.target.value as OrgRole),
                          'Role updated.'
                        )
                      }
                      className={styles.select}
                      aria-label={`Role for ${m.user_id}`}
                    >
                      {(Object.keys(ROLE_LABEL) as OrgRole[]).map((r) => (
                        <option key={r} value={r}>{ROLE_LABEL[r]}</option>
                      ))}
                    </select>
                    <button
                      className={styles.buttonGhost}
                      onClick={() =>
                        act(() => removeMember(orgId!, m.user_id), 'Member removed.')
                      }
                    >
                      Remove
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  );
}

function CreateOrgForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  return (
    <form
      className={styles.inline}
      onSubmit={async (e) => {
        e.preventDefault();
        if (!name.trim() || busy) return;
        setBusy(true);
        setErr(null);
        try {
          const { createOrganization } = await import('@/lib/organizations');
          await createOrganization(name.trim());
          onCreated();
        } catch (error: any) {
          setErr(error?.message ?? 'Could not create the organization');
        } finally {
          setBusy(false);
        }
      }}
    >
      <label className={styles.field}>
        <span className={styles.label}>Institution name</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="University of Somewhere"
          className={styles.input}
        />
      </label>
      <button className={styles.button} type="submit" disabled={busy}>
        {busy ? 'Creating…' : 'Create organization'}
      </button>
      {err && <span className={styles.error} role="alert">{err}</span>}
    </form>
  );
}
