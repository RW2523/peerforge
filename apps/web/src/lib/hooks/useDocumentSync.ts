/**
 * useDocumentSync Hook - Real-time Yjs synchronization
 */
import { useEffect, useState, useRef } from 'react';
import { DocumentCollaborationProvider } from '../document/yjs-provider';
import { AgentPresence } from '../document/types';

export function useDocumentSync(
  documentId: string | null,
  userId: string,
  userName: string
) {
  const [provider, setProvider] = useState<DocumentCollaborationProvider | null>(null);
  const [connected, setConnected] = useState(false);
  const [synced, setSynced] = useState(false);
  const [presences, setPresences] = useState<AgentPresence[]>([]);
  const providerRef = useRef<DocumentCollaborationProvider | null>(null);

  useEffect(() => {
    if (!documentId) return;

    const newProvider = new DocumentCollaborationProvider(
      documentId,
      userId,
      userName,
      'human'
    );

    newProvider.connect({
      onConnected: () => setConnected(true),
      onDisconnected: () => setConnected(false),
      onSynced: () => setSynced(true),
    });

    const unsubscribe = newProvider.onAwarenessChange(setPresences);

    setProvider(newProvider);
    providerRef.current = newProvider;

    return () => {
      unsubscribe();
      newProvider.disconnect();
    };
  }, [documentId, userId, userName]);

  return {
    provider,
    connected,
    synced,
    presences,
    ydoc: provider?.getYDoc(),
  };
}
