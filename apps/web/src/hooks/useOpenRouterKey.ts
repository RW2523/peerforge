import { useState, useEffect } from 'react';
import { keyStore, KeyPersistence } from '@/lib/openrouterKeyStore';

export function useOpenRouterKey() {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [persistence, setPersistence] = useState<KeyPersistence | null>(null);
  const [managementKey, setManagementKey] = useState<string | null>(null);
  const [managementPersistence, setManagementPersistence] = useState<KeyPersistence | null>(null);

  useEffect(() => {
    // Load keys on mount
    const key = keyStore.getKey();
    const persist = keyStore.getPersistence();
    const mgmtKey = keyStore.getManagementKey();
    const mgmtPersist = keyStore.getManagementKeyPersistence();
    
    setApiKey(key);
    setPersistence(persist);
    setManagementKey(mgmtKey);
    setManagementPersistence(mgmtPersist);
  }, []);

  const saveKey = (key: string, persist: KeyPersistence = 'memory') => {
    keyStore.setKey(key, persist);
    setApiKey(key);
    setPersistence(persist);
  };

  const clearKey = () => {
    keyStore.clearKey();
    setApiKey(null);
    setPersistence(null);
  };

  const saveManagementKey = (key: string, persist: KeyPersistence = 'memory') => {
    keyStore.setManagementKey(key, persist);
    setManagementKey(key);
    setManagementPersistence(persist);
  };

  const clearManagementKey = () => {
    keyStore.clearManagementKey();
    setManagementKey(null);
    setManagementPersistence(null);
  };

  const hasKey = keyStore.hasKey();
  const hasManagementKey = keyStore.hasManagementKey();

  return {
    apiKey,
    persistence,
    hasKey,
    saveKey,
    clearKey,
    managementKey,
    managementPersistence,
    hasManagementKey,
    saveManagementKey,
    clearManagementKey,
  };
}
