'use client';

/**
 * LiteratureStep — Stage 5: Literature & Web Search
 *
 * Two tabs:
 *   📚 Academic Papers  — arXiv, Semantic Scholar, PubMed, Crossref, OpenAlex
 *   🌐 Web Search       — Tavily AI-curated web results
 *
 * Selected items from either tab can be saved into the review session's RAG
 * context so AI reviewers can cite them during the debate.
 */

import { useState, useEffect } from 'react';
import * as api from '@/lib/api';
import type { PaperResult, SavedPaper, WebResult, SavedWebResult } from '@/lib/api';
import styles from './SetupSteps.module.css';
import literatureStyles from './LiteratureStep.module.css';

// ---------------------------------------------------------------------------
// Academic sources config
// ---------------------------------------------------------------------------

const SOURCE_LABELS: Record<string, string> = {
  arxiv: 'arXiv',
  semantic_scholar: 'Semantic Scholar',
  pubmed: 'PubMed',
  crossref: 'Crossref',
  openalex: 'OpenAlex',
};
const ALL_SOURCES = Object.keys(SOURCE_LABELS);

const sourceIcon: Record<string, string> = {
  arxiv: '📄',
  semantic_scholar: '🎓',
  pubmed: '🔬',
  crossref: '🔗',
  openalex: '🌐',
};

// ---------------------------------------------------------------------------
// Query condenser (mirrors backend _condense_query)
// ---------------------------------------------------------------------------

