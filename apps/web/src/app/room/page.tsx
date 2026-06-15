'use client';

import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import DebateSelector from '@/components/room/DebateSelector';
import EventFeed from '@/components/room/EventFeed';
import DebateControls from '@/components/room/DebateControls';
import DebateTimer from '@/components/room/DebateTimer';
import AgentBehaviorsPanel from '@/components/room/AgentBehaviorsPanel';
import InterveneComposer from '@/components/room/InterveneComposer';
import SummaryReport from '@/components/room/SummaryReport';
import DocumentPanel from './DocumentPanel';
import MockDefenseRoom from '@/components/room/MockDefenseRoom';
import VoiceDefenseRoom from '@/components/room/VoiceDefenseRoom';
import { useDebateRoom } from '@/hooks/useDebateRoom';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import * as api from '@/lib/api';
import styles from './room.module.css';

/**
 * Room Page - Live Debate Control Center
 * 
 * Data Isolation: All components receive debateId prop and only fetch/display
 * data for that specific debate. No cross-debate data leakage.
 * - EventFeed: filters events by debateId via WebSocket stream
 * - DebateControls: actions scoped to debateId
 * - InterveneComposer: interventions sent to debateId
 * - SummaryReport: summary generated for debateId
 * - AgendaPanel: localStorage keyed by debateId
 */
