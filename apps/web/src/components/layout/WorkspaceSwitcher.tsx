'use client';

/**
 * Lets someone enrolled in several courses choose which one they are working
 * in. Hidden when there is nothing to choose between.
 */
import { useWorkspace } from '@/components/WorkspaceProvider';
import styles from './WorkspaceSwitcher.module.css';

export default function WorkspaceSwitcher() {
  const { workspaceId, workspaces, switchWorkspace, loading } = useWorkspace();

  if (loading || workspaces.length < 2) return null;

  return (
    <label className={styles.wrap}>
      <span className={styles.srOnly}>Active course</span>
      <select
        className={styles.select}
        value={workspaceId ?? ''}
        onChange={(e) => switchWorkspace(e.target.value)}
      >
        {workspaces.map((w) => (
          <option key={w.workspace_id} value={w.workspace_id}>
            {w.name || 'Untitled workspace'}
            {w.role ? ` · ${w.role}` : ''}
          </option>
        ))}
      </select>
    </label>
  );
}
