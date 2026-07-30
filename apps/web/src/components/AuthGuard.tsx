'use client';

/**
 * Redirects signed-out visitors to /login.
 *
 * This is a usability boundary, not a security one — the API enforces access
 * on every request. Without it, protected pages render fully and then fail
 * each call, which reads to the user as the app being broken rather than as
 * needing to sign in.
 */
import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';

// Reachable without a session. /verify is deliberately public: anyone holding
// a certificate link must be able to check it.
const PUBLIC_PREFIXES = ['/login', '/logout', '/verify'];
const PUBLIC_EXACT = ['/'];

function isPublic(pathname: string): boolean {
  if (PUBLIC_EXACT.includes(pathname)) return true;
  return PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const devMode = process.env.NEXT_PUBLIC_AUTH_MODE === 'development';
  const [checked, setChecked] = useState(devMode);

  useEffect(() => {
    if (devMode || isPublic(pathname)) {
      setChecked(true);
      return;
    }

    let cancelled = false;

    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (cancelled) return;
        if (!data.session) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
          return;
        }
        setChecked(true);
      })
      .catch(() => {
        if (!cancelled) router.replace('/login');
      });

    return () => {
      cancelled = true;
    };
  }, [devMode, pathname, router]);

  if (!checked) {
    return (
      <div
        role="status"
        aria-live="polite"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '50vh',
          opacity: 0.7,
        }}
      >
        Checking your session…
      </div>
    );
  }

  return <>{children}</>;
}
