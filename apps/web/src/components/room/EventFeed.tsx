'use client';

import { useState, useRef, useEffect, ReactNode } from 'react';
import styles from './EventFeed.module.css';
import { WSEventEnvelope, ConnectionStatus } from '@/lib/wsClient';

interface EventFeedProps {
  events: WSEventEnvelope[];
  connectionStatus: ConnectionStatus;
  onPresenceUpdate?: (participantId: string, action: 'join' | 'leave') => void;
  onTyping?: (participantId: string) => void;
}

// Simple markdown parser for common patterns
function parseMarkdown(text: string): ReactNode {
  // Split by lines for list handling
  const lines = text.split('\n');
  const result: ReactNode[] = [];
  let key = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // Check for numbered list (1. 2. 3.)
    const numberedMatch = line.match(/^(\d+)\.\s+(.+)$/);
    if (numberedMatch) {
      result.push(
        <div key={key++} className={styles.listItem}>
          <span className={styles.listNumber}>{numberedMatch[1]}.</span>
          <span>{parseInlineMarkdown(numberedMatch[2])}</span>
        </div>
      );
      continue;
    }

    // Regular line with inline markdown
    if (line.trim()) {
      result.push(<div key={key++}>{parseInlineMarkdown(line)}</div>);
    } else {
      result.push(<br key={key++} />);
    }
  }

  return <>{result}</>;
}

// Parse inline markdown (bold, italic, code, mentions)
function parseInlineMarkdown(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;

  // Pattern: **bold**, *italic*, `code`, @mentions (including quoted multi-word names)
  // Updated pattern to match @"Full Name" or @SingleWord
  const pattern = /(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`(.+?)`)|(@"([^"]+)")|(@[\w-]+)/g;
  
  let match;
  while ((match = pattern.exec(text)) !== null) {
    // Add text before match
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }

    if (match[1]) {
      // **bold**
      parts.push(<strong key={key++}>{match[2]}</strong>);
    } else if (match[3]) {
      // *italic*
      parts.push(<em key={key++}>{match[4]}</em>);
    } else if (match[5]) {
      // `code`
      parts.push(<code key={key++} className={styles.inlineCode}>{match[6]}</code>);
    } else if (match[7]) {
      // @"Full Name" mention (quoted)
      parts.push(<span key={key++} className={styles.mention}>@{match[8]}</span>);
    } else if (match[9]) {
      // @SingleWord mention
      parts.push(<span key={key++} className={styles.mention}>{match[9]}</span>);
    }

    lastIndex = pattern.lastIndex;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

