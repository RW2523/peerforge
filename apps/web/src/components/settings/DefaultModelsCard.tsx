'use client';

import { useState, useEffect } from 'react';
import * as api from '@/lib/api';
import styles from './DefaultModelsCard.module.css';

interface DefaultModelsCardProps {
  apiKey: string | null;
  workspaceId: string;
}

export function DefaultModelsCard({ apiKey, workspaceId }: DefaultModelsCardProps) {
  const [workspaceModels, setWorkspaceModels] = useState<api.WorkspaceModelsResponse | null>(null);
  const [embeddingsModelId, setEmbeddingsModelId] = useState('');
  const [ocrModelId, setOcrModelId] = useState('');
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [modelsSuccess, setModelsSuccess] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);

  useEffect(() => {
    fetchWorkspaceModels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (apiKey) {
      fetchAvailableModels();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey]);

  const fetchAvailableModels = async () => {
    if (!apiKey) return;

    try {
      const data = await api.listOpenRouterModels(apiKey);
      const modelIds = data.models.map((m: any) => m.id);
      setAvailableModels(modelIds);
    } catch (err) {
      console.error('Failed to fetch available models:', err);
    }
  };

  const fetchWorkspaceModels = async () => {
    try {
      const data = await api.getWorkspaceModels(workspaceId);
      setWorkspaceModels(data);
      setEmbeddingsModelId(data.embeddings_model_id);
      setOcrModelId(data.ocr_model_id);
    } catch (err) {
      setEmbeddingsModelId('moonshot/kimi-embeddings-v1');
      setOcrModelId('qwen/qwen-2.5-72b-instruct');
    }
  };

  const handleSaveModels = async () => {
    if (!embeddingsModelId || !ocrModelId) return;

    setModelsLoading(true);
    setModelsError(null);
    setModelsSuccess(false);

    try {
      const data = await api.updateWorkspaceModels(workspaceId, {
        embeddings_model_id: embeddingsModelId,
        ocr_model_id: ocrModelId,
      });
      
      setWorkspaceModels(data);
      setModelsSuccess(true);
      
      setTimeout(() => setModelsSuccess(false), 3000);
    } catch (err) {
      setModelsError(err instanceof Error ? err.message : 'Failed to save defaults');
    } finally {
      setModelsLoading(false);
    }
  };

  return (
    <section className={styles.card}>
      <h2>Default Models (Workspace)</h2>
      <p className={styles.cardDesc}>
        These model defaults sync across all devices for this workspace. Your OpenRouter key stays in your browser only.
      </p>

      <div className={styles.form}>
        <label>
          RAG / Embeddings Model
          {availableModels.length > 0 ? (
            <select
              value={embeddingsModelId}
              onChange={(e) => setEmbeddingsModelId(e.target.value)}
              className={styles.select}
            >
              <option value="moonshot/kimi-embeddings-v1">Kimi 2.5 Embeddings (Default)</option>
              <option value="openai/text-embedding-3-small">OpenAI text-embedding-3-small</option>
              <option value="openai/text-embedding-3-large">OpenAI text-embedding-3-large</option>
              {availableModels
                .filter(id => id.includes('embed'))
                .map(id => (
                  <option key={id} value={id}>{id}</option>
                ))}
            </select>
          ) : (
            <input
              type="text"
              value={embeddingsModelId}
              onChange={(e) => setEmbeddingsModelId(e.target.value)}
              placeholder="moonshot/kimi-embeddings-v1"
            />
          )}
          <span className={styles.fieldHint}>
            Used for semantic search and RAG retrieval. {!apiKey && '(Add OpenRouter key above to see all available models)'}
          </span>
        </label>

        <label>
          OCR Post-Processing Model
          {availableModels.length > 0 ? (
            <select
              value={ocrModelId}
              onChange={(e) => setOcrModelId(e.target.value)}
              className={styles.select}
            >
              <option value="qwen/qwen-2.5-72b-instruct">Qwen 2.5 72B (Default)</option>
              <option value="qwen/qwen-2.5-32b-instruct">Qwen 2.5 32B</option>
              <option value="anthropic/claude-3-haiku">Claude 3 Haiku</option>
              {availableModels
                .filter(id => 
                  (id.includes('qwen') || id.includes('claude') || id.includes('gpt')) &&
                  !id.includes('embed')
                )
                .slice(0, 20)
                .map(id => (
                  <option key={id} value={id}>{id}</option>
                ))}
            </select>
          ) : (
            <input
              type="text"
              value={ocrModelId}
              onChange={(e) => setOcrModelId(e.target.value)}
              placeholder="qwen/qwen-2.5-72b-instruct"
            />
          )}
          <span className={styles.fieldHint}>
            Used after OCR to clean up and structure extracted text. {!apiKey && '(Add OpenRouter key above to see all available models)'}
          </span>
        </label>

        <button
          onClick={handleSaveModels}
          disabled={!embeddingsModelId || !ocrModelId || modelsLoading}
          className={styles.btnPrimary}
        >
          {modelsLoading ? 'Saving...' : 'Save Defaults'}
        </button>
      </div>

      {modelsError && (
        <div className={styles.error}>
          <span>❌</span>
          <div>
            <strong>Failed to Save</strong>
            <p>{modelsError}</p>
          </div>
        </div>
      )}

      {modelsSuccess && (
        <div className={styles.success}>
          <span>&#10003;</span>
          <div>
            <strong>Defaults Saved!</strong>
            <p>These settings are now active for this workspace across all devices.</p>
          </div>
        </div>
      )}

      {workspaceModels && (
        <div className={styles.timestamp}>
          Last updated: {new Date(workspaceModels.updated_at).toLocaleString()}
        </div>
      )}
    </section>
  );
}
