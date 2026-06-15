'use client';

import { useState } from 'react';
import { KeyPersistence } from '@/lib/openrouterKeyStore';
import styles from './AccountInfoCard.module.css';

interface ManagementKeyCardProps {
  managementKey: string | null;
  managementPersistence: KeyPersistence | null;
  onSave: (key: string, persistence: KeyPersistence) => void;
  onClear: () => void;
}

export function ManagementKeyCard({
  managementKey,
  managementPersistence,
  onSave,
  onClear
}: ManagementKeyCardProps) {
  const [keyInput, setKeyInput] = useState('');
  const [selectedPersistence, setSelectedPersistence] = useState<KeyPersistence>('local');

  const handleSave = () => {
    const trimmedKey = keyInput.trim();
    if (!trimmedKey) return;

    onSave(trimmedKey, selectedPersistence);
    setKeyInput('');
  };

  return (
    <section className={styles.card}>
      <h2>Management API Key (Optional)</h2>
      <p className={styles.cardDesc}>
        Add a management key to view your account credits balance. Regular API keys cannot access credit information.
        <a 
          href="https://openrouter.ai/settings/management-keys" 
          target="_blank" 
          rel="noopener noreferrer"
          style={{ marginLeft: '8px', color: 'var(--accent)' }}
        >
          Create management key →
        </a>
      </p>

      {managementKey ? (
        <div className={styles.keyStatus}>
          <div className={styles.keyStatusHeader}>
            <span className={styles.keyIcon} />
            <div>
              <strong>Management Key Saved</strong>
              <p>
                Stored: <span className={styles.persistenceBadge}>{managementPersistence}</span>
              </p>
            </div>
          </div>
          <button onClick={onClear} className={styles.btnDanger}>
            Clear Management Key
          </button>
        </div>
      ) : (
        <div className={styles.form}>
          <label>
            Management API Key
            <input
              type="password"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              placeholder="sk-or-v1-..."
            />
          </label>

          <div className={styles.persistenceOptions}>
            <label className={styles.radio}>
              <input
                type="radio"
                name="mgmt-persistence"
                value="memory"
                checked={selectedPersistence === 'memory'}
                onChange={(e) => setSelectedPersistence(e.target.value as KeyPersistence)}
              />
              <div>
                <strong>Do not save (memory only)</strong>
                <p>Key lost when page reloads</p>
              </div>
            </label>

            <label className={styles.radio}>
              <input
                type="radio"
                name="mgmt-persistence"
                value="session"
                checked={selectedPersistence === 'session'}
                onChange={(e) => setSelectedPersistence(e.target.value as KeyPersistence)}
              />
              <div>
                <strong>Save for this session</strong>
                <p>Cleared when browser closes</p>
              </div>
            </label>

            <label className={styles.radio}>
              <input
                type="radio"
                name="mgmt-persistence"
                value="local"
                checked={selectedPersistence === 'local'}
                onChange={(e) => setSelectedPersistence(e.target.value as KeyPersistence)}
              />
              <div>
                <strong>Save on this device (Recommended)</strong>
                <p>Key persists across sessions. Stored in browser localStorage.</p>
              </div>
            </label>
          </div>

          <button
            onClick={handleSave}
            disabled={!keyInput.trim()}
            className={styles.btnPrimary}
          >
            Save Management Key
          </button>
        </div>
      )}
    </section>
  );
}
