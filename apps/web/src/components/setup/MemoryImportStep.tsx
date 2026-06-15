import { useState, useEffect } from 'react';
import * as api from '@/lib/api';
import styles from './SetupSteps.module.css';

export interface MemoryImportConfig {
  enabled: boolean;
  source_debate_ids: string[];
  source_type: 'debate_full' | 'materials_only';
  scope: 'all_agents' | 'specific_agents';
  selected_participant_indices: number[];  // UI indices, will be mapped to participant_ids after setup
}

interface MemoryImportStepProps {
  workspaceId: string;
  participants: api.SetupParticipant[];
  memoryImport: MemoryImportConfig;
  onUpdate: (config: MemoryImportConfig) => void;
}

export function MemoryImportStep({
  workspaceId,
  participants,
  memoryImport,
  onUpdate,
}: MemoryImportStepProps) {
  const [importableSources, setImportableSources] = useState<api.ImportableDebate[]>([]);
  const [isLoadingSources, setIsLoadingSources] = useState(false);
  const [previewData, setPreviewData] = useState<Record<string, api.MemoryPreviewResponse>>({});
  const [isLoadingPreview, setIsLoadingPreview] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  // Load importable sources when toggle is enabled
  useEffect(() => {
    if (memoryImport.enabled && importableSources.length === 0) {
      loadImportableSources();
    }
  }, [memoryImport.enabled]);

  const loadImportableSources = async () => {
    setIsLoadingSources(true);
    setError(null);
    try {
      const response = await api.listImportableMemorySources(workspaceId, 20);
      setImportableSources(response.debates);
      if (response.debates.length === 0) {
        setError('No past review sessions available to import. Complete a review session first.');
      }
    } catch (err: any) {
      console.error('Failed to load importable sources:', err);
      setError(`Failed to load past review sessions: ${err.message}`);
    } finally {
      setIsLoadingSources(false);
    }
  };

  const handleToggle = (enabled: boolean) => {
    onUpdate({ ...memoryImport, enabled });
    if (enabled && importableSources.length === 0) {
      loadImportableSources();
    }
  };

  const handleSourceToggle = (debateId: string) => {
    const newIds = memoryImport.source_debate_ids.includes(debateId)
      ? memoryImport.source_debate_ids.filter(id => id !== debateId)
      : [...memoryImport.source_debate_ids, debateId];
    
    onUpdate({ ...memoryImport, source_debate_ids: newIds });

    // Load preview for this source (we'll use a fake debate_id for preview purposes)
    if (newIds.includes(debateId) && !previewData[debateId]) {
      loadPreview(debateId);
    }
  };

  const loadPreview = async (sourceDebateId: string) => {
    setIsLoadingPreview({ ...isLoadingPreview, [sourceDebateId]: true });
    try {
      // Note: preview requires a target debate_id, but we don't have one yet during setup
      // For now, we'll use the source_debate_id as a placeholder
      // In production, this might need to be called after debate creation or show static stats
      const response = await api.previewMemoryImport(sourceDebateId, sourceDebateId);
      setPreviewData({ ...previewData, [sourceDebateId]: response });
    } catch (err: any) {
      console.error('Failed to load preview:', err);
      // Preview failure is non-blocking
    } finally {
      setIsLoadingPreview({ ...isLoadingPreview, [sourceDebateId]: false });
    }
  };

  const handleScopeChange = (scope: 'all_agents' | 'specific_agents') => {
    onUpdate({ ...memoryImport, scope, selected_participant_indices: [] });
  };

  const handleParticipantToggle = (idx: number) => {
    const newIndices = memoryImport.selected_participant_indices.includes(idx)
      ? memoryImport.selected_participant_indices.filter(i => i !== idx)
      : [...memoryImport.selected_participant_indices, idx];
    
    onUpdate({ ...memoryImport, selected_participant_indices: newIndices });
  };

  const handleSourceTypeChange = (source_type: 'debate_full' | 'materials_only') => {
    onUpdate({ ...memoryImport, source_type });
  };

  const getParticipantLabel = (participant: api.SetupParticipant, idx: number): string => {
    if (participant.name) return participant.name;
    if (participant.role_description) return participant.role_description;
    return `Participant ${idx + 1}`;
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString(undefined, { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric' 
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className={styles.section}>
      <h2>Prior Review Memory</h2>
      <p className={styles.hint}>
        Optionally import materials and reviewer notes from previous sessions — useful when this is a revision round or continuation of prior work.
        Grants are immutable once the review starts, ensuring audit integrity.
      </p>

      <div className={styles.toggleRow}>
        <label className={styles.toggleLabel}>
          <input
            type="checkbox"
            checked={memoryImport.enabled}
            onChange={(e) => handleToggle(e.target.checked)}
            className={styles.toggle}
          />
          <span className={styles.toggleText}>
            {memoryImport.enabled ? 'Memory Import: ON' : 'Memory Import: OFF'}
          </span>
        </label>
      </div>

      {memoryImport.enabled && (
        <>
          {error && (
            <div className={styles.errorBanner}>
              {error}
            </div>
          )}

          {isLoadingSources ? (
            <div className={styles.loadingState}>Loading past review sessions...</div>
          ) : importableSources.length > 0 ? (
            <>
              <div className={styles.subsection}>
                <h3>1. Pick Past Review Sessions</h3>
                <p className={styles.subsectionHint}>Select one or more completed review sessions to import context from.</p>
                <div className={styles.sourceList}>
                  {importableSources.map((debate) => (
                    <label key={debate.debate_id} className={styles.sourceCard}>
                      <input
                        type="checkbox"
                        checked={memoryImport.source_debate_ids.includes(debate.debate_id)}
                        onChange={() => handleSourceToggle(debate.debate_id)}
                        className={styles.checkbox}
                      />
                      <div className={styles.sourceInfo}>
                        <div className={styles.sourceTitle}>{debate.title}</div>
                        <div className={styles.sourceMeta}>
                          <span className={styles.sourceDate}>
                            {formatDate(debate.ended_at || debate.created_at)}
                          </span>
                          <span className={styles.chip}>{debate.chunk_count} chunks</span>
                          <span className={styles.chip}>{debate.material_count} materials</span>
                          <span className={styles.chip}>{debate.participant_count} participants</span>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {memoryImport.source_debate_ids.length > 0 && (
                <>
                  <div className={styles.subsection}>
                    <h3>2. What Gets Imported?</h3>
                    <select
                      value={memoryImport.source_type}
                      onChange={(e) => handleSourceTypeChange(e.target.value as 'debate_full' | 'materials_only')}
                      className={styles.select}
                    >
                      <option value="debate_full">Full Session (all reviewer notes + documents)</option>
                      <option value="materials_only">Documents Only (uploaded files and links)</option>
                    </select>
                  </div>

                  <div className={styles.subsection}>
                    <h3>3. Who Can Use This Context?</h3>
                    <div className={styles.radioGroup}>
                      <label className={styles.radioLabel}>
                        <input
                          type="radio"
                          checked={memoryImport.scope === 'all_agents'}
                          onChange={() => handleScopeChange('all_agents')}
                          className={styles.radio}
                        />
                        <span>All Participants</span>
                      </label>
                      <label className={styles.radioLabel}>
                        <input
                          type="radio"
                          checked={memoryImport.scope === 'specific_agents'}
                          onChange={() => handleScopeChange('specific_agents')}
                          className={styles.radio}
                        />
                        <span>Only Selected Participants</span>
                      </label>
                    </div>

                    {memoryImport.scope === 'specific_agents' && (
                      <div className={styles.participantChecklistMt}>
                        {participants.length === 0 ? (
                          <p className={styles.warningText}>⚠ Add participants first in Step 3</p>
                        ) : (
                          <div className={styles.participantChecklist}>
                            {participants.map((participant, idx) => (
                              <label key={idx} className={styles.checkboxLabel}>
                                <input
                                  type="checkbox"
                                  checked={memoryImport.selected_participant_indices.includes(idx)}
                                  onChange={() => handleParticipantToggle(idx)}
                                  className={styles.checkbox}
                                />
                                <span>{getParticipantLabel(participant, idx)}</span>
                              </label>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className={styles.subsection}>
                    <h3>4. Preview</h3>
                    {memoryImport.source_debate_ids.map((debateId) => {
                      const source = importableSources.find(d => d.debate_id === debateId);
                      if (!source) return null;

                      return (
                        <div key={debateId} className={styles.previewCard}>
                          <div className={styles.previewTitle}>{source.title}</div>
                          <div className={styles.previewStats}>
                            <div className={styles.previewStat}>
                              <span className={styles.previewStatLabel}>Total Chunks:</span>
                              <span className={styles.previewStatValue}>{source.chunk_count}</span>
                            </div>
                            <div className={styles.previewStat}>
                              <span className={styles.previewStatLabel}>Materials:</span>
                              <span className={styles.previewStatValue}>{source.material_count}</span>
                            </div>
                            <div className={styles.previewStat}>
                              <span className={styles.previewStatLabel}>Artifacts:</span>
                              <span className={styles.previewStatValue}>
                                {source.artifact_count} <span className={styles.comingSoon}>(coming soon)</span>
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
