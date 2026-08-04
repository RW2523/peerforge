import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { keyStore, KeyPersistence } from '@/lib/openrouterKeyStore';
import { getOpenRouterKeyStatus } from '@/lib/api';

// Fetched once per page load and shared: every component using this hook was
// otherwise issuing its own request for the same answer.
let statusPromise: Promise<void> | null = null;

function loadServerKeyStatus(): Promise<void> {
  if (!statusPromise) {
    statusPromise = getOpenRouterKeyStatus()
      .then((s) => keyStore.setServerKeyAvailable(Boolean(s?.server_key_available)))
      .catch(() => {
        // An unreachable backend is not the same as "no key". Leave the flag
        // alone rather than disabling the whole UI on a transient failure.
      });
  }
  return statusPromise;
}

export function useOpenRouterKey() {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [persistence, setPersistence] = useState<KeyPersistence | null>(null);
  const [managementKey, setManagementKey] = useState<string | null>(null);
  const [managementPersistence, setManagementPersistence] = useState<KeyPersistence | null>(null);

  // Re-renders when server-key availability lands, so controls disabled on
  // first paint become usable without the user reloading.
  const serverKeyAvailable = useSyncExternalStore(
    useCallback((cb: () => void) => keyStore.subscribe(cb), []),
    () => keyStore.hasServerKey(),
    () => false
  );

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

    loadServerKeyStatus();
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

  // "Can we generate", which is true when the server holds a key even though
  // this browser holds none. hasBrowserKey is the narrower question Settings
  // asks when describing what the user personally stored.
  const hasKey = apiKey !== null || serverKeyAvailable;
  const hasBrowserKey = apiKey !== null;
  const hasManagementKey = keyStore.hasManagementKey();

  return {
    apiKey,
    persistence,
    hasKey,
    hasBrowserKey,
    serverKeyAvailable,
    saveKey,
    clearKey,
    managementKey,
    managementPersistence,
    hasManagementKey,
    saveManagementKey,
    clearManagementKey,
  };
}
