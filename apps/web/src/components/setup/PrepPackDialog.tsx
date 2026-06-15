/**
 * Redesigned Prep Pack Dialog - Comprehensive Agent Preparation View
 * Shows everything the agent read, researched, and understood
 */

'use client';

import { useState } from 'react';
import styles from './PrepPackDialog.module.css';

interface PrepPackDialogProps {
  isOpen: boolean;
  content: string | null;
  metadata: Record<string, any> | null;
  participantName: string;
  participantRole: string;
  meetingTitle?: string;
  meetingPurpose?: string;
  meetingAgenda?: string[];
  desiredOutcomes?: string[];
  materialsCount?: number;
  memoryChunksCount?: number;
  onClose: () => void;
}

export function PrepPackDialog({ 
  isOpen, 
  content, 
  metadata,
  participantName,
  participantRole,
  meetingTitle,
  meetingPurpose,
  meetingAgenda,
  desiredOutcomes,
  materialsCount = 0,
  memoryChunksCount = 0,
  onClose 
}: PrepPackDialogProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'research' | 'understanding'>('overview');
  
  if (!isOpen || !content) return null;

  // Extract web research from metadata (structured data)
  const webResearchPerformed = metadata?.web_research_performed || false;
  const webResearchQuery = metadata?.web_research_query || '';
  const webSearchUrls = metadata?.web_search_urls || [];
  const webSearchResults = metadata?.web_search_results || [];
  
  // Fallback: Parse from content if metadata doesn't have structured results
  const extractWebResearch = (rawContent: string) => {
    if (webSearchResults.length > 0) {
      return webSearchResults; // Use structured data from metadata
    }
    
    // Fallback to parsing from content string
    const match = rawContent.match(/\*\*Web Research Results:\*\*\n([\s\S]*?)(?=\n\*\*|$)/);
    if (match) {
      const resultsText = match[1];
      const results = [];
      const resultMatches = resultsText.matchAll(/(\d+)\.\s+(.*?)\n\s+(.*?)\n\s+Source:\s+(.*?)(?=\n\n|\n\d+\.|\n$)/gs);
      for (const m of resultMatches) {
        results.push({
          number: m[1],
          title: m[2].trim(),
          snippet: m[3].trim(),
          url: m[4].trim()
        });
      }
      return results;
    }
    return [];
  };

  const webResearchResults = extractWebResearch(content);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerContent}>
            <h2 className={styles.title}>Agent Preparation Report</h2>
            <p className={styles.subtitle}>
              <span className={styles.agentName}>{participantName}</span>
              <span className={styles.divider}>•</span>
              <span className={styles.roleName}>{participantRole}</span>
            </p>
          </div>
          <button onClick={onClose} className={styles.closeBtn} aria-label="Close">
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div className={styles.tabs}>
          <button 
            className={`${styles.tab} ${activeTab === 'overview' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            📊 Overview
          </button>
          <button 
            className={`${styles.tab} ${activeTab === 'research' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('research')}
          >
            🌐 Research ({webSearchUrls.length})
          </button>
          <button 
            className={`${styles.tab} ${activeTab === 'understanding' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('understanding')}
          >
            🧠 Understanding
          </button>
        </div>

        {/* Content */}
        <div className={styles.content}>
          
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className={styles.tabContent}>
              
              {/* Meeting Context */}
              <section className={styles.section}>
                <h3 className={styles.sectionTitle}>📋 Meeting Context</h3>
                <div className={styles.card}>
                  {meetingTitle && (
                    <div className={styles.infoRow}>
                      <span className={styles.label}>Title:</span>
                      <span className={styles.value}>{meetingTitle}</span>
                    </div>
                  )}
                  {meetingPurpose && (
                    <div className={styles.infoRow}>
                      <span className={styles.label}>Purpose:</span>
                      <span className={styles.value}>{meetingPurpose}</span>
                    </div>
                  )}
                  {meetingAgenda && meetingAgenda.length > 0 && (
                    <div className={styles.infoRow}>
                      <span className={styles.label}>Agenda:</span>
                      <ul className={styles.list}>
                        {meetingAgenda.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {desiredOutcomes && desiredOutcomes.length > 0 && (
                    <div className={styles.infoRow}>
                      <span className={styles.label}>Desired Outcomes:</span>
                      <ul className={styles.list}>
                        {desiredOutcomes.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </section>

              {/* Preparation Summary */}
              <section className={styles.section}>
                <h3 className={styles.sectionTitle}>✅ Preparation Summary</h3>
                <div className={styles.statsGrid}>
                  <div className={styles.statCard}>
                    <div className={styles.statIcon}>📄</div>
                    <div className={styles.statValue}>{materialsCount}</div>
                    <div className={styles.statLabel}>Materials Analyzed</div>
                  </div>
                  <div className={styles.statCard}>
                    <div className={styles.statIcon}>🧠</div>
                    <div className={styles.statValue}>{memoryChunksCount}</div>
                    <div className={styles.statLabel}>Memory Chunks</div>
                  </div>
                  <div className={styles.statCard}>
                    <div className={styles.statIcon}>🌐</div>
                    <div className={styles.statValue}>{webResearchResults.length}</div>
                    <div className={styles.statLabel}>Web Sources</div>
                  </div>
                  <div className={styles.statCard}>
                    <div className={styles.statIcon}>✓</div>
                    <div className={styles.statValue}>Ready</div>
                    <div className={styles.statLabel}>Status</div>
                  </div>
                </div>
              </section>

              {/* What Agent Read */}
              <section className={styles.section}>
                <h3 className={styles.sectionTitle}>📚 What the Agent Read</h3>
                <div className={styles.card}>
                  <ul className={styles.checkList}>
                    <li>
                      <span className={styles.checkIcon}>✓</span>
                      <span>Meeting title, purpose, and agenda</span>
                    </li>
                    {materialsCount > 0 && (
                      <li>
                        <span className={styles.checkIcon}>✓</span>
                        <span><strong>{materialsCount}</strong> uploaded materials (documents, files)</span>
                      </li>
                    )}
                    {memoryChunksCount > 0 && (
                      <li>
                        <span className={styles.checkIcon}>✓</span>
                        <span><strong>{memoryChunksCount}</strong> relevant chunks from knowledge base</span>
                      </li>
                    )}
                    {webResearchPerformed && (
                      <li>
                        <span className={styles.checkIcon}>✓</span>
                        <span><strong>{webResearchResults.length}</strong> web research sources on: "{webResearchQuery}"</span>
                      </li>
                    )}
                  </ul>
                </div>
              </section>

            </div>
          )}

          {/* Research Tab */}
          {activeTab === 'research' && (
            <div className={styles.tabContent}>
              <section className={styles.section}>
                <h3 className={styles.sectionTitle}>🌐 Web Research Results</h3>
                
                {webResearchPerformed ? (
                  <>
                    <div className={styles.researchQuery}>
                      <span className={styles.label}>Search Query:</span>
                      <span className={styles.queryText}>"{webResearchQuery}"</span>
                    </div>

                      {webResearchResults.length > 0 ? (
                      <div className={styles.researchResults}>
                        {webResearchResults.map((result: any, idx: number) => (
                          <div key={idx} className={styles.researchCard}>
                            <div className={styles.researchHeader}>
                              <span className={styles.researchNumber}>#{idx + 1}</span>
                              <h4 className={styles.researchTitle}>{result.title}</h4>
                            </div>
                            <p className={styles.researchSnippet}>{result.snippet}...</p>
                            <a 
                              href={result.url || result.source} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className={styles.researchLink}
                            >
                              🔗 {result.url || result.source}
                            </a>
                          </div>
                        ))}
                      </div>
                    ) : webSearchUrls.length > 0 ? (
                      <div className={styles.urlList}>
                        <p className={styles.label}>🔗 URLs Researched ({webSearchUrls.length}):</p>
                        {webSearchUrls.map((url: string, idx: number) => (
                          <a 
                            key={idx}
                            href={url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className={styles.urlItem}
                          >
                            {idx + 1}. {url}
                          </a>
                        ))}
                      </div>
                    ) : (
                      <div className={styles.emptyState}>
                        <span className={styles.emptyIcon}>🔍</span>
                        <p>No web research results found for this query.</p>
                      </div>
                    )}
                  </>
                ) : (
                  <div className={styles.emptyState}>
                    <span className={styles.emptyIcon}>🌐</span>
                    <p>Web research was not performed for this preparation.</p>
                    <p className={styles.emptyHint}>Enable web search for agents to research topics online during preflight.</p>
                  </div>
                )}
              </section>
            </div>
          )}

          {/* Understanding Tab */}
          {activeTab === 'understanding' && (
            <div className={styles.tabContent}>
              <section className={styles.section}>
                <h3 className={styles.sectionTitle}>🧠 Agent's Understanding & Prep Pack</h3>
                <div className={styles.infoBox}>
                  <strong>💡 What is this?</strong> This is the synthesized preparation memo generated by the agent 
                  after analyzing all materials, memory, and research. It represents the agent's understanding 
                  and preparation for the review session.
                </div>
                <div className={styles.prepPackContent}>
                  <pre>{content}</pre>
                </div>
              </section>
            </div>
          )}

        </div>

      </div>
    </div>
  );
}
