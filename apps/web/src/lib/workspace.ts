'use client';

/**
 * Workspace / identity resolution.
 *
 * `useMe()` fetches the signed-in user's workspace, role, and plan from the
 * API (`GET /me`) so pages stop hardcoding a workspace id. In local dev
 * (REQUIRE_AUTH=false) the API returns the fixed dev workspace as owner.
 */
import { useEffect, useState } from 'react';
import { getMe, Me } from './api';

// The dev/test workspace the API returns when auth is disabled. Kept as a
// fallback so pages render before /me resolves (and if it ever fails).
export const DEV_WORKSPACE_ID = '00000000-0000-0000-0000-000000000101';

export function useMe() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getMe()
      .then((m) => { if (alive) setMe(m); })
      .catch((e) => { if (alive) setError(String(e?.message || e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  return { me, loading, error, workspaceId: me?.workspace_id ?? DEV_WORKSPACE_ID };
}
