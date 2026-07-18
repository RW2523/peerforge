'use client';

/**
 * Join — redeem a workspace invite.
 *
 * A student or advisor pastes the token an advisor sent them (or arrives via
 * /join?token=…). Redemption writes their workspace membership with the
 * invited role. Requires being signed in; single-use, expiry-checked.
 */
import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import { acceptInvite } from '@/lib/api';
import styles from './join.module.css';

function JoinInner() {
  const router = useRouter();
  const search = useSearchParams();
  const [token, setToken] = useState('');
  const [status, setStatus] = useState<'idle' | 'working' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    const t = search.get('token');
    if (t) setToken(t);
  }, [search]);

  const submit = async (value: string) => {
    const t = value.trim();
    if (!t) return;
    setStatus('working');
    setMessage(null);
    try {
      const result = await acceptInvite(t);
      setRole(result.role);
      setStatus('done');
    } catch (e) {
      setMessage(String((e as Error)?.message || e));
      setStatus('error');
    }
  };

  return (
    <>
      <AppNav />
      <main className={styles.page}>
        <div className={styles.card}>
          <h1 className={styles.title}>Join a workspace</h1>

          {status === 'done' ? (
            <>
              <p className={styles.success}>
                You&apos;ve joined as <strong>{role}</strong>. Welcome aboard.
              </p>
              <div className={styles.actions}>
                <button className={styles.primary} onClick={() => router.push(role === 'advisor' ? '/advisor' : '/')}>
                  Continue →
                </button>
              </div>
            </>
          ) : (
            <>
              <p className={styles.subtitle}>
                Paste the invite token your advisor sent you. You need to be signed in to accept it.
              </p>
              <input
                className={styles.input}
                placeholder="Invite token"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') submit(token); }}
                autoFocus
              />
              {status === 'error' && message && (
                <p className={styles.error}>{message}</p>
              )}
              <div className={styles.actions}>
                <button
                  className={styles.primary}
                  onClick={() => submit(token)}
                  disabled={!token.trim() || status === 'working'}
                >
                  {status === 'working' ? 'Joining…' : 'Accept invite'}
                </button>
                <Link href="/" className={styles.secondary}>Cancel</Link>
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}

export default function JoinPage() {
  return (
    <Suspense fallback={<div className={styles.page}>Loading…</div>}>
      <JoinInner />
    </Suspense>
  );
}
