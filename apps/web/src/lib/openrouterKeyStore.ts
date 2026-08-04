/**
 * Centralized OpenRouter API key storage
 *
 * BYOK: a key held here is never sent to our backend DB, only used in request
 * headers. But it is no longer the only way to generate — the deployment can
 * carry its own key, and the backend resolves header → account key → server
 * key on every AI route. `serverKeyAvailable` records that, so the UI stops
 * demanding a key the server already has.
 */

export type KeyPersistence = 'memory' | 'session' | 'local';

class OpenRouterKeyStore {
  private memoryKey: string | null = null;
  private memoryManagementKey: string | null = null;
  private serverKeyAvailable = false;
  private statusKnown = false;
  private listeners = new Set<() => void>();

  /** Told by the app once /me/openrouter-key has answered. */
  setServerKeyAvailable(available: boolean): void {
    if (this.statusKnown && this.serverKeyAvailable === available) return;
    this.serverKeyAvailable = available;
    this.statusKnown = true;
    this.listeners.forEach((l) => l());
  }

  hasServerKey(): boolean {
    return this.serverKeyAvailable;
  }

  /**
   * Whether we have actually heard back about the server's key.
   *
   * Before the answer arrives, "no key" and "not asked yet" look identical,
   * and treating them the same made every AI control flash "API Key Required"
   * on first paint — on a deployment that has a key.
   */
  isStatusKnown(): boolean {
    return this.statusKnown;
  }

  /** Notified when server-key availability changes, so gates re-render. */
  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  getKey(): string | null {
    // Priority: memory > sessionStorage > localStorage
    if (this.memoryKey) return this.memoryKey;

    if (typeof window === 'undefined') return null;

    const sessionKey = sessionStorage.getItem('openrouter_api_key');
    if (sessionKey) return sessionKey;

    const localKey = localStorage.getItem('openrouter_api_key');
    if (localKey) return localKey;

    return null;
  }

  setKey(key: string, persistence: KeyPersistence = 'memory'): void {
    if (typeof window === 'undefined') return;

    // Clear all storage first
    this.clearKey();

    // Store based on persistence choice
    switch (persistence) {
      case 'memory':
        this.memoryKey = key;
        break;
      case 'session':
        sessionStorage.setItem('openrouter_api_key', key);
        break;
      case 'local':
        localStorage.setItem('openrouter_api_key', key);
        break;
    }
  }

  clearKey(): void {
    this.memoryKey = null;
    
    if (typeof window === 'undefined') return;
    
    sessionStorage.removeItem('openrouter_api_key');
    localStorage.removeItem('openrouter_api_key');
  }

  getPersistence(): KeyPersistence | null {
    if (this.memoryKey) return 'memory';
    
    if (typeof window === 'undefined') return null;
    
    if (sessionStorage.getItem('openrouter_api_key')) return 'session';
    if (localStorage.getItem('openrouter_api_key')) return 'local';
    
    return null;
  }

  /**
   * Can this deployment generate? Not "is there a key in this browser".
   *
   * Gating on browser storage alone disabled every AI control on a deployment
   * whose server key worked perfectly well. Before the server has answered we
   * assume yes, so the UI does not accuse a working deployment of missing a
   * key during the moment it takes to ask. Acting without one simply surfaces
   * the backend's own message instead.
   */
  hasKey(): boolean {
    if (this.getKey() !== null) return true;
    return this.statusKnown ? this.serverKeyAvailable : true;
  }

  /** True only when the key came from this browser, for Settings to display. */
  hasBrowserKey(): boolean {
    return this.getKey() !== null;
  }

  // Management Key methods (for accessing credits/admin endpoints)
  getManagementKey(): string | null {
    // Priority: memory > sessionStorage > localStorage
    if (this.memoryManagementKey) return this.memoryManagementKey;

    if (typeof window === 'undefined') return null;

    const sessionKey = sessionStorage.getItem('openrouter_management_key');
    if (sessionKey) return sessionKey;

    const localKey = localStorage.getItem('openrouter_management_key');
    if (localKey) return localKey;

    return null;
  }

  setManagementKey(key: string, persistence: KeyPersistence = 'memory'): void {
    if (typeof window === 'undefined') return;

    // Clear all management key storage first
    this.clearManagementKey();

    // Store based on persistence choice
    switch (persistence) {
      case 'memory':
        this.memoryManagementKey = key;
        break;
      case 'session':
        sessionStorage.setItem('openrouter_management_key', key);
        break;
      case 'local':
        localStorage.setItem('openrouter_management_key', key);
        break;
    }
  }

  clearManagementKey(): void {
    this.memoryManagementKey = null;
    
    if (typeof window === 'undefined') return;
    
    sessionStorage.removeItem('openrouter_management_key');
    localStorage.removeItem('openrouter_management_key');
  }

  getManagementKeyPersistence(): KeyPersistence | null {
    if (this.memoryManagementKey) return 'memory';
    
    if (typeof window === 'undefined') return null;
    
    if (sessionStorage.getItem('openrouter_management_key')) return 'session';
    if (localStorage.getItem('openrouter_management_key')) return 'local';
    
    return null;
  }

  hasManagementKey(): boolean {
    return this.getManagementKey() !== null;
  }
}

export const keyStore = new OpenRouterKeyStore();
