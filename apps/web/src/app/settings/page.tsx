'use client';

import { useState, useEffect } from 'react';
import AppNav from '@/components/layout/AppNav';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import { KeyPersistence } from '@/lib/openrouterKeyStore';
import { DefaultModelsCard } from '@/components/settings/DefaultModelsCard';
import { AccountInfoCard } from '@/components/settings/AccountInfoCard';
import { ManagementKeyCard } from '@/components/settings/ManagementKeyCard';
import { AccountKeyCard } from '@/components/settings/AccountKeyCard';
import * as api from '@/lib/api';
import styles from './settings.module.css';

export default function SettingsPage() {
  const { 
    apiKey, 
    persistence, 
    saveKey, 
    clearKey,
    managementKey,
    managementPersistence,
    saveManagementKey,
    clearManagementKey 
  } = useOpenRouterKey();
  
  const [keyInput, setKeyInput] = useState('');
  const [selectedPersistence, setSelectedPersistence] = useState<KeyPersistence>('local');
  const [accountInfo, setAccountInfo] = useState<api.OpenRouterAccountResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [validationSuccess, setValidationSuccess] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Demo workspace ID (replace with actual user's workspace in production)
  const workspaceId = '00000000-0000-0000-0000-000000000101';

  useEffect(() => {
    if (apiKey) {
      setKeyInput('');
      fetchAccountInfo();
    } else {
      setAccountInfo(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey, managementKey]);

  useEffect(() => {
    if (persistence) {
      setSelectedPersistence(persistence);
    }
  }, [persistence]);

  const fetchAccountInfo = async () => {
    if (!apiKey) return;

    setLoading(true);
    setError(null);

    try {
      const data = await api.getOpenRouterAccount(apiKey, managementKey);
      setAccountInfo(data);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch account info');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveKey = async () => {
    const trimmedKey = keyInput.trim();
    if (!trimmedKey) return;

    // Reset states
    setValidating(true);
    setValidationError(null);
    setValidationSuccess(false);

    try {
      // Validate key by calling /openrouter/account (with management key if available)
      const data = await api.getOpenRouterAccount(trimmedKey, managementKey);
      
      // If we got here, key is valid
      setValidationSuccess(true);
      setAccountInfo(data);
      setLastUpdated(new Date());
      
      // Save key to browser storage
      saveKey(trimmedKey, selectedPersistence);
      setKeyInput('');
      
      // Clear success message after 3 seconds
      setTimeout(() => setValidationSuccess(false), 3000);
    } catch (err) {
      // Key is invalid or network error
      const errorMessage = err instanceof Error ? err.message : 'Failed to validate key';
      setValidationError(errorMessage);
      
      // Don't save invalid key
      // Keep input so user can correct it
    } finally {
      setValidating(false);
    }
  };

  const handleSaveManagementKey = (key: string, persistence: KeyPersistence) => {
    // Save management key to browser storage
    saveManagementKey(key, persistence);
    
    // Refresh account info to fetch credits
    if (apiKey) {
      fetchAccountInfo();
    }
  };

  const handleClearKey = () => {
    clearKey();
    setAccountInfo(null);
    setLastUpdated(null);
  };

  const handleClearManagementKey = () => {
    clearManagementKey();
    // Refresh account info without management key
    if (apiKey) {
      fetchAccountInfo();
    }
  };

  return (
    <>
      <AppNav />
      <div className={styles.container}>
      <div className={styles.content}>
        <h1>Settings</h1>
        <p className={styles.subtitle}>Enter your OpenRouter API key to enable AI features</p>
        
        {!apiKey && (
          <div style={{
            backgroundColor: '#e3f2fd',
            border: '1px solid #2196f3',
            borderRadius: '8px',
            padding: '16px 20px',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <span style={{ fontSize: '24px' }}>💡</span>
            <div>
              <strong style={{ color: '#1565c0' }}>First Time Setup</strong>
              <p style={{ margin: '4px 0 0 0', color: '#1565c0', fontSize: '14px' }}>
                Choose "Save on this device" to keep your API key across page refreshes. You can always clear it later.
              </p>
            </div>
          </div>
        )}

          {/* API Key Card */}
          <section className={styles.card}>
            <h2>OpenRouter API Key</h2>
            <p className={styles.cardDesc}>
              Enter your OpenRouter key to use AI features. Your key is never stored on our servers.
            </p>

            {apiKey ? (
              <div className={styles.keyStatus}>
                <div className={styles.keyStatusHeader}>
                  <span className={styles.keyIcon}>✅</span>
                  <div>
                    <strong>Key Verified & Saved</strong>
                    <p>
                      Stored: <span className={styles.persistenceBadge}>{persistence}</span>
                    </p>
                  </div>
                </div>
                <button onClick={handleClearKey} className={styles.btnDanger}>
                  Clear Key
                </button>
              </div>
            ) : (
              <>
                <div className={styles.form}>
                  <label>
                    API Key
                    <input
                      type="password"
                      value={keyInput}
                      onChange={(e) => setKeyInput(e.target.value)}
                      placeholder="sk-or-..."
                    />
                  </label>

                  <div className={styles.persistenceOptions}>
                    <label className={styles.radio}>
                      <input
                        type="radio"
                        name="persistence"
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
                        name="persistence"
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
                        name="persistence"
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
                    onClick={handleSaveKey}
                    disabled={!keyInput.trim() || validating}
                    className={styles.btnPrimary}
                  >
                    {validating ? 'Validating...' : 'Validate & Save Key'}
                  </button>
                </div>

                {validationError && (
                  <div className={styles.error}>
                    <span>❌</span>
                    <div>
                      <strong>Validation Failed</strong>
                      <p>{validationError}</p>
                      <p className={styles.hint}>Please check your key and try again.</p>
                    </div>
                  </div>
                )}

                {validationSuccess && (
                  <div className={styles.success}>
                    <span>✅</span>
                    <div>
                      <strong>Key Verified!</strong>
                      <p>Your OpenRouter key is valid and has been saved.</p>
                    </div>
                  </div>
                )}

                <div className={styles.securityNote}>
                  <span>🔒</span>
                  <div>
                    <strong>Security Promise</strong>
                    <p>Your API key is never sent to our database. It stays in your browser only.</p>
                  </div>
                </div>
              </>
            )}
          </section>

          {/* Account-stored OpenRouter key (encrypted server-side) */}
          <AccountKeyCard />

          {/* Management Key Card */}
          <ManagementKeyCard
            managementKey={managementKey}
            managementPersistence={managementPersistence}
            onSave={handleSaveManagementKey}
            onClear={handleClearManagementKey}
          />

          {/* Account Info Card */}
          <AccountInfoCard
            apiKey={apiKey}
            accountInfo={accountInfo}
            loading={loading}
            error={error}
            lastUpdated={lastUpdated}
            onRefresh={fetchAccountInfo}
          />

          {/* Default Models Card */}
          <DefaultModelsCard apiKey={apiKey} workspaceId={workspaceId} />
        </div>
      </div>
    </>
  );
}
