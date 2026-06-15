'use client';

import { useRouter } from 'next/navigation';
import styles from './KeyVault.module.css';

interface KeyVaultProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function KeyVault({ isOpen, onClose }: KeyVaultProps) {
  const router = useRouter();

  const handleGoToSettings = () => {
    onClose();
    router.push('/settings');
  };

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div>
            <h2>OpenRouter API Key Required</h2>
            <p className={styles.subtitle}>Configure in Settings</p>
          </div>
          <button className={styles.closeBtn} onClick={onClose}>
            ✕
          </button>
        </div>

        <div className={styles.content}>
          <div className={styles.infoBox}>
            <p><strong>You need to set your OpenRouter API key first.</strong></p>
            <p>Your key enables:</p>
            <ul>
              <li>Loading the model catalog</li>
              <li>Generating persona drafts</li>
              <li>Creating meeting summaries</li>
            </ul>
          </div>

          <div className={styles.securityNote}>
            <span className={styles.icon}>🔒</span>
            <div>
              <strong>Security Promise</strong>
              <p>Your API key is never stored on our servers. It stays in your browser only.</p>
            </div>
          </div>

          <div className={styles.actions}>
            <button className={styles.btnPrimary} onClick={handleGoToSettings}>
              Go to Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
