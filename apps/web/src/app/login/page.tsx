'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { signInWithPassword, signInWithMagicLink } from '@/lib/supabase';
import styles from './login.module.css';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [useMagicLink, setUseMagicLink] = useState(false);
  const [status, setStatus] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setStatus('Signing in...');
    
    try {
      await signInWithPassword(email, password);
      setStatus('Success! Redirecting...');
      router.push('/setup');
    } catch (err: any) {
      setStatus(`Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMagicLinkLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setStatus('Sending magic link...');
    
    try {
      await signInWithMagicLink(email);
      setStatus('Check your email for the magic link!');
    } catch (err: any) {
      setStatus(`Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.loginHeader}>
          <span className={styles.loginIcon}>🎓</span>
          <h1>PeerForge</h1>
        </div>
        <p className={styles.subtitle}>Sign in to your academic review workspace</p>

        <div className={styles.toggle}>
          <button
            className={!useMagicLink ? styles.active : ''}
            onClick={() => setUseMagicLink(false)}
            disabled={isLoading}
          >
            Password
          </button>
          <button
            className={useMagicLink ? styles.active : ''}
            onClick={() => setUseMagicLink(true)}
            disabled={isLoading}
          >
            Magic Link
          </button>
        </div>

        {!useMagicLink ? (
          <form onSubmit={handlePasswordLogin} className={styles.form}>
            <div className={styles.field}>
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                disabled={isLoading}
              />
            </div>

            <div className={styles.field}>
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                disabled={isLoading}
              />
            </div>

            <button type="submit" disabled={isLoading} className={styles.btn}>
              Sign In
            </button>
          </form>
        ) : (
          <form onSubmit={handleMagicLinkLogin} className={styles.form}>
            <div className={styles.field}>
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                disabled={isLoading}
              />
            </div>

            <button type="submit" disabled={isLoading} className={styles.btn}>
              Send Magic Link
            </button>
          </form>
        )}

        {status && (
          <div className={styles.status}>
            {status}
          </div>
        )}
      </div>
    </div>
  );
}