export default function EventFeed({ events: wsEvents, connectionStatus, onPresenceUpdate, onTyping }: EventFeedProps) {
  const [displayEvents, setDisplayEvents] = useState<WSEventEnvelope[]>([]);
  const feedRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Group thinking events with their corresponding agent messages
  useEffect(() => {
    const shouldFilterOut = [
      'state_update',
      'typing',
      'presence_update',
    ];
    
    const filtered = wsEvents.filter((event) => {

      // Handle side-effect events but don't display them
      if (event.type === 'presence_update' && onPresenceUpdate) {
        const action = event.payload?.action;
        const participantId = event.payload?.participant_id;
        if (action && participantId) {
          onPresenceUpdate(participantId, action);
        }
      }

      if (event.type === 'typing' && onTyping) {
        const participantId = event.payload?.participant_id;
        if (participantId && !event.payload?.ping) {
          onTyping(participantId);
        }
      }

      return !shouldFilterOut.includes(event.type);
    });
    
    // Get all thinking events
    const allThinking = wsEvents.filter(e => e.type === 'agent_thinking');
    
    // Get all messages
    const allMessages = filtered.filter(e => e.type === 'agent_message');
    
    // Process events
    const processed: any[] = [];
    
    filtered.forEach(event => {
      if (event.type === 'agent_message') {
        // Attach thinking that came before this message
        const agentName = event.payload?.agent_name;
        const thinkingForMessage = allThinking.filter(t => 
          t.payload?.agent_name === agentName &&
          t.sequence_number < event.sequence_number &&
          t.sequence_number > (event.sequence_number - 80)
        );
        
        processed.push({ ...event, thinkingEvents: thinkingForMessage });
      } else if (event.type !== 'agent_thinking') {
        processed.push({ ...event, thinkingEvents: [] });
      }
    });
    
    // Show ALL thinking events that don't have a message yet (live)
    allThinking.forEach(thinkEvent => {
      const agentName = thinkEvent.payload?.agent_name;
      if (!agentName) return;
      
      // Check if this agent has a message AFTER this thinking event
      const hasLaterMessage = allMessages.some(m => {
        if (m.payload?.agent_name !== agentName) return false;
        
        // If thinking event has no sequence_number, fall back to timestamp comparison
        if (thinkEvent.sequence_number == null) {
          const thinkTime = thinkEvent.occurred_at ? new Date(thinkEvent.occurred_at).getTime() : 0;
          const msgTime = m.occurred_at ? new Date(m.occurred_at).getTime() : 0;
          return msgTime > thinkTime;
        }
        
        // Normal sequence number comparison
        return m.sequence_number != null && m.sequence_number > thinkEvent.sequence_number;
      });
      
      // Show inline if no later message exists
      if (!hasLaterMessage) {
        processed.push({
          ...thinkEvent,
          isLiveThinking: true,
          thinkingEvents: []
        });
      }
    });
    
    processed.sort((a, b) => (a.sequence_number || 0) - (b.sequence_number || 0));
    setDisplayEvents(processed);
  }, [wsEvents, onPresenceUpdate, onTyping]);

  // Auto-scroll on new events
  useEffect(() => {
    if (autoScroll && feedRef.current) {
      setTimeout(() => {
        feedRef.current?.scrollTo({
          top: feedRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }, 100);
    }
  }, [displayEvents, autoScroll]);

  const handleScroll = () => {
    if (!feedRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = feedRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setAutoScroll(isNearBottom);
  };

  const scrollToBottom = () => {
    feedRef.current?.scrollTo({
      top: feedRef.current.scrollHeight,
      behavior: 'smooth',
    });
    setAutoScroll(true);
  };

  return (
    <div className={styles.feedContainer}>
      <div className={styles.feedHeader}>
        <h2>Live Feed</h2>
        <div className={styles.connectionStatus}>
          <span className={`${styles.statusDot} ${styles[connectionStatus]}`} />
          <span className={styles.statusText}>
            {connectionStatus === 'connected' ? 'Connected' : 
             connectionStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
          </span>
        </div>
      </div>

      <div 
        ref={feedRef}
        className={styles.feed}
        onScroll={handleScroll}
      >
        {displayEvents.length === 0 ? (
          <div className={styles.emptyState}>
            <p>No messages yet. The debate will appear here when it starts.</p>
          </div>
        ) : (
          displayEvents.map((event, index) => {
            // Turn = complete round where ALL participants spoke
            const turn = event.payload?.turn;
            const previousEvent = index > 0 ? displayEvents[index - 1] : null;
            const previousTurn = previousEvent?.payload?.turn;
            
            // Show separator when turn number changes
            const showTurnSeparator = turn && turn !== previousTurn;

            return (
              <EventCard 
                key={event.event_id} 
                event={event} 
                showTurnSeparator={showTurnSeparator}
                turnNumber={turn}
              />
            );
          })
        )}
      </div>

      {!autoScroll && displayEvents.length > 0 && (
        <button className={styles.jumpToBottom} onClick={scrollToBottom}>
          ↓ Jump to latest
        </button>
      )}
    </div>
  );
}

interface TurnCitation {
  chunk_id: string;
  doc_title: string;
  material_id?: string | null;
  page_num?: number | null;
  sha256?: string | null;
  sha256_verified: boolean;
  method: string;
  score: number;
  claim: string;
  chunk_excerpt: string;
  highlight?: { start: number; end: number } | null;
}

/** Glass-Box chips under a live panel message: each verified claim links to its
 *  source line; a message with zero grounded claims is flagged honestly. */
function CitationChips({ citations }: { citations: TurnCitation[] }) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  if (citations.length === 0) {
    return (
      <div className={styles.citationRow}>
        <span className={styles.citationChipGap} title="No claim in this message could be matched to your uploaded materials">
          ⚠ no verified source
        </span>
      </div>
    );
  }

  const open = openIdx !== null ? citations[openIdx] : null;
  return (
    <div className={styles.citationBlock}>
      <div className={styles.citationRow}>
        {citations.map((c, i) => (
          <button
            key={c.chunk_id + i}
            className={`${styles.citationChip} ${openIdx === i ? styles.citationChipActive : ''}`}
            onClick={() => setOpenIdx(openIdx === i ? null : i)}
            title={c.sha256_verified ? 'Source verified — click to see the exact line' : 'Source linked — click to view'}
          >
            {c.sha256_verified ? '🔒' : '📄'} {c.doc_title}
            {c.page_num != null && ` · p.${c.page_num}`}
          </button>
        ))}
      </div>
      {open && (
        <div className={styles.citationSource}>
          <div className={styles.citationVerify}>
            {open.sha256_verified ? '🔒 GROUNDED — sha256 verified' : '📄 Source linked'}
            {open.sha256 && <code className={styles.citationHash}>{open.sha256.slice(0, 16)}…</code>}
          </div>
          <p className={styles.citationExcerpt}>
            {open.highlight && open.highlight.start < open.highlight.end ? (
              <>
                {open.chunk_excerpt.slice(0, open.highlight.start)}
                <mark>{open.chunk_excerpt.slice(open.highlight.start, open.highlight.end)}</mark>
                {open.chunk_excerpt.slice(open.highlight.end)}
              </>
            ) : (
              open.chunk_excerpt
            )}
          </p>
          <div className={styles.citationClaim}>Claim: “{open.claim}”</div>
        </div>
      )}
    </div>
  );
}

function EventCard({ event, showTurnSeparator, turnNumber }: { event: WSEventEnvelope; showTurnSeparator?: boolean; turnNumber?: number }) {
  // Thinking collapsed by default to avoid spam
  const hasThinking = (event as any).thinkingEvents?.length > 0;
  const [expanded, setExpanded] = useState(false);
  const [detailsExpanded, setDetailsExpanded] = useState(false);

  const getEventColor = (type: string) => {
    if (type === 'agent_thinking') return '#8b5cf6'; // Purple for thinking
    if (type === 'agent_message') return '#0070F3';
    if (type === 'human_message') return '#0070F3';
    if (type === 'intervention') return '#0070F3';
    if (type === 'summary') return '#0070F3';
    if (type === 'error') return '#E00';
    return '#0070F3';
  };

  const getActor = () => {
    // For thinking events, show the agent who is thinking
    if (event.type === 'agent_thinking' && event.payload?.agent_name) {
      return `${event.payload.agent_name} (thinking)`;
    }
    if (event.payload?.agent_name) return event.payload.agent_name;
    if (event.payload?.actor) return event.payload.actor;
    if (event.sender_type === 'agent') return 'Agent';
    if (event.sender_type === 'user') return 'User';
    return 'System';
  };

  const getMessage = () => {
    if (event.payload?.message) return event.payload.message;
    if (event.payload?.content) return event.payload.content;
    if (event.payload?.text) return event.payload.text;
    return null;
  };

  const getEventTypeLabel = (type: string) => {
    if (type === 'agent_message') return 'Message';
    if (type === 'human_message') return '👤 You';
    if (type === 'intervention') return 'Intervention';
    if (type === 'system_message') return '⚙️ System';
    if (type === 'turn_start') return '▶️ Turn Start';
    if (type === 'turn_end') return '⏸️ Turn End';
    if (type === 'state_update') return 'State';
    if (type === 'strategic_action') return 'Strategic Move';
    if (type === 'agent_thinking') return ''; // No label, just show content
    if (type === 'error') return '❌ Error';
    return type.replace(/_/g, ' ');
  };
  
  const renderThinkingBlock = (payload: any) => {
    const stage = payload?.stage || 'Processing';
    const status = payload?.status || 'Thinking...';
    const details = payload?.details || [];
    const thinkingType = payload?.thinking_type || '';
    
    // Icon based on thinking type
    const getThinkingIcon = () => {
      if (thinkingType.includes('reasoning')) return '🤔';
      if (thinkingType.includes('generating')) return '✍️';
      if (thinkingType.includes('validating')) return '–';
      if (thinkingType.includes('issues')) return '!';
      if (thinkingType.includes('corrected')) return '🔧';
      if (thinkingType.includes('regenerating')) return '↺';
      return '💭';
    };
    
    return (
      <div className={styles.thinkingBlock}>
        <div className={styles.thinkingHeader}>
          <span className={styles.thinkingIcon}>{getThinkingIcon()}</span>
          <span className={styles.thinkingStage}>{stage}</span>
        </div>
        <div className={styles.thinkingStatus}>{status}</div>
        {details.length > 0 && (
          <div className={styles.thinkingDetails}>
            {details.map((detail: string, i: number) => (
              <div key={i} className={styles.thinkingDetail}>
                {detail}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };
  
  const renderStrategicAction = (payload: any) => {
    const move = payload?.move;
    const agent = payload?.agent;
    
    if (!move) return null;
    
    return (
      <div className={styles.strategicAction}>
        <div className={styles.strategicHeader}>
          <strong>{agent}</strong> proposes: <strong>{move.action.toUpperCase()}</strong>
        </div>
        {move.question && <div className={styles.strategicDetail}>"{move.question}"</div>}
        {move.options && (
          <div className={styles.strategicOptions}>
            {move.options.map((opt: string, i: number) => (
              <span key={i} className={styles.option}>• {opt}</span>
            ))}
          </div>
        )}
        {move.sub_questions && (
          <div className={styles.strategicDetail}>
            {move.sub_questions.map((q: string, i: number) => (
              <div key={i}>→ {q}</div>
            ))}
          </div>
        )}
        {move.what_needed && <div className={styles.strategicDetail}>{move.what_needed}</div>}
        {move.proposal && <div className={styles.strategicDetail}>{move.proposal}</div>}
        {move.reason && <div className={styles.strategicDetail}>{move.reason}</div>}
      </div>
    );
  };

  return (
    <>
      {showTurnSeparator && turnNumber ? (
        <div className={styles.turnSeparator}>
          <div className={styles.turnLine} />
          <span className={styles.turnBadge}>Round {turnNumber}</span>
          <div className={styles.turnLine} />
        </div>
      ) : null}
      <div className={`${styles.event} ${event.type === 'agent_thinking' && (event as any).isLiveThinking ? styles.thinkingEventCard : ''}`} style={{ '--event-color': getEventColor(event.type) } as any}>
        {/* Hide header for live thinking events */}
        {!(event.type === 'agent_thinking' && (event as any).isLiveThinking) && (
          <div className={styles.eventHeader}>
            <div className={styles.eventMeta}>
              <span className={styles.actor}>{getActor()}</span>
              <span className={styles.eventType}>{getEventTypeLabel(event.type)}</span>
            </div>
            <span className={styles.timestamp}>
              {event.occurred_at ? new Date(event.occurred_at).toLocaleTimeString() : 'N/A'}
            </span>
          </div>
        )}

        {/* Live thinking (individual steps, real-time) */}
        {event.type === 'agent_thinking' && (event as any).isLiveThinking ? (
          <div className={styles.liveThinkingStep}>
            {renderThinkingBlock(event.payload)}
          </div>
        ) : event.type === 'strategic_action' ? (
          renderStrategicAction(event.payload)
        ) : getMessage() ? (
          <>
            <div className={styles.message}>
              {parseMarkdown(getMessage()!)}
            </div>

            {/* Glass-Box: verified source chips for this turn */}
            {event.type === 'agent_message' && Array.isArray(event.payload?.citations) && (
              <CitationChips citations={event.payload.citations} />
            )}

            {/* Show thinking process if available */}
            {(event as any).thinkingEvents && (event as any).thinkingEvents.length > 0 && (
              <div className={styles.thinkingSection}>
                <button
                  className={styles.showThinkingBtn}
                  onClick={() => setExpanded(!expanded)}
                  type="button"
                  data-expanded={expanded}
                >
                  <span style={{ opacity: 0.7, marginRight: '6px' }}>💭</span>
                  {expanded ? 'Hide' : 'View'} reasoning · {(event as any).thinkingEvents.length} {(event as any).thinkingEvents.length === 1 ? 'step' : 'steps'}
                </button>
                
                {expanded && (
                  <div className={styles.thinkingSteps}>
                    {(event as any).thinkingEvents.map((thinkEvent: any, idx: number) => (
                      <div key={idx} className={styles.thinkingStep}>
                        {renderThinkingBlock(thinkEvent.payload)}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        ) : null}

        {event.type !== 'agent_thinking' && (
          <button
            className={styles.expandBtn}
            onClick={() => setDetailsExpanded(!detailsExpanded)}
          >
            {detailsExpanded ? 'Hide details' : 'Show details'}
          </button>
        )}

        {detailsExpanded && (
          <div className={styles.details}>
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Event ID:</span>
              <span className={styles.detailValue}>{event.event_id}</span>
            </div>
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Sequence:</span>
              <span className={styles.detailValue}>#{event.sequence_number}</span>
            </div>
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Sender:</span>
              <span className={styles.detailValue}>{event.sender_type} ({event.sender_id || 'system'})</span>
            </div>
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Payload:</span>
              <pre className={styles.payloadPre}>{JSON.stringify(event.payload, null, 2)}</pre>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
