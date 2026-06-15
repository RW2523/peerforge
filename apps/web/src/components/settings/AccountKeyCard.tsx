'use client';

/**
 * AccountKeyCard
 * ─────────────────────────────────────────────────────────────────────────
 * Manages the OpenRouter key stored on the user's ACCOUNT (encrypted
 * server-side). Once connected, every device the user signs in from works
 * without re-pasting the key — the backend resolves it automatically when
 * a request doesn't carry one.
 *
 * Distinct from the browser-local key (ManagementKeyCard / keyStore):
 * a locally entered key always takes precedence for the current browser.
 */

import { useState, useEffect } from 'react';
import * as api from '@/lib/api';

export function AccountKeyCard() {
  const [status, setStatus] = useState<api.AccountKeyStatus | null>(null);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api.getAccountOpenRouterKey().then(setStatus).catch(() => setStatus({ connected: false, masked: null }));
  }, []);

  const handleSave = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const s = await api.saveAccountOpenRouterKey(input.trim());
      setStatus(s);
      setInput('');
      setNotice('Key connected to your account. It now works on every device you sign in from.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save key');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Remove the OpenRouter key from your account?')) return;
    setBusy(true);
    setError(null);
    try {
      const s = await api.deleteAccountOpenRouterKey();
      setStatus(s);
      setNotice('Key removed from your account.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to remove key');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{
      background: 'var(--surface-1)',
      border: '1px solid var(--border-soft)',
      borderRadius: 12,
      padding: '20px 24px',
      marginBottom: 24,
    }}>
      <h3 style={{ margin: '0 0 4px', fontSize: '1.02rem' }}>🔐 Account API Key</h3>
      <p style={{ margin: '0 0 14px', fontSize: '0.85rem', color: 'var(--text-2)', lineHeight: 1.5 }}>
        Store your OpenRouter key on your account (encrypted at rest). It is used
        automatically whenever this browser hasn&apos;t got a local key — and follows
        you across devices. The full key is never shown again after saving.
      </p>

      {error && (
        <div style={{ color: '#d64545', fontSize: '0.84rem', marginBottom: 10 }}>⚠ {error}</div>
      )}
      {notice && (
        <div style={{ color: '#1e9e57', fontSize: '0.84rem', marginBottom: 10 }}>✓ {notice}</div>
      )}

      {status?.connected ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <code style={{
            background: 'var(--surface-2)', padding: '6px 12px', borderRadius: 6,
            fontSize: '0.86rem',
          }}>{status.masked}</code>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>Connected</span>
          <button
            onClick={handleDelete}
            disabled={busy}
            style={{
              background: 'transparent', border: '1px solid rgba(255,107,107,0.5)',
              color: '#d64545', borderRadius: 8, padding: '7px 14px',
              fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer',
            }}
          >
            Remove
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <input
            type="password"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="sk-or-…"
            style={{
              flex: 1, minWidth: 220, padding: '9px 12px',
              border: '1px solid var(--border-medium)', borderRadius: 8,
              background: 'var(--surface-0)', color: 'inherit', fontSize: '0.88rem',
            }}
          />
          <button
            onClick={handleSave}
            disabled={busy || !input.trim().startsWith('sk-or-')}
            style={{
              background: 'var(--accent)', color: '#fff', border: 'none',
              borderRadius: 8, padding: '9px 18px', fontSize: '0.86rem',
              fontWeight: 600, cursor: 'pointer',
              opacity: busy || !input.trim().startsWith('sk-or-') ? 0.55 : 1,
            }}
          >
            {busy ? 'Saving…' : 'Connect to Account'}
          </button>
        </div>
      )}
    </div>
  );
}
