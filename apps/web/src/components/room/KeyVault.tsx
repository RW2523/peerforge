'use client';

import { useRouter } from 'next/navigation';
import Modal from '@/components/ui/Modal';
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
    <Modal open={isOpen} onClose={onClose} title="OpenRouter API Key Required">
      <p className={styles.subtitle}>Configure in Settings</p>

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
    </Modal>
  );
}
