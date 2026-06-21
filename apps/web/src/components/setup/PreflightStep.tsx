/**
 * Preflight Step - Agent preparation before debate starts
 * Shows per-agent progress, retry/skip actions, and prep pack previews
 */

'use client';

import { useState, useEffect } from 'react';
import * as api from '@/lib/api';
import { usePreflight } from '@/hooks/usePreflight';
import { SkipDialog } from './PreflightDialogs';
import { PrepPackDialog } from './PrepPackDialog';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import styles from './SetupSteps.module.css';

interface PreflightStepProps {
  debateId: string | null;
  participants: api.SetupParticipant[];
  participantIds: string[];
  onCanContinueChange?: (canContinue: boolean) => void;
  meetingTitle?: string;
  meetingPurpose?: string;
  meetingAgenda?: string[];
  desiredOutcomes?: string[];
}

// Real-time status component for running agents
function AnimatedStatus({ 
  participantRunId, 
  participantId 
}: { 
  participantRunId: string;
  participantId: string;
}) {
  const [progressMessage, setProgressMessage] = useState('⏳ Waiting to start...');
  
  useEffect(() => {
    // Listen for WebSocket preflight progress events
    const handlePreflightProgress = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'preflight_progress' && data.participant_id === participantId) {
          setProgressMessage(data.message || 'Processing...');
        }
      } catch (err) {
        // Ignore parse errors
      }
    };
    
    // Try to attach to existing WebSocket connection
    // Note: This is a simplified version - in production you'd use a proper WebSocket hook
    window.addEventListener('message', handlePreflightProgress);
    
    return () => {
      window.removeEventListener('message', handlePreflightProgress);
    };
  }, [participantId]);
  
  return (
    <div style={{ 
      fontSize: '0.875rem', 
      color: 'var(--text-muted)', 
      marginTop: '0.5rem',
      fontStyle: 'italic',
      animation: 'pulse 2s ease-in-out infinite'
    }}>
      {progressMessage}
    </div>
  );
}

