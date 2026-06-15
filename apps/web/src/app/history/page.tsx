'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import PracticeJourneyCard from '@/components/room/PracticeJourneyCard';
import * as api from '@/lib/api';
import type { DebateListItem } from '@/lib/api';
import styles from './history.module.css';

export default function HistoryPage() {
  const router = useRouter();
  const [debates, setDebates] = useState<DebateListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDebate, setSelectedDebate] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<any[]>([]);
  const [summary, setSummary] = useState<any | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'transcript' | 'summary'>('list');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'date-desc' | 'date-asc' | 'title-asc' | 'title-desc'>('date-desc');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'running' | 'paused' | 'ended'>('all');

  useEffect(() => {
    loadDebates();
  }, []);

  const loadDebates = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Use proper API endpoint
      const response = await api.listDebates('00000000-0000-0000-0000-000000000101', 50);
      setDebates(response.items || []);
    } catch (err) {
      console.error('Failed to load debates:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to load debates';
      
      // Provide helpful error message if backend is not running
      if (errorMessage.includes('Failed to fetch') || errorMessage.includes('fetch')) {
        setError('Unable to connect to backend server. Please ensure the API server is running on http://localhost:8000');
      } else {
        setError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  const viewDebateTranscript = async (debateId: string) => {
    setSelectedDebate(debateId);
    setViewMode('transcript');
    
    try {
      // Fetch all events for this debate
      const events = await api.getDebateEvents(debateId);
      setTranscript(events);
    } catch (err) {
      console.error('Failed to load transcript:', err);
      setError('Failed to load transcript');
    }
  };

  const viewDebateSummary = async (debateId: string) => {
    setSelectedDebate(debateId);
    setViewMode('summary');
    
    try {
      const data = await api.getDebateSummary(debateId);
      setSummary(data);
    } catch (err) {
      console.error('Failed to load summary:', err);
      setSummary(null);
    }
  };

  const openInRoom = (debateId: string) => {
    router.push(`/room?debate_id=${debateId}`);
  };

  const handleDelete = async (debateId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    
    if (!confirm('Are you sure you want to delete this review session? This action cannot be undone.')) {
      return;
    }
    
    setDeleting(debateId);
    try {
      await api.deleteDebate(debateId);
      // Remove from local state
      setDebates(prev => prev.filter(d => d.debate_id !== debateId));
    } catch (err) {
      console.error('Failed to delete debate:', err);
      setError('Failed to delete debate');
    } finally {
      setDeleting(null);
    }
  };

  // Filter and sort debates
  const filteredAndSortedDebates = debates
    .filter(debate => {
      // Status filter
      if (statusFilter !== 'all' && debate.state !== statusFilter) {
        return false;
      }
      
      // Search filter
      if (!searchQuery) return true;
      const query = searchQuery.toLowerCase();
      return (
        debate.title?.toLowerCase().includes(query) ||
        debate.debate_id.toLowerCase().includes(query)
      );
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'date-desc':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'date-asc':
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        case 'title-asc':
          return (a.title || '').localeCompare(b.title || '');
        case 'title-desc':
          return (b.title || '').localeCompare(a.title || '');
        default:
          return 0;
      }
    });
  
  // Count debates by status
  const statusCounts = {
    all: debates.length,
    pending: debates.filter(d => d.state === 'pending').length,
    running: debates.filter(d => d.state === 'running').length,
    paused: debates.filter(d => d.state === 'paused').length,
    ended: debates.filter(d => d.state === 'ended').length,
  };

  const getStateBadge = (state: string) => {
    const stateStyles: Record<string, string> = {
      pending: styles.statePending,
      running: styles.stateRunning,
      paused: styles.statePaused,
      ended: styles.stateEnded,
    };
    
    return (
      <span className={`${styles.stateBadge} ${stateStyles[state] || ''}`}>
        {state}
      </span>
    );
  };

  return (
    <>
      <AppNav />
      <div className={styles.historyPage}>
        <div className={styles.container}>
          <header className={styles.header}>
            <div>
              <h1>Session History</h1>
              <p className={styles.subtitle}>View past review sessions, transcripts, and feedback reports</p>
            </div>
            {viewMode !== 'list' && (
              <button onClick={() => { setViewMode('list'); setSelectedDebate(null); }} className={styles.btnBack}>
                ← Back to List
              </button>
            )}
          </header>

          {error && (
            <div className={styles.error}>
              <span style={{ fontWeight: 600, color: 'var(--warning)' }}>!</span>
              <div>
                <div>{error}</div>
                {error.includes('backend server') && (
                  <div style={{ marginTop: '8px', fontSize: '12px' }}>
                    Start the backend: <code style={{ background: 'var(--surface-0)', padding: '2px 6px', borderRadius: '4px' }}>cd apps/api && python -m uvicorn src.main:app --reload</code>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* List View */}
          {viewMode === 'list' && (
            <div className={styles.debatesList}>
              {/* Status Filter Tabs */}
              {!loading && debates.length > 0 && (
                <div className={styles.statusTabs}>
                  <button
                    onClick={() => setStatusFilter('all')}
                    className={`${styles.statusTab} ${statusFilter === 'all' ? styles.statusTabActive : ''}`}
                  >
                    All <span className={styles.tabCount}>{statusCounts.all}</span>
                  </button>
                  <button
                    onClick={() => setStatusFilter('pending')}
                    className={`${styles.statusTab} ${statusFilter === 'pending' ? styles.statusTabActive : ''}`}
                  >
                    <span className={styles.tabDot} data-status="pending"></span>
                    Pending <span className={styles.tabCount}>{statusCounts.pending}</span>
                  </button>
                  <button
                    onClick={() => setStatusFilter('running')}
                    className={`${styles.statusTab} ${statusFilter === 'running' ? styles.statusTabActive : ''}`}
                  >
                    <span className={styles.tabDot} data-status="running"></span>
                    Running <span className={styles.tabCount}>{statusCounts.running}</span>
                  </button>
                  <button
                    onClick={() => setStatusFilter('paused')}
                    className={`${styles.statusTab} ${statusFilter === 'paused' ? styles.statusTabActive : ''}`}
                  >
                    <span className={styles.tabDot} data-status="paused"></span>
                    Paused <span className={styles.tabCount}>{statusCounts.paused}</span>
                  </button>
                  <button
                    onClick={() => setStatusFilter('ended')}
                    className={`${styles.statusTab} ${statusFilter === 'ended' ? styles.statusTabActive : ''}`}
                  >
                    <span className={styles.tabDot} data-status="ended"></span>
                    Ended <span className={styles.tabCount}>{statusCounts.ended}</span>
                  </button>
                </div>
              )}

              {/* Search and Sort Controls */}
              {!loading && debates.length > 0 && (
                <div className={styles.controls}>
                  <div className={styles.searchBox}>
                    <span className={styles.searchIcon}>&#x2315;</span>
                    <input
                      type="text"
                      placeholder="Search sessions by title or ID..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className={styles.searchInput}
                    />
                    {searchQuery && (
                      <button 
                        onClick={() => setSearchQuery('')}
                        className={styles.clearBtn}
                        title="Clear search"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                  
                  <div className={styles.sortBox}>
                    <label htmlFor="sort-select">Sort by:</label>
                    <select
                      id="sort-select"
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value as any)}
                      className={styles.sortSelect}
                    >
                      <option value="date-desc">Newest First</option>
                      <option value="date-asc">Oldest First</option>
                      <option value="title-asc">Title A–Z</option>
                      <option value="title-desc">Title Z–A</option>
                    </select>
                  </div>
                </div>
              )}

              {loading ? (
                <div className={styles.loading}>
                  <div className={styles.spinner}></div>
                  <p>Loading sessions...</p>
                </div>
              ) : filteredAndSortedDebates.length === 0 && (searchQuery || statusFilter !== 'all') ? (
                <div className={styles.emptyState}>
                  <span className={styles.emptyIcon} aria-hidden="true" />
                  <h3>No results found</h3>
                  <p>
                    {searchQuery 
                      ? `No debates match your search for "${searchQuery}"` 
                      : `No ${statusFilter} debates found`}
                  </p>
                  <button 
                    onClick={() => {
                      setSearchQuery('');
                      setStatusFilter('all');
                    }} 
                    className={styles.btnSecondary}
                  >
                    Clear Filters
                  </button>
                </div>
              ) : debates.length === 0 ? (
                <div className={styles.emptyState}>
                  <span className={styles.emptyIcon} aria-hidden="true" />
                  <h3>No review sessions yet</h3>
                  <p>Start your first review session to begin practicing</p>
                  <button onClick={() => router.push('/setup')} className={styles.btnPrimary}>
                    New Review Session
                  </button>
                </div>
              ) : (
                <>
                  {filteredAndSortedDebates.length > 0 && (searchQuery || statusFilter !== 'all') && (
                    <div className={styles.resultsCount}>
                      Showing {filteredAndSortedDebates.length} of {debates.length} review sessions
                      {searchQuery && ` matching "${searchQuery}"`}
                    </div>
                  )}
                  <div className={styles.grid}>
                  {filteredAndSortedDebates.map((debate) => (
                    <div key={debate.debate_id} className={styles.debateCard}>
                      <div className={styles.cardHeader}>
                        <h3 className={styles.debateTitle}>{debate.title || 'Untitled Review Session'}</h3>
                        {getStateBadge(debate.state)}
                      </div>
                      
                      <div className={styles.cardMeta}>
                        <span className={styles.metaItem}>
                          {new Date(debate.created_at).toLocaleDateString()}
                        </span>
                        {debate.participant_count && (
                          <span className={styles.metaItem}>
                            {debate.participant_count} participants
                          </span>
                        )}
                        {debate.message_count && (
                          <span className={styles.metaItem}>
                            {debate.message_count} messages
                          </span>
                        )}
                      </div>

                      <div className={styles.cardActions}>
                        <button 
                          onClick={() => viewDebateTranscript(debate.debate_id)}
                          className={styles.btnSecondary}
                          title="View transcript"
                        >
                          Transcript
                        </button>
                        {debate.state === 'ended' && (
                          <button 
                            onClick={() => viewDebateSummary(debate.debate_id)}
                            className={styles.btnSecondary}
                            title="View summary"
                          >
                            Summary
                          </button>
                        )}
                        <button 
                          onClick={() => router.push(`/room?debate_id=${debate.debate_id}&tab=defense`)}
                          className={styles.btnDefense}
                          title="Open Practice Q&A room"
                        >
                          Practice Q&A
                        </button>
                        <button 
                          onClick={() => router.push(`/room?debate_id=${debate.debate_id}&tab=voice`)}
                          className={styles.btnVoice}
                          title="Open Voice Practice room"
                        >
                          🎤 Voice
                        </button>
                        <button 
                          onClick={(e) => handleDelete(debate.debate_id, e)}
                          className={styles.btnDelete}
                          disabled={deleting === debate.debate_id}
                          title="Delete debate"
                        >
                          {deleting === debate.debate_id ? '⏳' : '🗑️'}
                        </button>
                      </div>

                      <div className={styles.cardId}>
                        ID: {debate.debate_id}
                      </div>
                    </div>
                  ))}
                </div>
                </>
              )}
            </div>
          )}

          {/* Transcript View */}
          {viewMode === 'transcript' && selectedDebate && (
            <div className={styles.transcriptView}>
              <div className={styles.viewHeader}>
                <h2>Full Transcript</h2>
                <div className={styles.viewActions}>
                  <button onClick={() => openInRoom(selectedDebate)} className={styles.btnPrimary}>
                    Open in Room
                  </button>
                </div>
              </div>

              <div className={styles.transcript}>
                {transcript.length === 0 ? (
                  <div className={styles.emptyState}>
                    <p>No messages in this session yet</p>
                  </div>
                ) : (
                  transcript.map((event, idx) => {
                    const content = event.content || event.payload || {};
                    const agentName = content.agent_name || content.actor || 'System';
                    const text = content.text || content.message || '';
                    
                    return (
                      <div key={event.event_id || idx} className={styles.message}>
                        <div className={styles.messageHeader}>
                          <span className={styles.messageSender}>{agentName}</span>
                          <span className={styles.messageSeq}>#{event.sequence_number}</span>
                        </div>
                        <div className={styles.messageContent}>
                          {text}
                        </div>
                        {event.event_type === 'human_message' && (
                          <div className={styles.humanBadge}>🎙️ Human Intervention</div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* Summary View */}
          {viewMode === 'summary' && selectedDebate && (
            <div className={styles.summaryView}>
              <div className={styles.viewHeader}>
                <h2>Feedback Report</h2>
                <div className={styles.viewActions}>
                  <button onClick={() => viewDebateTranscript(selectedDebate)} className={styles.btnSecondary}>
                    View Transcript
                  </button>
                  <button onClick={() => openInRoom(selectedDebate)} className={styles.btnPrimary}>
                    Open in Room
                  </button>
                </div>
              </div>

              {/* Preparation funnel — keep practicing after reading the report */}
              <PracticeJourneyCard
                debateId={selectedDebate}
                onStartPractice={() => router.push(`/room?debate_id=${selectedDebate}&tab=defense`)}
              />

              {summary ? (
                <div className={styles.summaryContent}>
                      <section className={styles.summarySection}>
                    <h3>Summary of Contribution</h3>
                    <p className={styles.summaryText}>{summary.summary}</p>
                  </section>

                  <section className={styles.summarySection}>
                    <h3>Detailed Review Notes</h3>
                    <div className={styles.minutesText}>{summary.minutes}</div>
                  </section>

                  {summary.action_items && summary.action_items.length > 0 && (() => {
                    const recommendation = summary.action_items.find((i: any) => i._type === 'recommendation');
                    const actionItems = summary.action_items.filter((i: any) => i._type !== 'recommendation');
                    return (
                      <>
                        {recommendation && (
                          <section className={styles.summarySection}>
                            <h3>Final Recommendation</h3>
                            <div style={{
                              background: '#f0fdf4',
                              border: '2px solid #22c55e',
                              borderRadius: '8px',
                              padding: '16px',
                              fontSize: '15px',
                              fontWeight: 600,
                            }}>
                              {recommendation.description}
                            </div>
                          </section>
                        )}
                        {actionItems.length > 0 && (
                          <section className={styles.summarySection}>
                            <h3>Required Changes &amp; Next Steps</h3>
                            <div className={styles.actionItems}>
                              {actionItems.map((item: any, idx: number) => (
                                <div key={idx} className={styles.actionItem}>
                                  <div className={styles.actionHeader}>
                                    <span className={styles.actionPriority} data-priority={item.priority}>
                                      {item.priority === 'high' ? '🔴' : item.priority === 'medium' ? '🟡' : '🟢'}
                                    </span>
                                    <span className={styles.actionOwner}>{item.owner}</span>
                                  </div>
                                  <p className={styles.actionDescription}>{item.description}</p>
                                </div>
                              ))}
                            </div>
                          </section>
                        )}
                      </>
                    );
                  })()}

                  {summary.generated_at && (
                    <div className={styles.summaryMeta}>
                      Generated on {new Date(summary.generated_at).toLocaleString()}
                      {summary.model_used && ` using ${summary.model_used}`}
                    </div>
                  )}
                </div>
              ) : (
                <div className={styles.emptyState}>
                  <span className={styles.emptyIcon} aria-hidden="true" />
                  <h3>No Report Generated</h3>
                  <p>This session hasn't produced a report yet</p>
                  <button onClick={() => openInRoom(selectedDebate)} className={styles.btnPrimary}>
                    Open in Room to Generate
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
