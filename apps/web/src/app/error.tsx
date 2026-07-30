'use client';

import Link from 'next/link';
import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        gap: '1rem',
        padding: '2rem',
        textAlign: 'center',
      }}
    >
      <h1 style={{ fontSize: '1.5rem', margin: 0 }}>This page hit an error</h1>
      <p style={{ maxWidth: '48ch', color: 'var(--text-secondary, #666)', margin: 0 }}>
        The rest of the app is still running. Try again, and if it keeps happening,
        reload the page or go back to the dashboard.
      </p>
      {error.digest && (
        <code style={{ fontSize: '0.8rem', opacity: 0.7 }}>Reference: {error.digest}</code>
      )}
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
        <button onClick={reset} style={buttonStyle}>
          Try again
        </button>
        <Link href="/" style={{ ...buttonStyle, textDecoration: 'none' }}>
          Go to dashboard
        </Link>
      </div>
    </main>
  );
}

const buttonStyle: React.CSSProperties = {
  padding: '0.5rem 1.25rem',
  borderRadius: '6px',
  border: '1px solid var(--border-medium, #ccc)',
  background: 'transparent',
  color: 'inherit',
  cursor: 'pointer',
  font: 'inherit',
};
