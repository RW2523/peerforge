/**
 * Hook for consuming SSE event stream
 */
import { useEffect, useState, useCallback } from 'react';

export interface DebateEvent {
  event_id: string;
  debate_id: string;
  event_type: string;
  sequence_number: number;
  occurred_at: string;
  payload: any;
}

export interface StreamState {
  events: DebateEvent[];
  debateState: string | null;
  isConnected: boolean;
  error: string | null;
}

const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE || 'production';
const TEST_TOKEN = process.env.NEXT_PUBLIC_TEST_TOKEN || '';

export function useEventStream(url: string | null) {
  const [state, setState] = useState<StreamState>({
    events: [],
    debateState: null,
    isConnected: false,
    error: null,
  });

  const connect = useCallback(() => {
    if (!url) return;

    setState(prev => ({ ...prev, isConnected: true, error: null }));

    // Create EventSource with auth header (Phase 4A: using fetch workaround for auth)
    // Note: EventSource doesn't support custom headers, so we append token as query param
    // or use fetch-based SSE client for production
    let streamUrl = url;
    if (AUTH_MODE === 'development' && TEST_TOKEN) {
      // For demo purposes, we'll use a simple fetch-based approach
      // Production would use proper SSE library with auth headers
      const separator = url.includes('?') ? '&' : '?';
      streamUrl = `${url}${separator}auth=${encodeURIComponent(TEST_TOKEN)}`;
    }

    const eventSource = new EventSource(streamUrl);

    eventSource.addEventListener('debate_event', (e) => {
      try {
        const event = JSON.parse(e.data);
        setState(prev => ({
          ...prev,
          events: [...prev.events, event],
        }));
      } catch (err) {
        console.error('Failed to parse debate_event:', err);
      }
    });

    eventSource.addEventListener('state_update', (e) => {
      try {
        const update = JSON.parse(e.data);
        setState(prev => ({
          ...prev,
          debateState: update.state,
        }));
      } catch (err) {
        console.error('Failed to parse state_update:', err);
      }
    });

    eventSource.addEventListener('stream_end', () => {
      setState(prev => ({ ...prev, isConnected: false }));
      eventSource.close();
    });

    eventSource.onerror = (err) => {
      console.error('EventSource error:', err);
      setState(prev => ({
        ...prev,
        isConnected: false,
        error: 'Stream connection error',
      }));
      eventSource.close();
    };

    return () => {
      eventSource.close();
      setState(prev => ({ ...prev, isConnected: false }));
    };
  }, [url]);

  useEffect(() => {
    const cleanup = connect();
    return cleanup;
  }, [connect]);

  return state;
}
