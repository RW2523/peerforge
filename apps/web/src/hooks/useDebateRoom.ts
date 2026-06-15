/**
 * React hook for WebSocket-based debate room transport
 * 
 * Manages WebSocket lifecycle, event subscription, and command dispatch
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { WSClient, WSEventEnvelope, WSCommandType, ConnectionStatus, WSAckMessage } from '@/lib/wsClient';
import { getAccessToken } from '@/lib/supabase';

export interface UseDebateRoomOptions {
  debateId: string;
  enabled?: boolean;
  sinceSequence?: number;
}

export interface UseDebateRoomResult {
  events: WSEventEnvelope[];
  connectionStatus: ConnectionStatus;
  sendCommand: (command: WSCommandType, payload?: Record<string, any>) => Promise<WSAckMessage>;
  clearEvents: () => void;
}

export function useDebateRoom(options: UseDebateRoomOptions): UseDebateRoomResult {
  const { debateId, enabled = true, sinceSequence = 0 } = options;
  
  const [events, setEvents] = useState<WSEventEnvelope[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const clientRef = useRef<WSClient | null>(null);
  const lastSeenSequenceRef = useRef<number>(0);

  // Poll for new thinking events from DB every 1 second
  useEffect(() => {
    if (!enabled || !debateId) return;

    const pollThinkingEvents = async () => {
      try {
        const token = await getAccessToken();
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/debates/${debateId}/events?event_type=agent_thinking&limit=20&since=${lastSeenSequenceRef.current}`,
          {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {}
          }
        );
        if (response.ok) {
          const dbEvents = await response.json();
          
          // Add events that we don't already have
          setEvents(prev => {
            const existingIds = new Set(prev.map(e => e.event_id));
            const newEvents = dbEvents.filter((e: any) => !existingIds.has(e.event_id));
            
            if (newEvents.length > 0) {
              console.log(`📥 Polled ${newEvents.length} new thinking events from DB (since seq ${lastSeenSequenceRef.current})`);
              
              // Update lastSeenSequence to highest sequence number
              const maxSeq = Math.max(...newEvents.map((e: any) => e.sequence_number || 0));
              if (maxSeq > lastSeenSequenceRef.current) {
                lastSeenSequenceRef.current = maxSeq;
              }
              
              return [...prev, ...newEvents];
            }
            return prev;
          });
        }
      } catch (err) {
        // Silent fail
      }
    };

    const interval = setInterval(pollThinkingEvents, 1000);
    pollThinkingEvents(); // Initial poll

    return () => clearInterval(interval);
  }, [enabled, debateId]);

  // Event handler
  const handleEvent = useCallback((event: WSEventEnvelope) => {
    // Debug: Log thinking events
    if (event.type === 'agent_thinking') {
      console.log('🟢 THINKING EVENT RECEIVED:', event.payload?.stage, 'at', new Date().toLocaleTimeString());
    }
    if (event.type === 'agent_message') {
      console.log('💬 MESSAGE EVENT RECEIVED at', new Date().toLocaleTimeString());
    }
    
    setEvents((prev) => {
      // Deduplicate by event_id (belt and suspenders with client-side dedupe)
      if (event.event_id && prev.some(e => e.event_id === event.event_id)) {
        return prev;
      }
      return [...prev, event];
    });
  }, []);

  // Connection status handler
  const handleConnectionChange = useCallback((status: ConnectionStatus) => {
    setConnectionStatus(status);
  }, []);

  // Auth token provider
  const getAuthToken = useCallback(async () => {
    const token = await getAccessToken();
    if (!token) {
      throw new Error('No auth token available');
    }
    return token;
  }, []);

  // Error handler
  const handleError = useCallback((error: Error) => {
    console.error('[useDebateRoom] WebSocket error:', error);
  }, []);

  // Initialize WebSocket client
  useEffect(() => {
    if (!enabled || !debateId) {
      return;
    }

    const client = new WSClient({
      debateId,
      getAuthToken,
      onEvent: handleEvent,
      onConnectionChange: handleConnectionChange,
      onError: handleError,
      sinceSequence,
      baseUrl: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
    });

    clientRef.current = client;
    client.connect();

    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, [debateId, enabled, sinceSequence, getAuthToken, handleEvent, handleConnectionChange, handleError]);

  // Command dispatcher with auto-reconnect
  const sendCommand = useCallback(async (command: WSCommandType, payload?: Record<string, any>): Promise<WSAckMessage> => {
    if (!clientRef.current) {
      // Presence commands are best-effort — silently no-op when WS is gone
      if (command === 'join_presence' || command === 'leave_presence') {
        return { type: 'ack', request_id: '', command, timestamp: '' } as WSAckMessage;
      }
      throw new Error('WebSocket client not initialized');
    }
    
    // Auto-reconnect if disconnected (user took time to read)
    if (clientRef.current.getStatus() !== 'connected') {
      console.log(`⚠️ WebSocket disconnected, reconnecting before sending ${command}...`);
      try {
        await clientRef.current.connect();
        
        // Wait up to 10 seconds for connection
        const startTime = Date.now();
        while (clientRef.current.getStatus() !== 'connected' && Date.now() - startTime < 10000) {
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        if (clientRef.current.getStatus() !== 'connected') {
          throw new Error('Failed to reconnect - please refresh the page');
        }
        
        console.log('✅ Reconnected successfully, sending command...');
      } catch (err) {
        throw new Error(`Failed to reconnect: ${err}`);
      }
    }

    return clientRef.current.sendCommand(command, payload);
  }, []);

  // Clear events (for testing or reset)
  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return {
    events,
    connectionStatus,
    sendCommand,
    clearEvents,
  };
}
