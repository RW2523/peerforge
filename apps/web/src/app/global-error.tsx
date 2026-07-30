'use client';

import { useEffect } from 'react';

// Replaces the root layout when the layout itself throws, so it must render
// its own <html> and <body> and cannot rely on any app styling.
export default function GlobalError({
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
    <html lang="en">
      <body
        style={{
          fontFamily: 'system-ui, sans-serif',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          margin: 0,
          gap: '1rem',
          padding: '2rem',
          textAlign: 'center',
        }}
      >
        <h1 style={{ fontSize: '1.5rem', margin: 0 }}>PeerForge could not start</h1>
        <p style={{ maxWidth: '48ch', margin: 0, opacity: 0.75 }}>
          Something failed before the app could render. Reloading usually clears it.
        </p>
        {error.digest && (
          <code style={{ fontSize: '0.8rem', opacity: 0.6 }}>Reference: {error.digest}</code>
        )}
        <button
          onClick={reset}
          style={{
            padding: '0.5rem 1.25rem',
            borderRadius: '6px',
            border: '1px solid currentColor',
            background: 'transparent',
            color: 'inherit',
            cursor: 'pointer',
            font: 'inherit',
          }}
        >
          Reload
        </button>
      </body>
    </html>
  );
}
