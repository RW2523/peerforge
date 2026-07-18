import { useRef, useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import * as api from '@/lib/api';
import { keyStore } from '@/lib/openrouterKeyStore';
import { validateMaterials, normalizeUrl, SETUP_LIMITS, getMainResearchFile, MAIN_RESEARCH_FILE_REQUIRED } from '@/lib/setupValidation';
import styles from './SetupSteps.module.css';

interface MaterialsStepProps {
  debateId?: string;
  materials: api.SetupMaterial[];
  onAdd: (kind: 'text' | 'link' | 'file_placeholder') => void;
  onUpdate: (idx: number, updates: Partial<api.SetupMaterial>) => void;
  onRemove: (idx: number) => void;
  uploadedFiles?: api.MaterialStatus[];
  onFilesUploaded?: (files: api.MaterialStatus[]) => void;
}

const STATUS_BADGES: Record<string, string> = {
  pending: '⏳ Pending',
  processing: '⚙️ Processing',
  complete: '✅ Ready',
  failed: '❌ Failed',
  needs_ocr: '👁️ Needs OCR',
};

const getStatusBadge = (status: string, kind?: string) => {
  if (kind === 'audio' && (status === 'pending' || status === 'processing')) {
    return '🎙️ Transcribing…';
  }
  return STATUS_BADGES[status] || status;
};

export function MaterialsStep({
  debateId,
  materials,
  onAdd,
  onUpdate,
  onRemove,
  uploadedFiles = [],
  onFilesUploaded,
}: MaterialsStepProps) {
  const mainInputRef = useRef<HTMLInputElement>(null);
  const researchInputRef = useRef<HTMLInputElement>(null);
  const transcriptInputRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pollInterval, setPollInterval] = useState<NodeJS.Timeout | null>(null);
  // Ensures unembedded chunks get embedded once processing completes (RAG safety net)
  const embedTriggeredRef = useRef(false);

  // Action items grouped by transcript material id
  const [actionItems, setActionItems] = useState<Record<string, api.TranscriptActionItem[]>>({});
  const [extracting, setExtracting] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [removingMain, setRemovingMain] = useState(false);
  const [showDeleteMainModal, setShowDeleteMainModal] = useState(false);
  const [deleteMainError, setDeleteMainError] = useState<string | null>(null);
  const deleteCancelRef = useRef<HTMLButtonElement>(null);

  // ── Status polling ──────────────────────────────────────────────────────
  const refreshStatus = useCallback(async () => {
    if (!debateId) return;
    try {
      const status = await api.getMaterialsStatus(debateId);
      if (onFilesUploaded) onFilesUploaded(status.materials);
      const allDone = status.materials.every(
        (m) => m.processed_status === 'complete' || m.processed_status === 'failed'
      );
      if (allDone && pollInterval) {
        clearInterval(pollInterval);
        setPollInterval(null);
      }
      // Once everything is processed, make sure every chunk is embedded so
      // semantic retrieval (RAG) works — covers upload-time embedding failures.
      if (allDone && status.materials.length > 0 && !embedTriggeredRef.current) {
        const key = keyStore.getKey();
        if (key) {
          embedTriggeredRef.current = true;
          api.triggerEmbeddingGeneration(debateId, key).catch(() => {
            embedTriggeredRef.current = false; // allow retry on next poll cycle
          });
        }
      }
    } catch {
      /* ignore polling errors */
    }
  }, [debateId, onFilesUploaded, pollInterval]);

  useEffect(() => {
    if (debateId) {
      refreshStatus();
      api.listActionItems(debateId)
        .then((items) => {
          const grouped: Record<string, api.TranscriptActionItem[]> = {};
          items.forEach((it) => {
            const key = it.material_id || 'unknown';
            (grouped[key] = grouped[key] || []).push(it);
          });
          setActionItems(grouped);
        })
        .catch(() => { /* none yet */ });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debateId]);

  useEffect(() => {
    return () => { if (pollInterval) clearInterval(pollInterval); };
  }, [pollInterval]);

  // ── Upload ──────────────────────────────────────────────────────────────
  const doUpload = async (
    files: FileList | null,
    category: api.MaterialCategory,
    isPrimary: boolean,
    inputRef: React.RefObject<HTMLInputElement | null>
  ) => {
    if (!files || files.length === 0 || !debateId) return;
    setUploading(category);
    setUploadError(null);
    try {
      const openrouterKey = keyStore.getKey();
      await api.uploadMaterials(debateId, Array.from(files), openrouterKey, category, isPrimary);
      await refreshStatus();
      const interval = setInterval(refreshStatus, 3000);
      setPollInterval(interval);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setUploading(null);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  // ── Action items ──────────────────────────────────────────────────────────
  const handleExtract = async (materialId: string) => {
    if (!debateId) return;
    const key = keyStore.getKey();
    if (!key) {
      setActionError('Add your OpenRouter key in Settings to extract action items.');
      return;
    }
    setExtracting(materialId);
    setActionError(null);
    try {
      const items = await api.extractActionItems(debateId, materialId, key);
      setActionItems((prev) => ({ ...prev, [materialId]: items }));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Extraction failed');
    } finally {
      setExtracting(null);
    }
  };

  const patchItem = (materialId: string, actionId: string, patch: Partial<api.TranscriptActionItem>) => {
    setActionItems((prev) => ({
      ...prev,
      [materialId]: (prev[materialId] || []).map((it) =>
        it.action_id === actionId ? { ...it, ...patch } : it
      ),
    }));
  };

  const handleEditCommit = async (materialId: string, item: api.TranscriptActionItem) => {
    if (!debateId) return;
    try {
      await api.updateActionItem(debateId, item.action_id, {
        description: item.description,
        owner: item.owner || undefined,
        priority: item.priority,
      });
    } catch { /* keep local edit */ }
  };

  const pollDecision = useCallback((materialId: string, actionId: string) => {
    if (!debateId) return;
    const timer = setInterval(async () => {
      try {
        const dec = await api.getActionItemDecision(debateId, actionId);
        if (dec.status === 'decided') {
          clearInterval(timer);
          patchItem(materialId, actionId, {
            status: 'decided',
            decision: dec.decision,
            decision_rationale: dec.decision_rationale,
            decision_debate_id: dec.decision_debate_id,
          });
        }
      } catch { /* keep polling */ }
    }, 4000);
  }, [debateId]);

  const handleRunDebate = async (materialId: string, item: api.TranscriptActionItem) => {
    if (!debateId) return;
    const key = keyStore.getKey();
    if (!key) {
      setActionError('Add your OpenRouter key in Settings to run a panel discussion.');
      return;
    }
    patchItem(materialId, item.action_id, { status: 'debating' });
    try {
      const dec = await api.debateActionItem(debateId, item.action_id, key);
      patchItem(materialId, item.action_id, { decision_debate_id: dec.decision_debate_id });
      pollDecision(materialId, item.action_id);
    } catch (e) {
      patchItem(materialId, item.action_id, { status: 'extracted' });
      setActionError(e instanceof Error ? e.message : 'Failed to start debate');
    }
  };

  // ── Derived groupings ─────────────────────────────────────────────────────
  const mainFile = getMainResearchFile(uploadedFiles);
  const researchFiles = uploadedFiles.filter((f) => f.material_category === 'research');
  const supplementaryFiles = uploadedFiles.filter(
    (f) => f.material_category === 'supplementary' || (!f.material_category && !f.is_primary)
  );
  const transcriptFiles = uploadedFiles.filter((f) => f.material_category === 'transcript');

  const handleOpenDeleteMainModal = () => {
    if (!mainFile || !debateId) return;
    setDeleteMainError(null);
    setShowDeleteMainModal(true);
  };

  const handleCloseDeleteMainModal = useCallback(() => {
    if (removingMain) return;
    setShowDeleteMainModal(false);
    setDeleteMainError(null);
  }, [removingMain]);

  const handleConfirmDeleteMainFile = async () => {
    if (!mainFile || !debateId) return;

    setRemovingMain(true);
    setDeleteMainError(null);
    try {
      await api.deleteMaterial(debateId, mainFile.material_id);
      embedTriggeredRef.current = false;
      await refreshStatus();
      setShowDeleteMainModal(false);
    } catch (error) {
      setDeleteMainError(
        error instanceof Error ? error.message : 'Failed to remove main research file'
      );
    } finally {
      setRemovingMain(false);
    }
  };

  useEffect(() => {
    if (!showDeleteMainModal) return;

    deleteCancelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') handleCloseDeleteMainModal();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [showDeleteMainModal, handleCloseDeleteMainModal]);

  // Per-card validation issues (empty/partial/duplicate) — same source of truth
  // the Next button uses, so the UI and navigation never disagree.
  const materialIssues = new Map<number, string>();
  validateMaterials(materials).forEach((i) => materialIssues.set(i.index, i.issue));

  const disabled = !debateId || uploading !== null;

  const renderFileCard = (file: api.MaterialStatus, extra?: React.ReactNode) => (
    <div key={file.material_id} className={styles.materialCard}>
      <div className={styles.cardHeader}>
        <span className={styles.badge}>{file.kind}</span>
        <span className={styles.statusBadge}>{getStatusBadge(file.processed_status, file.kind)}</span>
      </div>
      <div className={styles.materialInfo}>
        <strong>{file.title}</strong>
        {file.file_size_bytes ? (
          <span className={styles.fileSize}>{(file.file_size_bytes / 1024).toFixed(1)} KB</span>
        ) : null}
        {file.processing_metadata?.word_count ? (
          <span className={styles.wordCount}>{file.processing_metadata.word_count} words</span>
        ) : null}
        {file.processing_metadata?.chunk_count ? (
          <span className={styles.chunkCount}>{file.processing_metadata.chunk_count} chunks</span>
        ) : null}
      </div>
      {file.processed_status === 'failed' && (
        <div className={styles.errorMessage}>
          {file.processing_metadata?.error || 'Processing failed'}
        </div>
      )}
      {extra}
    </div>
  );

  return (
    <div className={styles.section}>
      <h2>Knowledge Base</h2>
      <p className={styles.hint}>
        Organize the documents your panel will study. Everything here is saved and embedded into
        the agents&apos; memory so they can cite it during the review session.
      </p>

      {uploadError && <div className={styles.error}>{uploadError}</div>}

      {/* ── Section 1: Main Research File ───────────────────────────────── */}
      <div className={styles.kbSection}>
        <h3 className={styles.kbSectionTitle}>1 · Main Research File</h3>
        <p className={styles.kbSectionDesc}>
          Your primary document (thesis, proposal, paper). Pinned and always in the knowledge base.
        </p>
        <input
          ref={mainInputRef}
          type="file"
          accept=".pdf,.docx,.pptx,.txt,.md"
          style={{ display: 'none' }}
          onChange={(e) => doUpload(e.target.files, 'main_research', true, mainInputRef)}
          disabled={disabled}
        />
        {mainFile ? (
          renderFileCard(mainFile, (
            <div className={styles.lockRow}>
              <span className={styles.lockBadge}>🔒 Always in knowledge base</span>
              <div className={styles.mainFileActions}>
                <button
                  type="button"
                  className={styles.btnSecondary}
                  onClick={() => mainInputRef.current?.click()}
                  disabled={disabled}
                >
                  Replace
                </button>
                <button
                  type="button"
                  className={styles.btnRemoveIcon}
                  onClick={handleOpenDeleteMainModal}
                  disabled={disabled || removingMain}
                  title="Remove main research file"
                  aria-label="Remove main research file"
                >
                  <svg
                    className={styles.btnRemoveIconSvg}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6l-1 14H6L5 6" />
                    <path d="M10 11v6" />
                    <path d="M14 11v6" />
                    <path d="M9 6V4h6v2" />
                  </svg>
                </button>
              </div>
            </div>
          ))
        ) : (
          <button
            className={styles.btnAdd}
            onClick={() => mainInputRef.current?.click()}
            disabled={disabled}
            title={!debateId ? 'Session being created…' : 'Upload your main research document'}
          >
            <span>📌</span> {uploading === 'main_research' ? 'Uploading…' : 'Set Main Research File'}
          </button>
        )}
        {!mainFile && (
          <span className={styles.fieldError}>{MAIN_RESEARCH_FILE_REQUIRED}</span>
        )}
      </div>

      {/* ── Section 2: Research & Supplementary ─────────────────────────── */}
      <div className={styles.kbSection}>
        <h3 className={styles.kbSectionTitle}>2 · Supporting Files</h3>
        <p className={styles.kbSectionDesc}>
          Supporting papers, datasets, notes, links, or pasted passages — upload them all together. Editable and removable.
        </p>
        <div className={styles.buttonGroup}>
          <input
            ref={researchInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.pptx,.txt,.md"
            style={{ display: 'none' }}
            onChange={(e) => doUpload(e.target.files, 'research', false, researchInputRef)}
            disabled={disabled}
          />
          <button className={styles.btnAdd} onClick={() => researchInputRef.current?.click()} disabled={disabled}>
            <span>📚</span> {uploading === 'research' ? 'Uploading…' : 'Upload Supporting Files'}
          </button>
          <button onClick={() => onAdd('text')} className={styles.btnAdd}>
            <span>📝</span> Add Text
          </button>
          <button onClick={() => onAdd('link')} className={styles.btnAdd}>
            <span>🔗</span> Add Link
          </button>
        </div>

        <div className={styles.list}>
          {[...researchFiles, ...supplementaryFiles].map((file) =>
            renderFileCard(file, (
              <span className={styles.categoryBadge}>
                {file.material_category === 'research' ? 'Research' : 'Supplementary'}
              </span>
            ))
          )}

          {materials.map((material, idx) => {
            const issue = materialIssues.get(idx);
            return (
            <div key={idx} className={styles.materialCard}>
              <div className={styles.cardHeader}>
                <span className={styles.badge}>{material.kind}</span>
                <button onClick={() => onRemove(idx)} className={styles.btnRemove}>×</button>
              </div>
              <div className={styles.materialCardFields}>
                <input
                  type="text"
                  value={material.title || ''}
                  onChange={(e) => onUpdate(idx, { title: e.target.value })}
                  placeholder={material.kind === 'text' ? 'Title (optional)' : 'Title'}
                />
                {material.kind === 'text' && (
                  <textarea
                    value={material.body_text || ''}
                    onChange={(e) => onUpdate(idx, { body_text: e.target.value })}
                    placeholder={`Paste text content here (at least ${SETUP_LIMITS.TEXT_BODY_MIN} characters)`}
                    rows={3}
                    aria-invalid={!!issue}
                  />
                )}
                {(material.kind === 'link' || material.kind === 'file_placeholder') && (
                  <input
                    type="text"
                    value={material.url || ''}
                    onChange={(e) => onUpdate(idx, { url: e.target.value })}
                    onBlur={(e) => {
                      // Auto-normalize (prepend https://, lowercase host) on blur.
                      const n = normalizeUrl(e.target.value);
                      if (n && n !== material.url) onUpdate(idx, { url: n });
                    }}
                    placeholder="https://example.com"
                    aria-invalid={!!issue}
                  />
                )}
              </div>
              {issue && <span className={styles.materialCardError}>{issue}</span>}
            </div>
            );
          })}

          {researchFiles.length === 0 && supplementaryFiles.length === 0 && materials.length === 0 && (
            <p className={styles.empty}>No supporting files yet (optional)</p>
          )}
        </div>
      </div>

      {/* ── Section 3: Transcripts & Recordings ─────────────────────────── */}
      <div className={styles.kbSection}>
        <h3 className={styles.kbSectionTitle}>3 · Meeting Transcripts &amp; Recordings</h3>
        <p className={styles.kbSectionDesc}>
          Upload a text transcript or an audio recording (transcribed automatically). Then extract
          action items and let the panel discuss each decision.
        </p>
        <input
          ref={transcriptInputRef}
          type="file"
          multiple
          accept=".txt,.md,.docx,.mp3,.wav,.m4a,.webm"
          style={{ display: 'none' }}
          onChange={(e) => doUpload(e.target.files, 'transcript', false, transcriptInputRef)}
          disabled={disabled}
        />
        <button className={styles.btnAdd} onClick={() => transcriptInputRef.current?.click()} disabled={disabled}>
          <span>🎙️</span> {uploading === 'transcript' ? 'Uploading…' : 'Upload Transcript / Recording'}
        </button>

        {actionError && <div className={styles.error}>{actionError}</div>}

        <div className={styles.list}>
          {transcriptFiles.map((file) => {
            const items = actionItems[file.material_id] || [];
            const ready = file.processed_status === 'complete';
            return renderFileCard(file, (
              <div className={styles.transcriptBlock}>
                {ready && (
                  <button
                    className={styles.btnSecondary}
                    onClick={() => handleExtract(file.material_id)}
                    disabled={extracting === file.material_id}
                  >
                    {extracting === file.material_id
                      ? 'Extracting…'
                      : items.length > 0
                        ? '↻ Re-extract Action Items'
                        : '✨ Extract Action Items'}
                  </button>
                )}
                {items.length > 0 && (
                  <div className={styles.actionItemList}>
                    {items.map((item) => (
                      <div key={item.action_id} className={styles.actionItemRow}>
                        <div className={styles.actionItemMain}>
                          <input
                            className={styles.actionItemInput}
                            value={item.description}
                            onChange={(e) => patchItem(file.material_id, item.action_id, { description: e.target.value })}
                            onBlur={() => handleEditCommit(file.material_id, item)}
                          />
                          <select
                            className={styles.actionItemPriority}
                            value={item.priority}
                            onChange={(e) => {
                              patchItem(file.material_id, item.action_id, { priority: e.target.value as api.TranscriptActionItem['priority'] });
                              handleEditCommit(file.material_id, { ...item, priority: e.target.value as api.TranscriptActionItem['priority'] });
                            }}
                          >
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                          </select>
                        </div>

                        {item.status === 'extracted' && (
                          <button
                            className={styles.btnSecondary}
                            onClick={() => handleRunDebate(file.material_id, item)}
                          >
                            🏛️ Run panel discussion
                          </button>
                        )}
                        {item.status === 'debating' && (
                          <span className={styles.decisionPending}>⚙️ Panel discussing…</span>
                        )}
                        {item.status === 'decided' && item.decision && (
                          <div className={styles.decisionBox}>
                            <strong>Decision:</strong> {item.decision}
                            {item.decision_rationale ? (
                              <p className={styles.decisionRationale}>{item.decision_rationale}</p>
                            ) : null}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ));
          })}
          {transcriptFiles.length === 0 && (
            <p className={styles.empty}>No transcripts or recordings yet (optional)</p>
          )}
        </div>
      </div>

      {showDeleteMainModal && typeof document !== 'undefined' && createPortal(
        <div
          className={styles.deleteModalOverlay}
          onClick={handleCloseDeleteMainModal}
          role="presentation"
        >
          <div
            className={styles.deleteConfirmModal}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-main-file-title"
            aria-describedby="delete-main-file-desc"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="delete-main-file-title" className={styles.deleteConfirmTitle}>
              Delete document?
            </h3>
            <p id="delete-main-file-desc" className={styles.modalBody}>
              Are you sure you want to remove this document from the review session?
            </p>
            {deleteMainError && (
              <p className={styles.modalError} role="alert">
                {deleteMainError}
              </p>
            )}
            <div className={styles.modalActions}>
              <button
                ref={deleteCancelRef}
                type="button"
                className={styles.modalBtnCancel}
                onClick={handleCloseDeleteMainModal}
                disabled={removingMain}
              >
                Cancel
              </button>
              <button
                type="button"
                className={styles.modalBtnDelete}
                onClick={handleConfirmDeleteMainFile}
                disabled={removingMain}
              >
                {removingMain ? 'Deleting…' : 'Delete document'}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
