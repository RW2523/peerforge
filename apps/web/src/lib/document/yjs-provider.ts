/**
 * Yjs Provider for Document Collaboration
 * Handles real-time document synchronization using Yjs CRDT
 */

import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { Awareness } from 'y-protocols/awareness';
import { AgentPresence } from './types';

// ============================================================================
// Configuration
// ============================================================================

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

// ============================================================================
// Yjs Document Manager
// ============================================================================

export class DocumentCollaborationProvider {
  private ydoc: Y.Doc;
  private provider: WebsocketProvider | null = null;
  private documentId: string;
  private userId: string;
  private userName: string;
  private userType: 'human' | 'agent';
  private onConnected?: () => void;
  private onDisconnected?: () => void;
  private onSynced?: () => void;

  constructor(
    documentId: string,
    userId: string,
    userName: string,
    userType: 'human' | 'agent' = 'human'
  ) {
    this.documentId = documentId;
    this.userId = userId;
    this.userName = userName;
    this.userType = userType;
    this.ydoc = new Y.Doc();
  }

  /**
   * Connect to the WebSocket server and start syncing
   */
  connect(callbacks?: {
    onConnected?: () => void;
    onDisconnected?: () => void;
    onSynced?: () => void;
  }): void {
    if (this.provider) {
      console.warn('Provider already connected');
      return;
    }

    this.onConnected = callbacks?.onConnected;
    this.onDisconnected = callbacks?.onDisconnected;
    this.onSynced = callbacks?.onSynced;

    // Create WebSocket provider
    // Note: WebsocketProvider appends room name to URL, so base URL should be ws://host/path
    const wsUrl = `${WS_URL}/ws/document`;
    
    // Create custom awareness instance
    const awareness = new Awareness(this.ydoc);
    
    // Set local user state
    awareness.setLocalStateField('user', {
      id: this.userId,
      name: this.userName,
      type: this.userType,
      color: this.generateUserColor(),
    });
    
    this.provider = new WebsocketProvider(
      wsUrl,
      this.documentId,
      this.ydoc,
      {
        connect: true,
        awareness: awareness,
      }
    );

    // Set up event listeners
    this.setupEventListeners();
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): void {
    if (this.provider) {
      this.provider.disconnect();
      this.provider.destroy();
      this.provider = null;
    }
  }

  /**
   * Get the Yjs document
   */
  getYDoc(): Y.Doc {
    return this.ydoc;
  }

  /**
   * Get the WebSocket provider
   */
  getProvider(): WebsocketProvider | null {
    return this.provider;
  }

  /**
   * Get the shared text for a specific section
   */
  getSharedText(sectionKey: string): Y.Text {
    return this.ydoc.getText(sectionKey);
  }

  /**
   * Get all shared texts (for all sections)
   */
  getAllSharedTexts(): Map<string, Y.Text> {
    const texts = new Map<string, Y.Text>();
    this.ydoc.share.forEach((value, key) => {
      if (value instanceof Y.Text) {
        texts.set(key, value);
      }
    });
    return texts;
  }

  /**
   * Get awareness states (presence information)
   */
  getAwarenessStates(): AgentPresence[] {
    if (!this.provider) return [];

    const states: AgentPresence[] = [];
    const awareness = this.provider.awareness;

    awareness.getStates().forEach((state, clientId) => {
      if (state.user) {
        states.push({
          userId: state.user.id,
          userName: state.user.name,
          userType: state.user.type || 'human',
          color: state.user.color,
          cursor: state.cursor,
          selection: state.selection,
          activeSectionId: state.activeSectionId,
          lastActive: Date.now(),
        });
      }
    });

    return states;
  }

  /**
   * Update local awareness state (cursor position, active section)
   */
  updateAwareness(update: {
    cursor?: { x: number; y: number; position: number };
    selection?: { from: number; to: number };
    activeSectionId?: string;
  }): void {
    if (!this.provider) return;

    const awareness = this.provider.awareness;
    const currentState = awareness.getLocalState() || {};

    awareness.setLocalState({
      ...currentState,
      ...update,
      lastActive: Date.now(),
    });
  }

  /**
   * Subscribe to awareness changes
   */
  onAwarenessChange(callback: (states: AgentPresence[]) => void): () => void {
    if (!this.provider) {
      return () => {};
    }

    const awareness = this.provider.awareness;

    const handler = () => {
      callback(this.getAwarenessStates());
    };

    awareness.on('change', handler);

    // Return unsubscribe function
    return () => {
      awareness.off('change', handler);
    };
  }

  /**
   * Check if currently connected
   */
  isConnected(): boolean {
    return this.provider?.wsconnected || false;
  }

  /**
   * Check if document is synced
   */
  isSynced(): boolean {
    return this.provider?.synced || false;
  }

  // ============================================================================
  // Private Methods
  // ============================================================================

  private setupEventListeners(): void {
    if (!this.provider) return;

    // Connection status
    this.provider.on('status', (event: { status: string }) => {
      console.log(`[Yjs] Connection status: ${event.status}`);
      
      if (event.status === 'connected') {
        this.onConnected?.();
      } else if (event.status === 'disconnected') {
        this.onDisconnected?.();
      }
    });

    // Sync status
    this.provider.on('sync', (isSynced: boolean) => {
      console.log(`[Yjs] Sync status: ${isSynced}`);
      
      if (isSynced) {
        this.onSynced?.();
      }
    });

    // Connection errors
    this.provider.on('connection-error', (event: Event) => {
      console.error('[Yjs] Connection error:', event);
    });

    // Document updates
    this.ydoc.on('update', (update: Uint8Array, origin: any) => {
      console.log('[Yjs] Document updated', { updateSize: update.length, origin });
    });
  }

  private generateUserColor(): string {
    // Generate consistent color based on user ID
    const colors = [
      '#3b82f6', // blue
      '#10b981', // green
      '#f59e0b', // amber
      '#ef4444', // red
      '#8b5cf6', // purple
      '#06b6d4', // cyan
      '#ec4899', // pink
      '#f97316', // orange
    ];

    // Handle undefined or null userId
    if (!this.userId) {
      return colors[0]; // Default to blue
    }

    const hash = this.userId.split('').reduce((acc, char) => {
      return char.charCodeAt(0) + ((acc << 5) - acc);
    }, 0);

    return colors[Math.abs(hash) % colors.length];
  }
}

// ============================================================================
// Factory Function
// ============================================================================

export function createDocumentProvider(
  documentId: string,
  userId: string,
  userName: string,
  userType: 'human' | 'agent' = 'human'
): DocumentCollaborationProvider {
  return new DocumentCollaborationProvider(documentId, userId, userName, userType);
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Convert Yjs Text to plain string
 */
export function yjsTextToString(ytext: Y.Text): string {
  return ytext.toString();
}

/**
 * Convert Yjs Text to HTML (with formatting)
 */
export function yjsTextToHtml(ytext: Y.Text): string {
  // This is a simplified version
  // In production, use @tiptap/core's getHTML()
  return ytext.toString();
}

/**
 * Apply text update to Yjs Text
 */
export function applyTextUpdate(
  ytext: Y.Text,
  text: string,
  position: number = 0
): void {
  ytext.delete(0, ytext.length);
  ytext.insert(0, text);
}

/**
 * Insert text at position
 */
export function insertText(
  ytext: Y.Text,
  text: string,
  position: number
): void {
  ytext.insert(position, text);
}

/**
 * Delete text range
 */
export function deleteText(
  ytext: Y.Text,
  start: number,
  length: number
): void {
  ytext.delete(start, length);
}
