'use client';

/**
 * Onboarding — shown once after sign-up.
 *
 * Single, skippable step: connect an OpenRouter API key to the account.
 * The key powers every AI feature (review panels, practice Q&A, reports,
 * assessments) and is stored encrypted server-side, so it follows the
 * account across devices. Skipping is fine — the app reminds the user in
 * Settings when a key is needed.
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import * as api from '@/lib/api';

export default function OnboardingPage() {
  const router = useRouter();
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConnect = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.saveAccountOpenRouterKey(input.trim());
      router.push('/setup');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to connect key');
      setBusy(false);
    }
  };

  return (
    <>
      <AppNav />
      <main style={{
        maxWidth: 560, margin: '60px auto', padding: '0 24px',
      }}>
        <div style={{
          background: 'var(--surface-1)', border: '1px solid var(--border-soft)',
          borderRadius: 14, padding: '36px 36px 28px',
        }}>
          <div style={{ fontSize: '2rem', marginBottom: 10 }}>🔑</div>
          <h1 style={{ margin: '0 0 8px', fontSize: '1.4rem' }}>Connect your OpenRouter key</h1>
          <p style={{ margin: '0 0 20px', color: 'var(--text-2)', fontSize: '0.92rem', lineHeight: 1.6 }}>
            PeerForge runs every AI feature — review panels, practice Q&amp;A,
            feedback reports, assessments — on <strong>your own</strong> OpenRouter
            account, so you control cost and model choice. Your key is stored
            encrypted and never shown again in full.
          </p>
          <p style={{ margin: '0 0 20px', fontSize: '0.84rem', color: 'var(--text-2)' }}>
            No key yet? Create one in two minutes at{' '}
            <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer"
               style={{ color: 'var(--accent)', fontWeight: 600 }}>
              openrouter.ai/keys
            </a>. A few dollars of credit covers many practice sessions in Light mode.
          </p>

          {error && (
            <div style={{ color: '#d64545', fontSize: '0.85rem', marginBottom: 12 }}>⚠ {error}</div>
          )}

          <input
            type="password"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="sk-or-…"
            style={{
              width: '100%', boxSizing: 'border-box', padding: '11px 14px',
              border: '1px solid var(--border-medium)', borderRadius: 8,
              background: 'var(--surface-0)', color: 'inherit',
              fontSize: '0.92rem', marginBottom: 14,
            }}
          />

          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <button
              onClick={handleConnect}
              disabled={busy || !input.trim().startsWith('sk-or-')}
              style={{
                background: 'var(--accent)', color: '#fff', border: 'none',
                borderRadius: 8, padding: '11px 24px', fontSize: '0.92rem',
                fontWeight: 700, cursor: 'pointer',
                opacity: busy || !input.trim().startsWith('sk-or-') ? 0.55 : 1,
              }}
            >
              {busy ? 'Connecting…' : 'Connect & Continue'}
            </button>
            <button
              onClick={() => router.push('/setup')}
              style={{
                background: 'transparent', border: 'none', color: 'var(--text-2)',
                fontSize: '0.86rem', cursor: 'pointer', textDecoration: 'underline',
              }}
            >
              Skip for now
            </button>
          </div>
          <p style={{ margin: '16px 0 0', fontSize: '0.76rem', color: 'var(--text-2)' }}>
            You can connect or change the key any time in Settings.
          </p>
        </div>
      </main>
    </>
  );
}
