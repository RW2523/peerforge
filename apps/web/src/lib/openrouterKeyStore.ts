/**
 * Centralized OpenRouter API key storage
 * BYOK: Key never sent to our backend DB, only used in request headers
 */

export type KeyPersistence = 'memory' | 'session' | 'local';

class OpenRouterKeyStore {
  private memoryKey: string | null = null;
  private memoryManagementKey: string | null = null;

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

  hasKey(): boolean {
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
