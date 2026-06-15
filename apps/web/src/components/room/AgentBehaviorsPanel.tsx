'use client';

import { useState, useEffect } from 'react';
import styles from './AgentBehaviorsPanel.module.css';

interface Coalition {
  id: string;
  members: string[];
  formed_at: string;
  strategy?: string;
  goal?: string;
  type?: 'alliance' | 'rivalry';
}

interface PrivateMessage {
  id: string;
  from: string;
  to: string;
  message: string;
  timestamp: string;
}

interface SubTask {
  id: string;
  agent: string;
  task: string;
  status: 'planning' | 'executing' | 'completed';
  timestamp: string;
}

interface StrategicAction {
  id: string;
  agent: string;
  move: {
    action: string;
    question?: string;
    options?: string[];
    sub_topics?: string[];
    what_needed?: string;
    proposal?: string;
    reason?: string;
  };
  timestamp: string;
}

interface AgentBehaviorsPanelProps {
  debateId: string;
  events: any[];
  sendCommand?: (command: any, payload?: any) => Promise<any>;
}

export default function AgentBehaviorsPanel({ debateId, events, sendCommand }: AgentBehaviorsPanelProps) {
  const [coalitions, setCoalitions] = useState<Coalition[]>([]);
  const [privateMessages, setPrivateMessages] = useState<PrivateMessage[]>([]);
  const [subTasks, setSubTasks] = useState<SubTask[]>([]);
  const [strategicActions, setStrategicActions] = useState<StrategicAction[]>([]);
  const [activeTab, setActiveTab] = useState<'coalitions' | 'messages' | 'questions' | 'tasks' | 'actions'>('coalitions');
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [replyTexts, setReplyTexts] = useState<Map<string, string>>(new Map());
  const [seenQuestionIds, setSeenQuestionIds] = useState<Set<string>>(new Set());
  const [hasNewMessages, setHasNewMessages] = useState(false);
  
  // Filter messages sent to Host
  const questionsToHost = privateMessages.filter(msg => msg.to === 'Host');
  const agentToAgentMessages = privateMessages.filter(msg => msg.to !== 'Host');
  
  // Handle reply to agent question
  const handleReply = async (questionId: string, agentName: string) => {
    const replyText = replyTexts.get(questionId);
    if (!replyText?.trim() || !sendCommand) return;
    
    try {
      await sendCommand('intervene', {
        message: replyText,
        tagged_agents: [agentName]
      });
      
      // Clear the reply text
      setReplyTexts(prev => {
        const next = new Map(prev);
        next.delete(questionId);
        return next;
      });
    } catch (err) {
      console.error('Failed to send reply:', err);
    }
  };
  
  const updateReplyText = (questionId: string, text: string) => {
    setReplyTexts(prev => {
      const next = new Map(prev);
      next.set(questionId, text);
      return next;
    });
  };

  // Keyboard shortcut to close (Escape)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  useEffect(() => {
    // Process events to extract agent behaviors
    const newCoalitions: Coalition[] = [];
    const newMessages: PrivateMessage[] = [];
    const newTasks: SubTask[] = [];
    const newStrategicActions: StrategicAction[] = [];
    const newQuestionIds: string[] = [];

    events.forEach(event => {
      if (event.type === 'coalition_formed') {
        console.log('🤝 Coalition event:', event);
        newCoalitions.push({
          id: event.event_id,
          members: event.payload?.members || [],
          formed_at: event.occurred_at || event.payload?.timestamp,
          strategy: event.payload?.strategy,
          goal: event.payload?.goal,
          type: event.payload?.type || 'alliance'
        });
      } else if (event.type === 'private_message') {
        console.log('💬 Private message event:', event);
        // Backend uses 'from_agent' and 'to_agent' fields
        const toAgent = event.payload?.to_agent || event.payload?.to;
        if (toAgent === 'Host') {
          newQuestionIds.push(event.event_id);
        }
        newMessages.push({
          id: event.event_id,
          from: event.payload?.from_agent || event.payload?.from,
          to: toAgent,
          message: event.payload?.message,
          timestamp: event.occurred_at || event.payload?.timestamp
        });
      } else if (event.type === 'agent_subtask') {
        newTasks.push({
          id: event.event_id,
          agent: event.payload?.agent,
          task: event.payload?.task,
          status: event.payload?.status,
          timestamp: event.occurred_at || event.payload?.timestamp
        });
      } else if (event.type === 'strategic_action') {
        console.log('🎯 Strategic action event:', event);
        newStrategicActions.push({
          id: event.event_id,
          agent: event.payload?.agent,
          move: event.payload?.move || {},
          timestamp: event.occurred_at || event.payload?.timestamp
        });
      }
    });

    console.log('📊 Processed behaviors:', {
      coalitions: newCoalitions,
      messages: newMessages,
      tasks: newTasks
    });

    // Detect new messages for notification pulse
    if (newMessages.length > privateMessages.length && !isOpen) {
      setHasNewMessages(true);
    }
    
    setCoalitions(newCoalitions);
    setPrivateMessages(newMessages);
    setSubTasks(newTasks);
    setStrategicActions(newStrategicActions);
    
    // Auto-open panel ONLY for truly NEW questions (not seen before)
    const unseenQuestions = newQuestionIds.filter(id => !seenQuestionIds.has(id));
    if (unseenQuestions.length > 0 && !isOpen) {
      console.log('🔔 New question(s) detected, auto-opening panel');
      setIsOpen(true);
      setActiveTab('questions');
      // Mark these questions as seen
      setSeenQuestionIds(prev => {
        const next = new Set(prev);
        unseenQuestions.forEach(id => next.add(id));
        return next;
      });
    }
  }, [events, isOpen, seenQuestionIds, privateMessages.length]);

  // Calculate unread counts
  const unreadQuestionsCount = questionsToHost.length;
  const totalActivity = coalitions.length + privateMessages.length + subTasks.length;
  const hasActivity = totalActivity > 0;
  const hasUnreadQuestions = unreadQuestionsCount > 0;

  return (
    <>
      {/* Floating Toggle Button */}
      {!isOpen && (
        <button 
          className={`${styles.floatingToggle} ${hasNewMessages || hasUnreadQuestions ? styles.hasNotifications : ''}`}
          onClick={() => {
            setIsOpen(true);
            setHasNewMessages(false);
          }}
          title={hasActivity ? `${totalActivity} agent activities (${agentToAgentMessages.length} DMs, ${questionsToHost.length} questions)` : 'Agent Behaviors'}
        >
          🎭
          {hasActivity && (
            <span className={`${styles.notificationBadge} ${hasNewMessages ? styles.badgePulse : ''}`}>
              {totalActivity}
            </span>
          )}
        </button>
      )}

      {/* Overlay */}
      {isOpen && <div className={styles.overlay} onClick={() => setIsOpen(false)} />}

      {/* Floating Panel */}
      {isOpen && (
        <div className={`${styles.panel} ${styles.panelOpen} ${isMinimized ? styles.panelMinimized : ''}`}>
          <div className={styles.header}>
            <div className={styles.headerLeft}>
              <h3>🎭 Agent Activity</h3>
              <span className={styles.liveBadge}>● LIVE</span>
            </div>
            <div className={styles.headerActions}>
              <button 
                className={styles.minimizeBtn} 
                onClick={(e) => {
                  e.stopPropagation();
                  setIsMinimized(!isMinimized);
                }} 
                title={isMinimized ? "Expand" : "Minimize"}
              >
                {isMinimized ? '▢' : '−'}
              </button>
              <button 
                className={styles.closeBtn} 
                onClick={(e) => {
                  e.stopPropagation();
                  setIsOpen(false);
                  setIsMinimized(false);
                }} 
                title="Close (Esc)"
              >
                ✕
              </button>
            </div>
          </div>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'coalitions' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('coalitions')}
          title="Agent coalitions and alliances"
        >
          🤝 <span className={styles.tabLabel}>Groups</span> <span className={styles.count}>{coalitions.length}</span>
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'questions' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('questions')}
          title="Questions agents asked you"
        >
          ❓ <span className={styles.tabLabel}>For Me</span> <span className={styles.count}>{questionsToHost.length}</span>
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'messages' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('messages')}
          title="Private messages between agents"
        >
          <span className={styles.tabLabel}>Agent DMs</span> <span className={styles.count}>{agentToAgentMessages.length}</span>
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'actions' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('actions')}
          title="Strategic proposals"
        >
          <span className={styles.tabLabel}>Strategic</span> <span className={styles.count}>{strategicActions.length}</span>
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'tasks' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('tasks')}
          title="Agent autonomous actions"
        >
          <span className={styles.count}>{subTasks.length}</span>
        </button>
      </div>

      <div className={styles.content}>
        {activeTab === 'coalitions' && (
          <div className={styles.section}>
            {coalitions.length === 0 ? (
              <div className={styles.empty}>
                <span className={styles.emptyIcon} />
                <p>No coalitions formed yet</p>
                <p className={styles.emptyHint}>Agents will form alliances during the debate</p>
              </div>
            ) : (
              coalitions.map(coalition => (
                <div 
                  key={coalition.id} 
                  className={`${styles.coalitionCard} ${coalition.type === 'rivalry' ? styles.rivalryCard : ''}`}
                >
                  <div className={styles.coalitionHeader}>
                    <span className={`${styles.coalitionBadge} ${coalition.type === 'rivalry' ? styles.rivalryBadge : ''}`}>
                      {coalition.type === 'rivalry' ? '⚔️ Rivalry' : '🤝 Alliance'}
                    </span>
                    <span className={styles.coalitionTime}>
                      {new Date(coalition.formed_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className={styles.coalitionMembers}>
                    {coalition.members.map((member, idx) => (
                      <span key={idx} className={styles.memberBadge}>{member}</span>
                    ))}
                  </div>
                  {coalition.strategy && (
                    <div className={styles.coalitionStrategy}>
                      <strong>{coalition.type === 'rivalry' ? 'Opposition:' : 'Strategy:'}</strong> {coalition.strategy}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'questions' && (
          <div className={styles.section}>
            {questionsToHost.length === 0 ? (
              <div className={styles.emptyCompact}>
                <span className={styles.emptyIcon} />
                <p>No questions yet</p>
              </div>
            ) : (
              <div className={styles.hostQuestions}>
                {questionsToHost.map(msg => (
                  <div key={msg.id} className={styles.hostQuestionCard}>
                    <div className={styles.questionHeader}>
                      <span className={styles.questionFrom}>❓ {msg.from}</span>
                      <span className={styles.questionTime}>
                        {new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                      </span>
                    </div>
                    <div className={styles.questionText}>{msg.message}</div>
                    
                    {/* Reply Input */}
                    <div className={styles.replyBox}>
                      <input
                        type="text"
                        className={styles.replyInput}
                        placeholder={`Reply to ${msg.from}...`}
                        value={replyTexts.get(msg.id) || ''}
                        onChange={(e) => updateReplyText(msg.id, e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleReply(msg.id, msg.from);
                          }
                        }}
                      />
                      <button
                        className={styles.replyBtn}
                        onClick={() => handleReply(msg.id, msg.from)}
                        disabled={!replyTexts.get(msg.id)?.trim()}
                        title="Send reply (Enter)"
                      >
                        ↩
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'messages' && (
          <div className={styles.section}>
            {agentToAgentMessages.length === 0 ? (
              <div className={styles.emptyCompact}>
                <span className={styles.emptyIcon} />
                <p>No DMs yet</p>
              </div>
            ) : (
              (() => {
                // Group messages by conversation (both directions between 2 agents)
                const conversations = new Map<string, typeof agentToAgentMessages>();
                
                agentToAgentMessages.forEach(msg => {
                  const participants = [msg.from, msg.to].sort();
                  const key = participants.join('_');
                  
                  if (!conversations.has(key)) {
                    conversations.set(key, []);
                  }
                  conversations.get(key)!.push(msg);
                });
                
                return Array.from(conversations.entries()).map(([key, msgs]) => {
                  const participants = key.split('_');
                  
                  return (
                    <div key={key} className={styles.conversationThread}>
                      <div className={styles.threadHeader}>
                        <span className={styles.threadParticipants}>
                          {participants[0]} — {participants[1]}
                        </span>
                        <span className={styles.threadCount}>{msgs.length}</span>
                      </div>
                      <div className={styles.threadMessages}>
                        {msgs.map(msg => (
                          <div 
                            key={msg.id} 
                            className={`${styles.dmBubble} ${msg.from === participants[0] ? styles.dmLeft : styles.dmRight}`}
                          >
                            <div className={styles.dmSender}>{msg.from}</div>
                            <div className={styles.dmText}>{msg.message}</div>
                            <div className={styles.dmTime}>
                              {new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                });
              })()
            )}
          </div>
        )}

        {/* OLD INDIVIDUAL MESSAGE VIEW - REMOVED */}
        {false && activeTab === 'messages' && (
          <div className={styles.section}>
            {privateMessages.length === 0 ? (
              <div className={styles.empty}>
                <span className={styles.emptyIcon} />
                <p>No private messages yet</p>
                <p className={styles.emptyHint}>Agents negotiate behind the scenes</p>
              </div>
            ) : (
              privateMessages.map(msg => (
                <div key={msg.id} className={styles.messageCard}>
                  <div className={styles.messageHeader}>
                    <span className={styles.messagePath}>
                      {msg.from} → {msg.to}
                    </span>
                    <span className={styles.messageTime}>
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className={styles.messageContent}>{msg.message}</div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'actions' && (
          <div className={styles.section}>
            {strategicActions.length === 0 ? (
              <div className={styles.empty}>
                <span className={styles.emptyIcon} />
                <p>No strategic proposals yet</p>
                <p className={styles.emptyHint}>Agents can propose votes, format changes, etc.</p>
              </div>
            ) : (
              strategicActions.map(action => {
                const move = action.move;
                const icon = '';
                
                return (
                  <div key={action.id} className={styles.actionCard}>
                    <div className={styles.actionHeader}>
                      <span className={styles.actionBadge}>
                        {icon} {move.action.toUpperCase()}
                      </span>
                      <span className={styles.actionTime}>
                        {new Date(action.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className={styles.actionAgent}>by {action.agent}</div>
                    
                    {move.question && (
                      <div className={styles.actionDetail}>
                        <strong>Question:</strong> {move.question}
                      </div>
                    )}
                    
                    {move.options && (
                      <div className={styles.actionOptions}>
                        {move.options.map((opt, i) => (
                          <span key={i} className={styles.actionOption}>• {opt}</span>
                        ))}
                      </div>
                    )}
                    
                    {move.sub_topics && (
                      <div className={styles.actionDetail}>
                        <strong>Sub-topics:</strong>
                        {move.sub_topics.map((topic, i) => (
                          <div key={i}>→ {topic}</div>
                        ))}
                      </div>
                    )}
                    
                    {move.what_needed && (
                      <div className={styles.actionDetail}>
                        <strong>Evidence needed:</strong> {move.what_needed}
                      </div>
                    )}
                    
                    {move.proposal && (
                      <div className={styles.actionDetail}>
                        <strong>Proposal:</strong> {move.proposal}
                      </div>
                    )}
                    
                    {move.reason && (
                      <div className={styles.actionDetail}>
                        <strong>Reason:</strong> {move.reason}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {activeTab === 'tasks' && (
          <div className={styles.section}>
            {subTasks.length === 0 ? (
              <div className={styles.emptyCompact}>
                <span className={styles.emptyIcon} />
                <p>No tasks yet</p>
              </div>
            ) : (
              subTasks.map(task => (
                <div key={task.id} className={styles.taskCard}>
                  <div className={styles.taskHeader}>
                    <span className={styles.taskAgent}>{task.agent}</span>
                    <span className={`${styles.taskStatus} ${styles[`status-${task.status}`]}`}>
                      {task.status === 'planning' && 'Planning'}
                      {task.status === 'executing' && 'Executing'}
                      {task.status === 'completed' && 'Complete'}
                    </span>
                  </div>
                  <div className={styles.taskContent}>{task.task}</div>
                  <div className={styles.taskTime}>
                    {new Date(task.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
        </div>
        </div>
      )}
    </>
  );
}
