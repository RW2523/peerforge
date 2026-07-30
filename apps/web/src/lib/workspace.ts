/**
 * Active workspace selection.
 *
 * The server treats X-Workspace-Id as a *selector* over the workspaces the
 * caller belongs to — it never grants access — so persisting a stale or
 * tampered id here is safe: the API rejects it with a 403.
 */
const STORAGE_KEY = 'peerforge_active_workspace_id';

let activeWorkspaceId: string | null = null;

export function getActiveWorkspaceId(): string | null {
  if (activeWorkspaceId) return activeWorkspaceId;
  if (typeof window === 'undefined') return null;
  try {
    activeWorkspaceId = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    // Private browsing or storage disabled — fall back to memory only.
  }
  return activeWorkspaceId;
}

export function setActiveWorkspaceId(workspaceId: string | null): void {
  activeWorkspaceId = workspaceId;
  if (typeof window === 'undefined') return;
  try {
    if (workspaceId) {
      window.localStorage.setItem(STORAGE_KEY, workspaceId);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Non-fatal: the id still lives in module state for this session.
  }
}

export interface WorkspaceMembership {
  workspace_id: string;
  name: string | null;
  role: string | null;
  tenant_id: string | null;
  is_active: boolean;
}