function RoomPageContent() {
  const searchParams = useSearchParams();
  const { apiKey: openrouterKey } = useOpenRouterKey();
  const [debateId, setDebateId] = useState<string | null>(null);
  const [debateTitle, setDebateTitle] = useState<string>('');
  const [debateState, setDebateState] = useState<string>('pending');
  const [isYoloMode, setIsYoloMode] = useState(false);
  const [yoloStatus, setYoloStatus] = useState<string | null>(null);
  const [participants, setParticipants] = useState<{ name: string; id: string }[]>([]);
  const [onlineParticipants, setOnlineParticipants] = useState<Set<string>>(new Set());
  const [typingParticipants, setTypingParticipants] = useState<Set<string>>(new Set());
  const typingTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const [policyConfig, setPolicyConfig] = useState<any>(null);
  const [participantTurnCounts, setParticipantTurnCounts] = useState<Record<string, number>>({});
  const [debateStartedAt, setDebateStartedAt] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'transcript' | 'document' | 'defense' | 'voice'>('transcript');

  const handleDebateLoaded = (id: string, title: string, state: string) => {
    setDebateId(id);
    setDebateTitle(title);
    setDebateState(state.toLowerCase());
    console.log('🎯 Debate loaded:', { id, title, state: state.toLowerCase() });
    // Auto-switch to requested tab from URL
    const tabParam = searchParams.get('tab');
    if (tabParam === 'defense' || tabParam === 'voice') {
      setActiveTab(tabParam);
    }
  };

  // Auto-load debate from URL params (e.g., from setup flow)
  useEffect(() => {
    const debateIdFromUrl = searchParams.get('debate_id');
    if (debateIdFromUrl && !debateId) {
      // Auto-load the debate
      api.getDebate(debateIdFromUrl)
        .then(debate => {
          handleDebateLoaded(debate.debate_id, debate.title || 'Untitled', debate.state);
          setPolicyConfig(debate.policy_config || {});
          setDebateStartedAt(debate.started_at || null);
          setIsYoloMode(debate.autonomous_mode || false);
          console.log('📊 Policy Config loaded:', debate.policy_config);
          console.log('⏰ Debate started at:', debate.started_at);
          console.log('🚀 YOLO Mode:', debate.autonomous_mode);
          
          // Check for document
          fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/debates/${debate.debate_id}/document`)
            .then(res => res.ok ? res.json() : null)
            .then(doc => {
              if (doc && doc.document_id) {
                setDocumentId(doc.document_id);
                console.log('📄 Document found:', doc.document_id);
              }
            })
            .catch(err => console.log('No document for this debate'));
        })
        .catch(err => {
          console.error('Failed to auto-load debate:', err);
        });
    }
  }, [searchParams, debateId]);

  // WebSocket connection for realtime room transport (single connection owner)
  const { events, sendCommand, connectionStatus } = useDebateRoom({
    debateId: debateId || '',
    enabled: !!debateId && debateState !== 'ended',
  });

  // Update policy config and debate metadata when new agent messages arrive or state changes
  useEffect(() => {
    if (!debateId) return;
    
    const hasNewAgentMessage = events.some(e => e.type === 'agent_message');
    const hasStateChange = events.some(e => e.type === 'state_update');
    
    if (hasNewAgentMessage || hasStateChange) {
      api.getDebate(debateId)
        .then(debate => {
          setPolicyConfig(debate.policy_config || {});
          setDebateStartedAt(debate.started_at || null);
          setIsYoloMode(debate.autonomous_mode || false);
          if (hasStateChange) {
            setDebateState(debate.state);
          }
        })
        .catch(err => {
          console.error('Failed to refresh debate policy:', err);
        });
    }
    
    // Calculate turn counts per participant
    const counts: Record<string, number> = {};
    events.forEach(event => {
      if (event.type === 'agent_message' && event.payload?.agent_name) {
        const agentName = event.payload.agent_name;
        counts[agentName] = (counts[agentName] || 0) + 1;
      }
    });
    setParticipantTurnCounts(counts);
  }, [events.length, debateId]); // Only when events array length changes

  // Presence join/leave via WebSocket
  useEffect(() => {
    if (!debateId || !sendCommand || connectionStatus !== 'connected') return;

    // Join presence via WebSocket
    sendCommand('join_presence').catch(err => {
      // Non-fatal — presence is best-effort
      console.warn('Failed to join presence:', err);
    });

    // Leave presence on unmount/disconnect — best-effort, never surfaces an error
    return () => {
      try {
        sendCommand('leave_presence').catch(() => {
          // Silently ignore — WS may already be gone when component unmounts
        });
      } catch {
        // sendCommand itself may throw synchronously if client is null
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debateId, connectionStatus]); // sendCommand is stable (useCallback with empty deps), exclude from deps to prevent infinite loop

  // Handle presence updates from EventFeed
  const handlePresenceUpdate = useCallback((participantId: string, action: 'join' | 'leave') => {
    setOnlineParticipants(prev => {
      const next = new Set(prev);
      if (action === 'join') {
        next.add(participantId);
      } else {
        next.delete(participantId);
      }
      return next;
    });
  }, []);

  // Handle typing signals from EventFeed
  const handleTyping = useCallback((participantId: string) => {
    // Add to typing set
    setTypingParticipants(prev => new Set(prev).add(participantId));

    // Clear existing timer
    const existing = typingTimersRef.current.get(participantId);
    if (existing) {
      clearTimeout(existing);
    }

    // Remove after 3 seconds
    const timer = setTimeout(() => {
      setTypingParticipants(prev => {
        const next = new Set(prev);
        next.delete(participantId);
        return next;
      });
      typingTimersRef.current.delete(participantId);
    }, 3000);

    typingTimersRef.current.set(participantId, timer);
  }, []); // typingTimersRef is stable, exclude from deps

  // Load agenda data from localStorage
  const getAgendaData = () => {
    if (!debateId) return { items: [], outcome: { desired: '', criteria: [] } };
    
    const agendaKey = `agenda_${debateId}`;
    const outcomeKey = `outcome_${debateId}`;
    
    const items = JSON.parse(localStorage.getItem(agendaKey) || '[]');
    const outcome = JSON.parse(localStorage.getItem(outcomeKey) || '{"desired":"","criteria":[]}');
    
    return { items, outcome };
  };

  // Fetch participants when debate is loaded
  useEffect(() => {
    if (!debateId) return;

    api.getDebate(debateId)
      .then((data) => {
        if (data.participants) {
          const participantList = data.participants
            .filter((p: any) => {
              const name = p.agent_config?.name || p.role_name || '';
              return name !== 'Ultimate Host';
            })
            .map((p: any) => ({
              id: p.participant_id,
              name: p.agent_config?.name || p.role_name || 'Unknown Agent',
            }));
          setParticipants(participantList);
          console.log('👥 Participants loaded:', participantList.length);
        }
      })
      .catch((err) => console.error('Failed to fetch participants:', err));
  }, [debateId]);

  return (
    <>
      <AppNav />
      <div className={styles.room}>
      {/* Left Rail: Meeting Info */}
      <aside className={styles.leftRail}>
        <div className={styles.meetingInfo}>
          {debateId && (
            <>
              <div className={styles.debateHeader}>
                <h1 className={styles.debateTitle}>{debateTitle || 'Untitled'}</h1>
                <div className={styles.badges}>
                  <div className={`${styles.stateBadge} ${styles[`state-${debateState}`]}`}>
                    {debateState?.toUpperCase()}
                  </div>
                  {isYoloMode && (
                    <div className={styles.yoloBadge} title="Auto Mode — turns run automatically">
                      ⚡ AUTO
                    </div>
                  )}
                </div>
              </div>
              
              
              {/* Turn & Progress Info */}
              {policyConfig && debateState === 'running' && participants.length > 0 && (
                <div className={styles.turnInfo}>
                  <div className={styles.turnNumber}>
                    <span className={styles.turnLabel}>TURN</span>
                    <span className={styles.turnValue}>#{Math.floor((policyConfig.total_turns_taken || 0) / participants.length) + 1}</span>
                  </div>
                  <div className={styles.turnDetails}>
                    <div className={styles.turnStat}>
                      <span className={styles.statLabel}>Total Messages</span>
                      <span className={styles.statValue}>{policyConfig.total_turns_taken || 0}</span>
                    </div>
                    {policyConfig.max_rounds && (
                      <div className={styles.turnStat}>
                        <span className={styles.statLabel}>Max Rounds</span>
                        <span className={styles.statValue}>{policyConfig.max_rounds}</span>
                      </div>
                    )}
                  </div>
                  {policyConfig.max_rounds && (
                    <div className={styles.progressBar}>
                      <div 
                        className={styles.progressFill} 
                        style={{
                          width: `${Math.min(100, ((Math.floor((policyConfig.total_turns_taken || 0) / participants.length) + 1) / policyConfig.max_rounds) * 100)}%`
                        }}
                      />
                    </div>
                  )}
                </div>
              )}

              <section className={styles.section}>
                <h3>Review Panel</h3>
                <div className={styles.participantsList}>
                  {participants.length === 0 ? (
                    <p className={styles.empty}>No participants yet</p>
                  ) : (
                    participants.map((p) => {
                      const turnCount = participantTurnCounts[p.name] || 0;
                      const maxRounds = policyConfig?.max_rounds || '?';
                      
                      return (
                        <div key={p.id} className={styles.participant}>
                          <span className={styles.participantName}>{p.name}</span>
                          {debateState === 'running' && (
                            <span className={styles.participantTurns}>
                              {turnCount}/{maxRounds}
                            </span>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </section>
            </>
          )}
        </div>
      </aside>

      {/* Center: Tabbed View */}
      <main className={styles.center}>
        {!debateId ? (
          <div className={styles.emptyState}>
            <h2>Review Room</h2>
            <p>Load an existing review session or create a new one to get started.</p>
            <div className={styles.selectorWrapper}>
              <DebateSelector onDebateLoaded={handleDebateLoaded} />
            </div>
          </div>
        ) : (
          <>
            {/* Tab Navigation — always visible once debate is loaded */}
            <div className={styles.tabNav}>
              <button
                className={`${styles.tab} ${activeTab === 'transcript' ? styles.tabActive : ''}`}
                onClick={() => setActiveTab('transcript')}
              >
                {debateState === 'ended' ? 'Session Report' : 'Live Transcript'}
              </button>
              {documentId && (
                <button
                  className={`${styles.tab} ${activeTab === 'document' ? styles.tabActive : ''}`}
                  onClick={() => setActiveTab('document')}
                >
                  Document
                </button>
              )}
              <button
                className={`${styles.tab} ${activeTab === 'defense' ? styles.tabActive : ''}`}
                onClick={() => setActiveTab('defense')}
              >
                Practice Q&amp;A
              </button>
              <button
                className={`${styles.tab} ${activeTab === 'voice' ? styles.tabActive : ''}`}
                onClick={() => setActiveTab('voice')}
                title="Voice-powered practice — speak your answers aloud"
              >
                🎤 Voice Practice
              </button>
            </div>

            {/* Tab Content */}
            <div className={styles.tabContent}>
              {activeTab === 'transcript' && (
                debateState === 'ended' ? (
                  <div className={styles.reportScroll}>
                    <SummaryReport
                      debateId={debateId}
                      agendaData={getAgendaData()}
                      onStartPractice={() => setActiveTab('defense')}
                    />
                  </div>
                ) : (
                  <>
                    <EventFeed 
                      events={events}
                      connectionStatus={connectionStatus}
                      onPresenceUpdate={handlePresenceUpdate}
                      onTyping={handleTyping}
                    />
                    <InterveneComposer 
                      debateId={debateId} 
                      participants={participants}
                      sendCommand={sendCommand}
                    />
                  </>
                )
              )}
              {activeTab === 'document' && (
                <div className={styles.documentView}>
                  {documentId && (
                    <DocumentPanel 
                      debateId={debateId} 
                      documentId={documentId}
                      userId="user-1"
                      userName="User"
                    />
                  )}
                </div>
              )}
              {activeTab === 'defense' && (
                <div style={{ flex: 1, overflowY: 'auto', padding: '16px 0' }}>
                  <MockDefenseRoom debateId={debateId} openrouterKey={openrouterKey || ''} />
                </div>
              )}
              {activeTab === 'voice' && (
                <div style={{ flex: 1, overflowY: 'auto', padding: '16px 0' }}>
                  <VoiceDefenseRoom debateId={debateId} openrouterKey={openrouterKey || ''} />
                </div>
              )}
            </div>
          </>
        )}
      </main>

      {/* Right Panel: Controls & Document */}
      <aside className={styles.rightPanel}>
        {debateId ? (
          <>
            <DebateControls
              debateId={debateId}
              currentState={debateState}
              isYoloMode={isYoloMode}
              yoloStatus={yoloStatus}
              policyConfig={policyConfig}
              totalTurns={policyConfig?.total_turns_taken || 0}
              participantCount={participants.length}
              onPolicyUpdate={() => {
                // Refetch policy config when extended
                api.getDebate(debateId).then(debate => {
                  setPolicyConfig(debate.policy_config || {});
                }).catch(err => console.error('Failed to refresh policy:', err));
              }}
              onStateChange={(newState) => setDebateState(newState)}
              onYoloStatusChange={setYoloStatus}
              onAutoModeChange={setIsYoloMode}
              sendCommand={sendCommand}
            />
          </>
        ) : (
          <div className={styles.hint}>
            Load or create a debate to access controls.
          </div>
        )}
      </aside>

      {/* Floating Agent Behaviors Panel */}
      {debateId && (
        <AgentBehaviorsPanel debateId={debateId} events={events} sendCommand={sendCommand} />
      )}
      </div>
    </>
  );
}

export default function RoomPage() {
  return (
    <Suspense fallback={<div>Loading room...</div>}>
      <RoomPageContent />
    </Suspense>
  );
}
