'use client';

import { useState, useEffect } from 'react';
import styles from './DebateControls.module.css';
import * as api from '@/lib/api';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import { WSCommandType, WSAckMessage } from '@/lib/wsClient';

interface DebateControlsProps {
  debateId: string;
  currentState: string;
  isYoloMode?: boolean;
  yoloStatus?: string | null;
  policyConfig?: any;
  totalTurns?: number;
  participantCount?: number;
  onPolicyUpdate?: () => void;
  onStateChange: (newState: string) => void;
  onYoloStatusChange?: (status: string | null) => void;
  /** Called when Auto Mode is switched on from the controls. */
  onAutoModeChange?: (enabled: boolean) => void;
  sendCommand?: (command: WSCommandType, payload?: Record<string, any>) => Promise<WSAckMessage>;
}

export default function DebateControls({ debateId, currentState, isYoloMode = false, yoloStatus, policyConfig, totalTurns = 0, participantCount = 0, onPolicyUpdate, onStateChange, onYoloStatusChange, onAutoModeChange, sendCommand }: DebateControlsProps) {
  const { apiKey } = useOpenRouterKey();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEndConfirm, setShowEndConfirm] = useState(false);
  const [triggeringTurn, setTriggeringTurn] = useState(false);
  const [extending, setExtending] = useState(false);
  const [pausingYolo, setPausingYolo] = useState(false);
  const [startingAuto, setStartingAuto] = useState(false);
  
  // Debug: Log API key status
  console.log('🔑 DebateControls API Key:', apiKey ? `EXISTS (${apiKey.substring(0, 15)}...)` : 'NOT FOUND');

  // Keyboard shortcut: Space or Enter to trigger next turn (power user feature)
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Only if running, not in input field, and not triggering already
      if (
        currentState === 'running' &&
        !isYoloMode &&
        !triggeringTurn &&
        (e.key === ' ' || e.key === 'Enter') &&
        !(e.target as HTMLElement).matches('input, textarea, [contenteditable]')
      ) {
        e.preventDefault();
        handleNextTurn();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [currentState, isYoloMode, triggeringTurn, apiKey, debateId]);

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.startDebate(debateId);
      onStateChange(result.state);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start debate');
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async () => {
    setLoading(true);
    setError(null);
    try {
      // Check if debate can be paused
      if (currentState !== 'running') {
        setError('Can only pause a running debate');
        setLoading(false);
        return;
      }
      
      // If YOLO mode, pause autonomous loop as well
      if (isYoloMode) {
        await api.pauseAutonomousDebate(debateId);
      }
      
      if (sendCommand) {
        await sendCommand('control.pause');
        onStateChange('paused');
      } else {
        const result = await api.pauseDebate(debateId);
        onStateChange(result.state);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to pause debate');
    } finally {
      setLoading(false);
    }
  };

  const handleResume = async () => {
    setLoading(true);
    setError(null);
    try {
      // If YOLO mode, resume autonomous loop as well
      if (isYoloMode) {
        if (!apiKey) {
          setError('OpenRouter API key required for YOLO mode. Please add it in Settings.');
          setLoading(false);
          return;
        }
        await api.resumeAutonomousDebate(debateId, apiKey);
      }
      
      if (sendCommand) {
        await sendCommand('control.resume');
        onStateChange('running');
      } else {
        const result = await api.resumeDebate(debateId);
        onStateChange(result.state);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resume debate');
    } finally {
      setLoading(false);
    }
  };

  const handlePauseYolo = async () => {
    setPausingYolo(true);
    setError(null);
    try {
      await api.pauseAutonomousDebate(debateId);
      onYoloStatusChange?.('paused');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to pause autonomous debate');
    } finally {
      setPausingYolo(false);
    }
  };

  const handleResumeYolo = async () => {
    if (!apiKey) {
      setError('OpenRouter API key required. Please add it in Settings.');
      return;
    }

    setPausingYolo(true);
    setError(null);
    try {
      await api.resumeAutonomousDebate(debateId, apiKey);
      onYoloStatusChange?.('running');
      console.log('✅ Auto mode loop restarted');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resume autonomous debate');
    } finally {
      setPausingYolo(false);
    }
  };

  // Auto Mode: run the whole session hands-free — each panel member speaks in
  // turn (waiting for the previous turn to finish) until all rounds complete,
  // then the session concludes automatically.
  const handleStartAutoMode = async () => {
    if (!apiKey) {
      setError('OpenRouter API key required for Auto Mode. Please add it in Settings.');
      return;
    }
    setStartingAuto(true);
    setError(null);
    try {
      if (currentState === 'pending') {
        const result = await api.startDebate(debateId, apiKey);
        onStateChange(result.state);
      }
      await api.startAutonomousDebate(debateId, 5, apiKey);
      onAutoModeChange?.(true);
      onYoloStatusChange?.('running');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start Auto Mode');
    } finally {
      setStartingAuto(false);
    }
  };

  const handleEnd = async () => {
    setShowEndConfirm(false);
    setLoading(true);
    setError(null);
    try {
      if (sendCommand) {
        try {
          await sendCommand('control.end');
        } catch (wsErr) {
          // WebSocket unavailable — fall back to REST API
          console.warn('WS unavailable for control.end, using REST fallback:', wsErr);
          await api.endDebate(debateId);
        }
      } else {
        await api.endDebate(debateId);
      }
      onStateChange('ended');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to end debate');
    } finally {
      setLoading(false);
    }
  };

  const handleNextTurn = async () => {
    if (!apiKey) {
      setError('OpenRouter API key required. Please add it in Settings.');
      return;
    }

    setTriggeringTurn(true);
    setError(null);
    try {
      // Check if this should be a conclusion instead
      if (shouldConclude) {
        // Call conclude endpoint for host (if enabled) or just end the meeting
        if (policyConfig?.enable_host) {
          console.log('🏁 Triggering host conclusion...');
          try {
            const result = await api.concludeDebate(debateId, apiKey);
            console.log('✅ Host conclusion triggered:', result);
            // Don't change state - wait for host message via WebSocket
            // The host will speak, and THEN we can end the meeting
          } catch (error: any) {
            console.error('❌ Host conclusion failed:', error);
            alert(`Failed to conclude debate: ${error.message || 'Unknown error'}`);
            setTriggeringTurn(false);
            return;
          }
        } else {
          // No host - just end the meeting
          console.log('🏁 No host enabled - ending meeting directly');
          if (sendCommand) {
            try {
              await sendCommand('control.end');
            } catch (wsErr) {
              console.warn('WS unavailable for control.end, using REST fallback:', wsErr);
              await api.endDebate(debateId);
            }
          } else {
            await api.endDebate(debateId);
          }
          onStateChange('ended');
        }
      } else {
        // Regular turn
        if (sendCommand) {
          try {
            await sendCommand('control.next_turn', { openrouter_key: apiKey });
            // With non-blocking WS, ACK comes back immediately.
            // The agent_message event will appear in the feed when the LLM finishes.
          } catch (wsErr: any) {
            const errMsg = wsErr instanceof Error
              ? wsErr.message
              : (wsErr?.error || String(wsErr));

            if (errMsg.includes('already in progress')) {
              // Another turn is running — surface a friendly message, don't REST-fallback
              setError('A turn is already in progress. Please wait for the current agent to finish.');
              return;
            }
            if (errMsg.includes('Command timeout') || errMsg.includes('WebSocket disconnected')) {
              // LLM is still processing server-side; the event will arrive via broadcast.
              // Don't double-trigger via REST — just let the broadcast deliver the result.
              console.warn('WS command timed out or disconnected — waiting for broadcast:', errMsg);
              return;
            }
            // Genuine WS connection issue — fall back to REST
            console.warn('WS error for next_turn, using REST fallback:', wsErr);
            await api.triggerNextTurn(debateId, apiKey);
          }
        } else {
          await api.triggerNextTurn(debateId, apiKey);
        }
      }
      // Success! The event will appear in the feed
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger agent turn');
    } finally {
      setTriggeringTurn(false);
    }
  };

  const handleExtend = async () => {
    setExtending(true);
    setError(null);
    try {
      const hasRounds = policyConfig?.max_rounds;
      const hasTime = policyConfig?.timebox_minutes;
      
      if (hasRounds) {
        // Extend by 2 more rounds
        await api.extendDebate(debateId, 2, undefined);
      } else if (hasTime) {
        // Add 15 more minutes
        await api.extendDebate(debateId, undefined, 15);
      }
      
      // Refresh policy config
      if (onPolicyUpdate) {
        onPolicyUpdate();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to extend debate');
    } finally {
      setExtending(false);
    }
  };

  // Check if all rounds complete (should conclude)
  const maxTotalTurns = policyConfig?.max_rounds && participantCount > 0 
    ? policyConfig.max_rounds * participantCount
    : null;
  
  // Show conclude button if max rounds reached, regardless of host setting
  // If host is enabled, it will provide conclusion; otherwise just mark meeting as complete
  const shouldConclude = maxTotalTurns && totalTurns >= maxTotalTurns;
  
  const canStart = currentState === 'pending';
  const canPause = currentState === 'running';
  const canResume = currentState === 'paused';
  const canEnd = currentState === 'running' || currentState === 'paused';
  const canTriggerTurn = currentState === 'running' && apiKey;
  const canExtend = (currentState === 'running' || currentState === 'paused') && policyConfig && (policyConfig.max_rounds || policyConfig.timebox_minutes);
  
  // Debug: Log button state
  console.log('🎮 Button States:', { currentState, apiKey: !!apiKey, canTriggerTurn, sendCommand: !!sendCommand });

  return (
    <div className={styles.controls}>
      <h3>Controls</h3>

      {error && (
        <div className={styles.error}>
          <span>⚠</span>
          <span>{error}</span>
        </div>
      )}

      <div className={styles.buttons}>
        <button
          onClick={handleStart}
          disabled={!canStart || loading}
          className={canStart ? styles.btnPrimary : ''}
        >
          {loading && currentState === 'pending' ? 'Starting...' : 'Start'}
        </button>

        <button
          onClick={handlePause}
          disabled={!canPause || loading}
        >
          {loading && currentState === 'running' ? 'Pausing...' : 'Pause'}
        </button>

        <button
          onClick={handleResume}
          disabled={!canResume || loading}
          className={canResume ? styles.btnPrimary : ''}
        >
          {loading && currentState === 'paused' ? 'Resuming...' : 'Resume'}
        </button>

        {!isYoloMode && (
          <button
            onClick={handleNextTurn}
            disabled={!canTriggerTurn || triggeringTurn}
            className={shouldConclude ? styles.btnConclude : (canTriggerTurn ? styles.btnPrimary : '')}
            title={shouldConclude ? (policyConfig?.enable_host ? 'Host will provide final conclusion' : 'All rounds complete - End meeting') : (!apiKey ? 'Add OpenRouter API key in Settings' : 'Trigger next agent to speak')}
          >
            {triggeringTurn ? '🤔 Agent thinking...' : shouldConclude ? '🏁 Conclude Meeting' : '▶ Next Turn'} {!triggeringTurn && !shouldConclude && currentState === 'running' && !isYoloMode ? <span style={{opacity: 0.6, fontSize: '0.85em'}}>(Space)</span> : null}
          </button>
        )}

        {!isYoloMode && !shouldConclude && (currentState === 'pending' || currentState === 'running') && (
          <button
            onClick={handleStartAutoMode}
            disabled={startingAuto || !apiKey}
            className={styles.btnAuto}
            title={!apiKey
              ? 'Add OpenRouter API key in Settings'
              : 'Run the whole session automatically — each panel member speaks in turn until all rounds are complete'}
          >
            {startingAuto ? '⚡ Starting Auto Mode…' : '⚡ Auto Mode'}
          </button>
        )}

        {isYoloMode && currentState !== 'ended' && (
          yoloStatus === 'paused' ? (
            <button
              onClick={handleResumeYolo}
              disabled={pausingYolo}
              className={styles.btnAuto}
              title="Resume automatic turns"
            >
              {pausingYolo ? 'Resuming…' : '⚡ Resume Auto'}
            </button>
          ) : (
            <button
              onClick={handlePauseYolo}
              disabled={pausingYolo}
              className={styles.btnAuto}
              title="Pause automatic turns — you can resume any time"
            >
              {pausingYolo ? 'Pausing…' : '⏸ Pause Auto'}
            </button>
          )
        )}

        {canExtend && (
          <button
            onClick={handleExtend}
            disabled={extending}
            className={styles.btnExtend}
            title={policyConfig?.max_rounds ? 'Add 2 more rounds' : 'Add 15 more minutes'}
          >
            {extending ? 'Extending...' : policyConfig?.max_rounds ? '⏱️ +2 Rounds' : '⏱️ +15 Min'}
          </button>
        )}

        <button
          onClick={() => setShowEndConfirm(true)}
          disabled={!canEnd || loading}
          className={styles.btnDanger}
        >
          End Meeting
        </button>
      </div>

      {showEndConfirm && (
        <div className={styles.confirmSheet}>
          <div className={styles.confirmContent}>
            <h4>End this meeting?</h4>
            <p>
              Once ended, the debate will stop and you can generate a summary with minutes and action items.
            </p>
            <div className={styles.confirmActions}>
              <button
                className={styles.btnSecondary}
                onClick={() => setShowEndConfirm(false)}
              >
                Cancel
              </button>
              <button
                className={styles.btnDanger}
                onClick={handleEnd}
              >
                End Meeting
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