export function PreflightStep({
  debateId,
  participants,
  participantIds,
  onCanContinueChange,
  meetingTitle,
  meetingPurpose,
  meetingAgenda,
  desiredOutcomes,
}: PreflightStepProps) {
  const { apiKey } = useOpenRouterKey();
  const {
    status,
    isPolling,
    error,
    startPreflight,
    retryParticipant,
    skipParticipant,
    isStarted,
    isCompleted,
    canContinue,
    hasFailures,
    readyCount,
    totalCount,
  } = usePreflight();

  const [skipDialogOpen, setSkipDialogOpen] = useState(false);
  const [skipParticipantId, setSkipParticipantId] = useState<string | null>(null);
  const [skipReason, setSkipReason] = useState('');
  const [prepPackDialogOpen, setPrepPackDialogOpen] = useState(false);
  const [prepPackContent, setPrepPackContent] = useState<string | null>(null);
  const [prepPackMetadata, setPrepPackMetadata] = useState<Record<string, any> | null>(null);
  const [prepPackParticipantId, setPrepPackParticipantId] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [loadingPrepPack, setLoadingPrepPack] = useState(false);

  // Notify parent when readiness changes
  useEffect(() => {
    if (onCanContinueChange) {
      onCanContinueChange(canContinue);
    }
  }, [canContinue, onCanContinueChange]);

  // Clear "initializing" state when preflight actually starts
  useEffect(() => {
    if (isStarted) {
      setIsStarting(false);
    }
  }, [isStarted]);

  const handleStartPreflight = async () => {
    if (!debateId) return;
    if (!apiKey) return;

    setIsStarting(true);
    try {
      await startPreflight(debateId, apiKey);
      // Success - isStarting will be cleared when isStarted becomes true
      // But we need to reset it in case of edge cases
      setTimeout(() => setIsStarting(false), 2000);
    } catch (err: any) {
      console.error('Failed to start preflight:', err);
      setIsStarting(false);
    }
  };

  const handleRetry = async (participantId: string) => {
    if (!debateId) return;
    
    try {
      await retryParticipant(debateId, participantId);
    } catch (err: any) {
      console.error('Failed to retry:', err);
    }
  };

  const openSkipDialog = (participantId: string) => {
    setSkipParticipantId(participantId);
    setSkipReason('');
    setSkipDialogOpen(true);
  };

  const handleSkipConfirm = async () => {
    if (!debateId || !skipParticipantId || !skipReason.trim()) return;
    
    try {
      await skipParticipant(debateId, skipParticipantId, skipReason);
      setSkipDialogOpen(false);
      setSkipParticipantId(null);
      setSkipReason('');
    } catch (err: any) {
      console.error('Failed to skip:', err);
    }
  };

  const handleViewPrepPack = async (participantRun: api.ParticipantRunStatus) => {
    if (!participantRun.prep_pack_knowledge_id) return;
    
    setLoadingPrepPack(true);
    
    try {
      // Fetch the actual prep pack from backend
      const knowledgeUnit = await api.getAgentKnowledgeUnit(participantRun.prep_pack_knowledge_id);
      
      setPrepPackContent(knowledgeUnit.content || 'No content available');
      setPrepPackMetadata(knowledgeUnit.metadata || {});
      setPrepPackParticipantId(participantRun.participant_id);
      setPrepPackDialogOpen(true);
    } catch (error) {
      console.error('Failed to load prep pack:', error);
      alert('Failed to load prep pack. Please try again.');
    } finally {
      setLoadingPrepPack(false);
    }
  };

  const getParticipantName = (participantId: string): string => {
    const index = participantIds.indexOf(participantId);
    if (index !== -1 && index < participants.length) {
      return participants[index].name || participants[index].role_description || 'Participant';
    }
    return 'Unknown Participant';
  };

  const getParticipantRole = (participantId: string): string => {
    const index = participantIds.indexOf(participantId);
    if (index !== -1 && index < participants.length) {
      return participants[index].role_description || 'Agent';
    }
    return 'Agent';
  };

  const getInitials = (name: string): string => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const getStatusPill = (status: string, participantRunId?: string) => {
    const statusMap: Record<string, { label: string; className: string }> = {
      queued: { label: '⏳ Waiting...', className: styles.statusQueued },
      running: { label: '🚀 Preparing...', className: styles.statusRunning },
      success: { label: '✅ Ready', className: styles.statusSuccess },
      failed: { label: '❌ Failed', className: styles.statusFailed },
      skipped: { label: '⏭️ Skipped', className: styles.statusSkipped },
    };
    
    const config = statusMap[status] || { label: status, className: '' };
    
    return (
      <span className={`${styles.statusPill} ${config.className}`}>
        {config.label}
      </span>
    );
  };

  if (!debateId) {
    return (
      <div className={styles.stepContent}>
        <h2>Prepare your panel</h2>
        <div className={styles.alert} style={{ marginTop: '1.5rem' }}>
          <p>⚠️ Review session not created yet. Please complete previous steps first.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.stepContent}>
      <h2>Prepare your panel</h2>
      <p className={styles.stepDescription}>
        Panel members review your research materials and context before the session starts.
      </p>

      {error && (
        <div className={styles.alert} style={{ marginTop: '1.5rem', marginBottom: '1.5rem' }}>
          <p>⚠️ {error}</p>
        </div>
      )}

      {!isStarted && !isStarting && (
        <div style={{ marginTop: '2rem' }}>
          {!apiKey && (
            <div style={{
              background: 'var(--warning-bg, #fff8e1)',
              border: '1px solid var(--warning, #f5a623)',
              borderRadius: '8px',
              padding: '14px 18px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              fontSize: '0.9rem',
            }}>
              <span style={{ fontSize: '1.3rem' }}>🔑</span>
              <div>
                <strong style={{ color: 'var(--warning-dark, #b45309)' }}>OpenRouter API Key Required</strong>
                <p style={{ margin: '2px 0 0', color: 'var(--warning-dark, #b45309)' }}>
                  Add your key in{' '}
                  <a href="/settings" style={{ textDecoration: 'underline', fontWeight: 600 }}>
                    Settings
                  </a>{' '}
                  to prepare your panel.
                </p>
              </div>
            </div>
          )}
          <button
            onClick={handleStartPreflight}
            className={styles.btnPrimary}
            disabled={!apiKey}
            style={{
              padding: '1rem 2rem',
              fontSize: '1rem',
              opacity: apiKey ? 1 : 0.45,
              cursor: apiKey ? 'pointer' : 'not-allowed',
            }}
          >
            Start preparation
          </button>
          <p style={{ marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            This gathers context and prepares all agents in parallel — usually under a minute.
            Larger panels or heavy reasoning modes can take a few minutes.
          </p>
        </div>
      )}

      {isStarting && !isStarted && (
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>🚀</div>
          <p style={{ fontSize: '1rem', fontWeight: 500 }}>Initializing agent preparation...</p>
          <p style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            Setting up context and materials
          </p>
        </div>
      )}

      {isStarted && (
        <>
          <div className={styles.progressBar} style={{ marginTop: '1.5rem' }}>
            <div className={styles.progressBarLabel}>
              {readyCount} / {totalCount} ready
            </div>
            <div className={styles.progressBarTrack}>
              <div
                className={styles.progressBarFill}
                style={{ width: `${(readyCount / totalCount) * 100}%` }}
              />
            </div>
          </div>

          <div className={styles.participantsList} style={{ marginTop: '2rem' }}>
            {status?.participant_runs.map((participantRun) => {
              const name = getParticipantName(participantRun.participant_id);
              const initials = getInitials(name);

              // Check if web research was performed
              const webResearchPerformed = participantRun.metadata?.web_research_performed || false;
              const webSourcesCount = participantRun.metadata?.web_search_urls?.length || 0;
              const materialsCount = participantRun.metadata?.material_chunks_count || 0;
              const memoryCount = participantRun.metadata?.imported_chunks_count || 0;

              return (
                <div key={participantRun.participant_run_id} className={styles.participantCard}>
                  <div className={styles.participantAvatar}>
                    {initials}
                  </div>
                  <div className={styles.participantInfo}>
                    <div className={styles.participantNameRow}>
                      <div className={styles.participantName}>{name}</div>
                      {participantRun.status === 'success' && (
                        <div className={styles.badges}>
                          {webSourcesCount > 0 && (
                            <span className={styles.webBadge} title={`Researched ${webSourcesCount} web sources`}>
                              🌐 {webSourcesCount}
                            </span>
                          )}
                          {materialsCount > 0 && (
                            <span className={styles.materialBadge} title={`${materialsCount} materials analyzed`}>
                              📄 {materialsCount}
                            </span>
                          )}
                          {memoryCount > 0 && (
                            <span className={styles.memoryBadge} title={`${memoryCount} memory chunks`}>
                              🧠 {memoryCount}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    {getStatusPill(participantRun.status, participantRun.participant_run_id)}
                    {participantRun.status === 'running' && (
                      <AnimatedStatus 
                        participantRunId={participantRun.participant_run_id}
                        participantId={participantRun.participant_id}
                      />
                    )}
                  </div>
                  <div className={styles.participantActions}>
                    {participantRun.status === 'failed' && (
                      <button
                        onClick={() => handleRetry(participantRun.participant_id)}
                        className={styles.btnSecondary}
                        style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
                      >
                        Retry
                      </button>
                    )}
                    {(participantRun.status === 'queued' ||
                      participantRun.status === 'running' ||
                      participantRun.status === 'failed') && (
                      <button
                        onClick={() => openSkipDialog(participantRun.participant_id)}
                        className={styles.btnSecondary}
                        style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
                      >
                        Skip
                      </button>
                    )}
                    {participantRun.status === 'success' && participantRun.prep_pack_knowledge_id && (
                      <button
                        onClick={() => handleViewPrepPack(participantRun)}
                        disabled={loadingPrepPack}
                        className={styles.btnPrimary}
                        style={{ 
                          fontSize: '0.875rem', 
                          padding: '0.625rem 1.25rem',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          fontWeight: 600
                        }}
                      >
                        {loadingPrepPack ? (
                          <>⏳ Loading...</>
                        ) : (
                          <>📊 View Prep Pack</>
                        )}
                      </button>
                    )}
                    {participantRun.status === 'skipped' && participantRun.skip_reason && (
                      <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                        {participantRun.skip_reason}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {hasFailures && !isCompleted && (
            <div className={styles.alert} style={{ marginTop: '1.5rem' }}>
              <p>
                ⚠️ Some agents failed to prepare. You can retry individual agents or skip them to continue.
              </p>
            </div>
          )}

          {canContinue && hasFailures && (
            <div className={styles.alert} style={{ marginTop: '1.5rem' }}>
              <p>
                ⚠️ Some agents are skipped or failed. The debate will proceed with reduced context for these agents.
              </p>
            </div>
          )}

          {isPolling && (
            <div style={{ marginTop: '1.5rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              <span>Updating status...</span>
            </div>
          )}
        </>
      )}

      <SkipDialog
        isOpen={skipDialogOpen}
        skipReason={skipReason}
        onReasonChange={setSkipReason}
        onConfirm={handleSkipConfirm}
        onCancel={() => setSkipDialogOpen(false)}
      />

      <PrepPackDialog
        isOpen={prepPackDialogOpen}
        content={prepPackContent}
        metadata={prepPackMetadata}
        participantName={prepPackParticipantId ? getParticipantName(prepPackParticipantId) : 'Unknown'}
        participantRole={prepPackParticipantId ? getParticipantRole(prepPackParticipantId) : 'Unknown'}
        meetingTitle={meetingTitle}
        meetingPurpose={meetingPurpose}
        meetingAgenda={meetingAgenda}
        desiredOutcomes={desiredOutcomes}
        materialsCount={prepPackMetadata?.material_chunks_count || 0}
        memoryChunksCount={prepPackMetadata?.imported_chunks_count || 0}
        onClose={() => {
          setPrepPackDialogOpen(false);
          setPrepPackParticipantId(null);
          setPrepPackContent(null);
          setPrepPackMetadata(null);
        }}
      />
    </div>
  );
}
