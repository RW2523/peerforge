'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { acceptInvitation } from '@/lib/organizations';
import { setActiveWorkspaceId } from '@/lib/workspace';
import styles from './invite.module.css';

type Phase = 'accepting' | 'joined' | 'failed';

export default function AcceptInvitePage() {
  const params = useParams();
  const router = useRouter();
  const token = String(params?.token ?? '');

  const [phase, setPhase] = useState<Phase>('accepting');
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [result, setResult] = useState<{ workspace_id: string | null; role: string } | null>(null);

  const accept = useCallback(async () => {
    setPhase('accepting');
    setError(null);
    setStatus(null);
    try {
      const data = await acceptInvitation(token);
      // Land the user in the course they were invited to, not whichever
      // workspace happened to be active before.
      if (data.workspace_id) setActiveWorkspaceId(data.workspace_id);
      setResult({ workspace_id: data.workspace_id, role: data.role });
      setPhase('joined');
    } catch (err: any) {
      setError(err?.message ?? 'This invitation could not be accepted.');
      setStatus(typeof err?.status === 'number' ? err.status : null);
      setPhase('failed');
    }
  }, [token]);

  // An invitation is addressed to one person, so the usual "it expired" advice
  // is wrong when the real problem is that you are signed in as someone else.
  const wrongAccount = status === 403 || status === 401;

  useEffect(() => {
    if (token) accept();
  }, [token, accept]);

  return (
    <main className={styles.wrap}>
      <div className={styles.card}>
        {phase === 'accepting' && (
          <>
            <h1 className={styles.title}>Joining…</h1>
            <p className={styles.body} role="status" aria-live="polite">
              Checking your invitation.
            </p>
          </>
        )}

        {phase === 'joined' && (
          <>
            <h1 className={styles.title}>You&rsquo;re in</h1>
            <p className={styles.body}>
              You joined as <strong>{result?.role}</strong>.
              {result?.workspace_id
                ? ' Your course is ready.'
                : ' An administrator will add you to a course.'}
            </p>
            <div className={styles.actions}>
              <button className={styles.primary} onClick={() => router.push('/setup')}>
                Start a review session
              </button>
              <Link className={styles.secondary} href="/history">
                See your sessions
              </Link>
            </div>
          </>
        )}

        {phase === 'failed' && (
          <>
            <h1 className={styles.title}>This invitation didn&rsquo;t work</h1>
            <p className={styles.body}>{error}</p>
            {wrongAccount ? (
              <p className={styles.hint}>
                Invitations are tied to the email address they were sent to.
                Sign in with that address and open this link again.
              </p>
            ) : (
              <p className={styles.hint}>
                Invitations expire after a couple of weeks and can only be used once.
                Ask whoever invited you to send a new one.
              </p>
            )}
            <div className={styles.actions}>
              {wrongAccount ? (
                <Link className={styles.primary} href="/login">
                  Sign in as someone else
                </Link>
              ) : (
                <button className={styles.primary} onClick={accept}>
                  Try again
                </button>
              )}
              <Link className={styles.secondary} href="/">
                Go home
              </Link>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
