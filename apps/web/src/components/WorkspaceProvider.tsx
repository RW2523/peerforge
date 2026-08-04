'use client';

/**
 * Supplies the active workspace to the app.
 *
 * Every page used to hardcode a single workspace UUID, which meant the UI
 * could only ever address one tenant. This resolves the caller's real
 * memberships from the API instead.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { getMyWorkspaces } from '@/lib/api';
import { AUTH_DISABLED, supabase } from '@/lib/supabase';
import {
  getActiveWorkspaceId,
  setActiveWorkspaceId,
  WorkspaceMembership,
} from '@/lib/workspace';

interface WorkspaceContextValue {
  workspaceId: string | null;
  workspaces: WorkspaceMembership[];
  role: string | null;
  loading: boolean;
  error: string | null;
  switchWorkspace: (workspaceId: string) => void;
  reload: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue>({
  workspaceId: null,
  workspaces: [],
  role: null,
  loading: true,
  error: null,
  switchWorkspace: () => {},
  reload: () => {},
});

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [workspaces, setWorkspaces] = useState<WorkspaceMembership[]>([]);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getMyWorkspaces();
        if (cancelled) return;

        setWorkspaces(data.workspaces);

        // Keep the stored choice only while it is still a real membership.
        const stored = getActiveWorkspaceId();
        const storedIsValid = data.workspaces.some((w) => w.workspace_id === stored);
        const next =
          (storedIsValid ? stored : null) ??
          data.active_workspace_id ??
          data.workspaces[0]?.workspace_id ??
          null;

        setWorkspaceId(next);
        setActiveWorkspaceId(next);
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? 'Could not load your workspaces');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const switchWorkspace = useCallback((next: string) => {
    setWorkspaceId(next);
    setActiveWorkspaceId(next);
  }, []);

  const reload = useCallback(() => setReloadToken((n) => n + 1), []);

  // This provider sits in the root layout, so it mounts on the login page and
  // fetches once — before there is a session. Client-side navigation after
  // sign-in never remounts it, so without this the app landed on /setup still
  // holding the 401 from before anyone had signed in.
  useEffect(() => {
    // Nothing to listen for when the build has no sign-in: there is no session
    // to change, and subscribing points a Supabase client at a URL that is not
    // meant to be reachable.
    if (AUTH_DISABLED) return;

    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'SIGNED_IN' || event === 'SIGNED_OUT' || event === 'TOKEN_REFRESHED') {
        if (event === 'SIGNED_OUT') {
          setWorkspaces([]);
          setWorkspaceId(null);
        }
        reload();
      }
    });
    return () => data.subscription.unsubscribe();
  }, [reload]);

  const role = useMemo(
    () => workspaces.find((w) => w.workspace_id === workspaceId)?.role ?? null,
    [workspaces, workspaceId]
  );

  const value = useMemo(
    () => ({ workspaceId, workspaces, role, loading, error, switchWorkspace, reload }),
    [workspaceId, workspaces, role, loading, error, switchWorkspace, reload]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  return useContext(WorkspaceContext);
}
