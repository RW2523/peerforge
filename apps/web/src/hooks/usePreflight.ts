/**
 * Custom hook for managing preflight preparation state
 * Handles polling, retry, skip, and status tracking
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import * as api from '@/lib/api';

export interface UsePreflightResult {
  status: api.PreflightStatusResponse | null;
  isPolling: boolean;
  error: string | null;
  
  startPreflight: (debateId: string, openrouterKey?: string | null) => Promise<void>;
  retryParticipant: (debateId: string, participantId: string) => Promise<void>;
  skipParticipant: (debateId: string, participantId: string, reason: string) => Promise<void>;
  refreshStatus: (debateId: string) => Promise<void>;
  stopPolling: () => void;
  
  // Computed states
  isStarted: boolean;
  isCompleted: boolean;
  canContinue: boolean;
  hasFailures: boolean;
  readyCount: number;
  totalCount: number;
}

export function usePreflight(): UsePreflightResult {
  const [status, setStatus] = useState<api.PreflightStatusResponse | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const currentDebateIdRef = useRef<string | null>(null);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  // Refresh status (single fetch)
  const refreshStatus = useCallback(async (debateId: string) => {
    try {
      setError(null);
      const statusData = await api.getPreflightStatus(debateId);
      setStatus(statusData);
      
      // Stop polling if terminal state reached
      if (statusData.status === 'completed' || statusData.status === 'failed') {
        stopPolling();
      }
    } catch (err: any) {
      // If preflight hasn't been started yet, this is expected
      if (!err.message.includes('404') && !err.message.includes('No preflight run found')) {
        setError(err.message || 'Failed to fetch preflight status');
      }
    }
  }, [stopPolling]);

  // Start polling
  const startPollingInternal = useCallback((debateId: string) => {
    currentDebateIdRef.current = debateId;
    setIsPolling(true);
    
    // Initial fetch
    refreshStatus(debateId);
    
    // Poll every 2 seconds
    pollingIntervalRef.current = setInterval(() => {
      if (currentDebateIdRef.current) {
        refreshStatus(currentDebateIdRef.current);
      }
    }, 2000);
  }, [refreshStatus]);

  // Start preflight
  const startPreflight = useCallback(async (debateId: string, openrouterKey?: string | null) => {
    try {
      setError(null);
      const startResponse = await api.startPreflight(debateId, openrouterKey);
      
      // Convert start response to status format for immediate UI update
      setStatus({
        run_id: startResponse.run_id,
        debate_id: startResponse.debate_id,
        status: startResponse.status as any,
        created_at: new Date().toISOString(),
        participant_runs: startResponse.participant_runs.map(pr => ({
          participant_run_id: pr.participant_run_id,
          participant_id: pr.participant_id,
          agent_id: pr.agent_id,
          status: pr.status as any,
          metadata: {},
        })),
      });
      
      // Start polling for updates
      startPollingInternal(debateId);
    } catch (err: any) {
      setError(err.message || 'Failed to start preflight');
      throw err;
    }
  }, [startPollingInternal]);

  // Retry participant
  const retryParticipant = useCallback(async (debateId: string, participantId: string) => {
    try {
      setError(null);
      await api.retryPreflightParticipant(debateId, participantId);
      // Refresh immediately
      await refreshStatus(debateId);
      // Resume polling if not already
      if (!isPolling) {
        startPollingInternal(debateId);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to retry participant');
      throw err;
    }
  }, [refreshStatus, isPolling, startPollingInternal]);

  // Skip participant
  const skipParticipant = useCallback(async (
    debateId: string,
    participantId: string,
    reason: string
  ) => {
    try {
      setError(null);
      await api.skipPreflightParticipant(debateId, participantId, reason);
      // Refresh immediately
      await refreshStatus(debateId);
    } catch (err: any) {
      setError(err.message || 'Failed to skip participant');
      throw err;
    }
  }, [refreshStatus]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  // Computed states
  const isStarted = status !== null;
  const isCompleted = status?.status === 'completed' || status?.status === 'failed';
  
  const readyCount = status?.participant_runs.filter(
    pr => pr.status === 'success' || pr.status === 'skipped'
  ).length || 0;
  
  const totalCount = status?.participant_runs.length || 0;
  
  const hasFailures = status?.participant_runs.some(pr => pr.status === 'failed') || false;
  
  // Can continue if:
  // - Run is completed (all participants done), OR
  // - User has explicitly skipped some (at least one success or skipped)
  const canContinue = isCompleted || (
    isStarted && readyCount > 0 && readyCount === totalCount
  );

  return {
    status,
    isPolling,
    error,
    
    startPreflight,
    retryParticipant,
    skipParticipant,
    refreshStatus,
    stopPolling,
    
    isStarted,
    isCompleted,
    canContinue,
    hasFailures,
    readyCount,
    totalCount,
  };
}
