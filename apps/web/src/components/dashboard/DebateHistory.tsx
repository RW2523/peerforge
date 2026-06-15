'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import * as api from '@/lib/api';
import styles from './DebateHistory.module.css';

interface DebateHistoryProps {
  workspaceId: string;
  refreshTrigger?: number;
}

export default function DebateHistory({ workspaceId, refreshTrigger }: DebateHistoryProps) {
  const router = useRouter();
  const [debates, setDebates] = useState<api.DebateListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDebates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, refreshTrigger]);

  const loadDebates = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.listDebates(workspaceId, 20);
      setDebates(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load debates');
    } finally {
      setLoading(false);
    }
  };

  const getStateBadgeClass = (state: string) => {
    switch (state) {
      case 'pending':
        return styles.badgePending;
      case 'running':
        return styles.badgeRunning;
      case 'paused':
        return styles.badgePaused;
      case 'ended':
        return styles.badgeEnded;
      default:
        return styles.badgePending;
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const getStateLabel = (state: string) => {
    switch (state) {
      case 'pending': return 'Draft';
      case 'running': return 'Live';
      case 'paused': return 'Paused';
      case 'ended': return 'Complete';
      default: return state;
    }
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <h2>History</h2>
        <div className={styles.loading}>Loading debates...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <h2>History</h2>
        <div className={styles.error}>
          <span>⚠</span>
          <span>{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <h2>History</h2>
      
      {debates.length === 0 ? (
        <div className={styles.empty}>
          <p>No debates yet</p>
          <p className={styles.emptyHint}>Create your first debate above to get started</p>
        </div>
      ) : (
        <div className={styles.list}>
          {debates.map((debate) => (
            <div key={debate.debate_id} className={styles.item}>
              <div className={styles.itemHeader}>
                <div className={styles.itemTitle}>
                  <h3>{debate.title}</h3>
                  <span className={`${styles.badge} ${getStateBadgeClass(debate.state)}`}>
                    {getStateLabel(debate.state)}
                  </span>
                </div>
              </div>
              <div className={styles.itemMeta}>
                <span className={styles.metaTime}>
                  {formatDate(debate.updated_at || debate.created_at)}
                </span>
                {debate.state === 'running' && (
                  <span className={styles.metaLive}>● Live now</span>
                )}
              </div>
              <div className={styles.itemActions}>
                <button
                  onClick={() => router.push(`/room?debate_id=${debate.debate_id}`)}
                  className={styles.btnSecondary}
                >
                  Continue
                </button>
                <button
                  onClick={() => router.push(`/operator?debate_id=${debate.debate_id}`)}
                  className={styles.btnTertiary}
                >
                  Operator
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