function condenseQuery(text: string, maxChars = 300): string {
  if (!text) return '';
  const firstLine = text.split('\n').map(l => l.trim()).find(l => l.length > 0) ?? text;
  const stripped = firstLine.replace(/^(main\s+)?research\s+question[:\s]*/i, '').trim();
  const condensed = stripped
    .replace(/\b(how can|how do|what is|what are|can we|whether|using|based on|in order to)\b/gi, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
  return condensed.slice(0, maxChars);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface LiteratureStepProps {
  debateId: string | null;
  researchQuestion: string;
  onCanContinueChange?: (canContinue: boolean) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LiteratureStep({
  debateId,
  researchQuestion,
  onCanContinueChange,
}: LiteratureStepProps) {
  const [activeTab, setActiveTab] = useState<'academic' | 'web'>('academic');

  // ── Academic state ────────────────────────────────────────────────────────
  const [query, setQuery] = useState(() => condenseQuery(researchQuestion || ''));
  const [selectedSources, setSelectedSources] = useState<string[]>(ALL_SOURCES);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<PaperResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedPapers, setSelectedPapers] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedPapers, setSavedPapers] = useState<SavedPaper[]>([]);
  const [loadingSaved, setLoadingSaved] = useState(false);
  const [expandedAbstracts, setExpandedAbstracts] = useState<Set<string>>(new Set());
  const [hasSearched, setHasSearched] = useState(false);

  // ── Web search state ──────────────────────────────────────────────────────
  const [webQuery, setWebQuery] = useState(() => condenseQuery(researchQuestion || ''));
  const [webSearchDepth, setWebSearchDepth] = useState<'basic' | 'advanced'>('advanced');
  const [webSearching, setWebSearching] = useState(false);
  const [webResults, setWebResults] = useState<WebResult[]>([]);
  const [webError, setWebError] = useState<string | null>(null);
  const [selectedWebResults, setSelectedWebResults] = useState<Set<string>>(new Set());
  const [webSaving, setWebSaving] = useState(false);
  const [webSaveError, setWebSaveError] = useState<string | null>(null);
  const [savedWebResults, setSavedWebResults] = useState<SavedWebResult[]>([]);
  const [hasWebSearched, setHasWebSearched] = useState(false);

  // ── Effects ───────────────────────────────────────────────────────────────

  useEffect(() => {
    onCanContinueChange?.(true); // optional step
  }, [onCanContinueChange]);

  useEffect(() => {
    if (!debateId) return;
    loadSavedPapers();
    loadSavedWebResults();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debateId]);

  // ── Academic handlers ─────────────────────────────────────────────────────

  const loadSavedPapers = async () => {
    if (!debateId) return;
    setLoadingSaved(true);
    try {
      const data = await api.listSavedPapers(debateId);
      setSavedPapers(data.papers);
    } catch (err) {
      console.warn('Could not load saved papers:', err);
    } finally {
      setLoadingSaved(false);
    }
  };

  const handleSearch = async () => {
    if (!debateId) {
      setSearchError('Review session not yet created. Please complete earlier steps first.');
      return;
    }
    if (!query.trim()) return;

    setSearching(true);
    setSearchError(null);
    setSearchResults([]);
    setSelectedPapers(new Set());
    setHasSearched(true);

    try {
      const result = await api.searchLiterature(debateId, query.trim(), selectedSources);
      setSearchResults(result.papers);
      if (result.papers.length === 0) {
        setSearchError('No results found. Try a broader query or different sources.');
      }
    } catch (err: any) {
      setSearchError(err.message || 'Search failed. Check your connection and try again.');
    } finally {
      setSearching(false);
    }
  };

  const toggleSource = (source: string) => {
    setSelectedSources(prev =>
      prev.includes(source) ? prev.filter(s => s !== source) : [...prev, source],
    );
  };

  const getPaperKey = (p: PaperResult) =>
    p.doi ? `doi:${p.doi}` : `title:${p.title.toLowerCase().slice(0, 40)}`;

  const togglePaper = (key: string) => {
    setSelectedPapers(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const toggleAbstract = (key: string) => {
    setExpandedAbstracts(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const handleSaveSelected = async () => {
    if (!debateId || selectedPapers.size === 0) return;
    const toSave = searchResults.filter(p => selectedPapers.has(getPaperKey(p)));
    setSaving(true);
    setSaveError(null);
    try {
      await api.savePapersToContext(debateId, toSave, `search: ${query.slice(0, 60)}`);
      await loadSavedPapers();
      setSelectedPapers(new Set());
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save papers. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  // ── Web search handlers ───────────────────────────────────────────────────

  const loadSavedWebResults = async () => {
    if (!debateId) return;
    try {
      const data = await api.listSavedWebResults(debateId);
      setSavedWebResults(data.results);
    } catch (err) {
      console.warn('Could not load saved web results:', err);
    }
  };

  const handleWebSearch = async () => {
    if (!debateId) {
      setWebError('Review session not yet created. Please complete earlier steps first.');
      return;
    }
    if (!webQuery.trim()) return;

    setWebSearching(true);
    setWebError(null);
    setWebResults([]);
    setSelectedWebResults(new Set());
    setHasWebSearched(true);

    try {
      const result = await api.searchWeb(debateId, webQuery.trim(), {
        searchDepth: webSearchDepth,
        maxResults: 10,
      });
      setWebResults(result.results);
      if (result.results.length === 0) {
        setWebError('No results found. Try a different query.');
      }
    } catch (err: any) {
      const msg: string = err.message || '';
      if (msg.includes('not configured') || msg.includes('503')) {
        setWebError(
          'Web search requires a Tavily API key. Add TAVILY_API_KEY to apps/api/.env — get a free key at tavily.com',
        );
      } else {
        setWebError(msg || 'Web search failed. Check your connection and try again.');
      }
    } finally {
      setWebSearching(false);
    }
  };

  const getWebKey = (r: WebResult) => r.url;

  const toggleWebResult = (key: string) => {
    setSelectedWebResults(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const handleSaveWebSelected = async () => {
    if (!debateId || selectedWebResults.size === 0) return;
    const toSave = webResults.filter(r => selectedWebResults.has(getWebKey(r)));
    setWebSaving(true);
    setWebSaveError(null);
    try {
      await api.saveWebResults(debateId, toSave, `web: ${webQuery.slice(0, 60)}`);
      await loadSavedWebResults();
      setSelectedWebResults(new Set());
    } catch (err: any) {
      setWebSaveError(err.message || 'Failed to save results. Please try again.');
    } finally {
      setWebSaving(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  const totalSaved = savedPapers.length + savedWebResults.length;

  return (
    <div className={styles.section}>
      <h2>Literature &amp; Web Search</h2>
      <p className={styles.hint}>
        Search academic databases and the web to find relevant papers and resources.
        Add them to the review context so AI reviewers can cite them.
        <strong> This step is optional — you can continue without adding any sources.</strong>
      </p>

      {/* Tab switcher */}
      <div className={literatureStyles.tabRow}>
        <button
          type="button"
          className={`${literatureStyles.tab} ${activeTab === 'academic' ? literatureStyles.tabActive : ''}`}
          onClick={() => setActiveTab('academic')}
        >
          📚 Academic Papers
        </button>
        <button
          type="button"
          className={`${literatureStyles.tab} ${activeTab === 'web' ? literatureStyles.tabActive : ''}`}
          onClick={() => setActiveTab('web')}
        >
          🌐 Web Search
          <span className={literatureStyles.tabBadge}>Tavily</span>
        </button>
      </div>

      {/* ── ACADEMIC TAB ─────────────────────────────────────────────────── */}
      {activeTab === 'academic' && (
        <>
          {/* Source toggles */}
          <div className={literatureStyles.sourcesRow}>
            <span className={literatureStyles.sourcesLabel}>Sources:</span>
            {ALL_SOURCES.map(src => (
              <button
                key={src}
                type="button"
                className={`${literatureStyles.sourceChip} ${selectedSources.includes(src) ? literatureStyles.sourceChipActive : ''}`}
                onClick={() => toggleSource(src)}
              >
                {sourceIcon[src]} {SOURCE_LABELS[src]}
              </button>
            ))}
          </div>

          {/* Search bar */}
          <div className={literatureStyles.searchRow}>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <input
                type="text"
                className={literatureStyles.searchInput}
                value={query}
                onChange={e => setQuery(e.target.value.slice(0, 500))}
                placeholder="e.g. federated learning personalization privacy"
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSearch(); } }}
                disabled={searching}
              />
              <span className={`${literatureStyles.charCount} ${query.length > 450 ? literatureStyles.charCountWarn : ''}`}>
                {query.length}/500 characters
              </span>
            </div>
            <button
              type="button"
              className={literatureStyles.searchBtn}
              onClick={handleSearch}
              disabled={searching || !query.trim() || selectedSources.length === 0 || !debateId}
            >
              {searching ? 'Searching…' : 'Search'}
            </button>
          </div>

          {!debateId && (
            <p className={literatureStyles.infoNote}>Complete earlier steps to enable search.</p>
          )}

          {searchError && <div className={styles.error}>{searchError}</div>}

          {searchResults.length > 0 && (
            <div className={literatureStyles.resultsSection}>
              <div className={literatureStyles.resultsHeader}>
                <span className={literatureStyles.resultsCount}>
                  {searchResults.length} papers found
                </span>
                {selectedPapers.size > 0 && (
                  <button type="button" className={literatureStyles.saveBtn} onClick={handleSaveSelected} disabled={saving}>
                    {saving ? 'Saving…' : `Add ${selectedPapers.size} paper${selectedPapers.size > 1 ? 's' : ''} to context`}
                  </button>
                )}
              </div>
              {saveError && <div className={styles.error}>{saveError}</div>}

              <div className={literatureStyles.paperList}>
                {searchResults.map((paper, index) => {
                  const key = getPaperKey(paper);
                  const isSelected = selectedPapers.has(key);
                  const abstractExpanded = expandedAbstracts.has(key);
                  const checkboxId = `literature-paper-${index}`;
                  return (
                    <div key={key} className={`${literatureStyles.paperCard} ${isSelected ? literatureStyles.paperCardSelected : ''}`}>
                      <div className={literatureStyles.paperCardLayout}>
                        <input
                          id={checkboxId}
                          type="checkbox"
                          className={literatureStyles.paperCheckboxInput}
                          checked={isSelected}
                          onChange={() => togglePaper(key)}
                        />
                        <label htmlFor={checkboxId} className={literatureStyles.paperTitle}>
                          {paper.title}
                        </label>
                        <span className={literatureStyles.sourceBadge}>
                          {sourceIcon[paper.source]} {SOURCE_LABELS[paper.source] || paper.source}
                        </span>
                        <div className={literatureStyles.paperCardDetails}>
                          <div className={literatureStyles.paperMeta}>
                            {paper.authors.slice(0, 3).join(', ')}
                            {paper.authors.length > 3 && ' et al.'}
                            {paper.year && <span className={literatureStyles.year}> · {paper.year}</span>}
                            {paper.venue && <span className={literatureStyles.venue}> · {paper.venue}</span>}
                            {paper.citation_count > 0 && (
                              <span className={literatureStyles.citations}> · {paper.citation_count} citations</span>
                            )}
                          </div>
                          {paper.abstract && (
                            <div className={literatureStyles.abstractSection}>
                              <p className={`${literatureStyles.abstract} ${abstractExpanded ? literatureStyles.abstractExpanded : ''}`}>
                                {paper.abstract}
                              </p>
                              {paper.abstract.length > 200 && (
                                <button type="button" className={literatureStyles.toggleAbstractBtn} onClick={() => toggleAbstract(key)}>
                                  {abstractExpanded ? 'Show less' : 'Show more'}
                                </button>
                              )}
                            </div>
                          )}
                          {paper.url && (
                            <a href={paper.url} target="_blank" rel="noopener noreferrer" className={literatureStyles.paperLink}>
                              View paper →
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {selectedPapers.size > 0 && (
                <div className={literatureStyles.saveFooter}>
                  <button type="button" className={literatureStyles.saveBtn} onClick={handleSaveSelected} disabled={saving}>
                    {saving ? 'Saving…' : `Add ${selectedPapers.size} selected paper${selectedPapers.size > 1 ? 's' : ''} to review context`}
                  </button>
                </div>
              )}
            </div>
          )}

          {hasSearched && searchResults.length === 0 && !searching && !searchError && (
            <p className={literatureStyles.noResults}>No results returned. Try a different query.</p>
          )}
        </>
      )}

      {/* ── WEB SEARCH TAB ───────────────────────────────────────────────── */}
      {activeTab === 'web' && (
        <>
          <div className={literatureStyles.webInfoBanner}>
            <span>🔍</span>
            <span>
              Powered by <strong>Tavily</strong> — AI-curated web search optimised for research.
              Requires <code>TAVILY_API_KEY</code> in your API environment.
              Get a free key at{' '}
              <a href="https://tavily.com" target="_blank" rel="noopener noreferrer">tavily.com</a>.
            </span>
          </div>

          {/* Depth toggle */}
          <div className={literatureStyles.depthRow}>
            <span className={literatureStyles.sourcesLabel}>Search depth:</span>
            <button
              type="button"
              className={`${literatureStyles.sourceChip} ${webSearchDepth === 'basic' ? literatureStyles.sourceChipActive : ''}`}
              onClick={() => setWebSearchDepth('basic')}
            >
              ⚡ Basic (fast)
            </button>
            <button
              type="button"
              className={`${literatureStyles.sourceChip} ${webSearchDepth === 'advanced' ? literatureStyles.sourceChipActive : ''}`}
              onClick={() => setWebSearchDepth('advanced')}
            >
              🔬 Advanced (deeper)
            </button>
          </div>

          {/* Web search bar */}
          <div className={literatureStyles.searchRow}>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <input
                type="text"
                className={literatureStyles.searchInput}
                value={webQuery}
                onChange={e => setWebQuery(e.target.value.slice(0, 500))}
                placeholder="e.g. federated learning writing style personalization"
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleWebSearch(); } }}
                disabled={webSearching}
              />
              <span className={`${literatureStyles.charCount} ${webQuery.length > 450 ? literatureStyles.charCountWarn : ''}`}>
                {webQuery.length}/500 characters
              </span>
            </div>
            <button
              type="button"
              className={literatureStyles.searchBtn}
              onClick={handleWebSearch}
              disabled={webSearching || !webQuery.trim() || !debateId}
            >
              {webSearching ? 'Searching…' : 'Search'}
            </button>
          </div>

          {!debateId && (
            <p className={literatureStyles.infoNote}>Complete earlier steps to enable search.</p>
          )}

          {webError && <div className={styles.error}>{webError}</div>}

          {webResults.length > 0 && (
            <div className={literatureStyles.resultsSection}>
              <div className={literatureStyles.resultsHeader}>
                <span className={literatureStyles.resultsCount}>
                  {webResults.length} results found
                </span>
                {selectedWebResults.size > 0 && (
                  <button type="button" className={literatureStyles.saveBtn} onClick={handleSaveWebSelected} disabled={webSaving}>
                    {webSaving ? 'Saving…' : `Add ${selectedWebResults.size} result${selectedWebResults.size > 1 ? 's' : ''} to context`}
                  </button>
                )}
              </div>
              {webSaveError && <div className={styles.error}>{webSaveError}</div>}

              <div className={literatureStyles.paperList}>
                {webResults.map((result, index) => {
                  const key = getWebKey(result);
                  const isSelected = selectedWebResults.has(key);
                  const checkboxId = `literature-web-${index}`;
                  return (
                    <div key={key} className={`${literatureStyles.paperCard} ${isSelected ? literatureStyles.paperCardSelected : ''}`}>
                      <div className={literatureStyles.paperCardLayout}>
                        <input
                          id={checkboxId}
                          type="checkbox"
                          className={literatureStyles.paperCheckboxInput}
                          checked={isSelected}
                          onChange={() => toggleWebResult(key)}
                        />
                        <label htmlFor={checkboxId} className={literatureStyles.paperTitle}>
                          {result.title}
                        </label>
                        <span className={literatureStyles.sourceBadge}>
                          🌐 {result.source_domain || 'web'}
                        </span>
                        <div className={literatureStyles.paperCardDetails}>
                          <div className={literatureStyles.paperMeta}>
                            <a href={result.url} target="_blank" rel="noopener noreferrer" className={literatureStyles.paperLink}>
                              {result.url.length > 70 ? result.url.slice(0, 70) + '…' : result.url}
                            </a>
                            {result.published_date && (
                              <span className={literatureStyles.year}> · {result.published_date}</span>
                            )}
                            {result.score > 0 && (
                              <span className={literatureStyles.citations}> · relevance {Math.round(result.score * 100)}%</span>
                            )}
                          </div>
                          {result.content && (
                            <div className={literatureStyles.abstractSection}>
                              <p className={literatureStyles.abstract}>{result.content}</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {selectedWebResults.size > 0 && (
                <div className={literatureStyles.saveFooter}>
                  <button type="button" className={literatureStyles.saveBtn} onClick={handleSaveWebSelected} disabled={webSaving}>
                    {webSaving ? 'Saving…' : `Add ${selectedWebResults.size} selected result${selectedWebResults.size > 1 ? 's' : ''} to review context`}
                  </button>
                </div>
              )}
            </div>
          )}

          {hasWebSearched && webResults.length === 0 && !webSearching && !webError && (
            <p className={literatureStyles.noResults}>No results returned. Try a different query.</p>
          )}
        </>
      )}

      {/* ── Saved sources summary (shared across both tabs) ──────────────── */}
      {totalSaved > 0 && (
        <div className={literatureStyles.savedSection}>
          <h3 className={literatureStyles.savedTitle}>
            Sources added to review context ({totalSaved})
          </h3>

          {savedPapers.length > 0 && (
            <>
              <p className={literatureStyles.savedGroupLabel}>📚 Academic Papers ({savedPapers.length})</p>
              <ul className={literatureStyles.savedList}>
                {savedPapers.map(p => (
                  <li key={p.material_id} className={literatureStyles.savedItem}>
                    <span className={literatureStyles.savedItemTitle}>{p.title}</span>
                    <span className={literatureStyles.savedItemMeta}>
                      {SOURCE_LABELS[p.source] || p.source}
                      {p.year && ` · ${p.year}`}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {savedWebResults.length > 0 && (
            <>
              <p className={literatureStyles.savedGroupLabel}>🌐 Web Results ({savedWebResults.length})</p>
              <ul className={literatureStyles.savedList}>
                {savedWebResults.map(r => (
                  <li key={r.material_id} className={literatureStyles.savedItem}>
                    <span className={literatureStyles.savedItemTitle}>{r.title}</span>
                    <span className={literatureStyles.savedItemMeta}>
                      {r.source_domain || 'web'}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {loadingSaved && (
        <p className={literatureStyles.infoNote}>Loading saved sources…</p>
      )}
    </div>
  );
}
