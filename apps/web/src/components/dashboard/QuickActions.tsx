'use client';

import Link from 'next/link';
import styles from './QuickActions.module.css';

export default function QuickActions() {
  return (
    <div className={styles.container}>
      <h2>Quick Actions</h2>
      <div className={styles.grid}>
        <Link href="/setup" className={styles.action}>
          <div className={styles.actionIcon}>⚙️</div>
          <div className={styles.actionContent}>
            <h3>Advanced Setup</h3>
            <p>Configure participants, materials, and AI agents</p>
          </div>
          <div className={styles.actionArrow}>→</div>
        </Link>

        <Link href="/settings" className={styles.action}>
          <div className={styles.actionIcon}>🔑</div>
          <div className={styles.actionContent}>
            <h3>OpenRouter Settings</h3>
            <p>Manage your API key and view account info</p>
          </div>
          <div className={styles.actionArrow}>→</div>
        </Link>

        <Link href="/operator" className={styles.action}>
          <div className={styles.actionIcon}>🎛️</div>
          <div className={styles.actionContent}>
            <h3>Operator Console</h3>
            <p>Legacy control interface for debates</p>
          </div>
          <div className={styles.actionArrow}>→</div>
        </Link>
      </div>
    </div>
  );
}
