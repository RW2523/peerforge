import { useState } from 'react';
import * as api from '@/lib/api';
import { keyStore } from '@/lib/openrouterKeyStore';
import styles from './SummaryGenerateForm.module.css';

interface SummaryGenerateFormProps {
  debateId: string;
  isLoading: boolean;
  onGenerate: (summary: api.SummaryResponse) => void;
  onStatusChange: (status: string) => void;
}

const SUMMARY_MODELS = [
  { id: 'anthropic/claude-sonnet-4-5', label: 'Claude Sonnet 4.5 (recommended)' },
  { id: 'openai/gpt-4o-mini', label: 'GPT-4o Mini (fast, cheap)' },
  { id: 'openai/gpt-4o', label: 'GPT-4o' },
  { id: 'anthropic/claude-3-haiku', label: 'Claude 3 Haiku (fast)' },
  { id: 'google/gemini-flash-1.5', label: 'Gemini Flash 1.5' },
  { id: 'meta-llama/llama-3.1-8b-instruct', label: 'Llama 3.1 8B (free tier)' },
];

export function SummaryGenerateForm({
  debateId,
  isLoading,
  onGenerate,
  onStatusChange,
}: SummaryGenerateFormProps) {
  // Pre-fill key from keyStore so user doesn't have to re-enter it
  const [openrouterKey, setOpenrouterKey] = useState(() => keyStore.getKey() || '');
  const [modelId, setModelId] = useState('anthropic/claude-sonnet-4-5');

  const handleGenerate = async () => {
    if (!openrouterKey.trim()) {
      onStatusChange('Error: OpenRouter API key required');
      return;
    }

    onStatusChange('Generating summary via OpenRouter...');
    try {
      const result = await api.generateSummary(debateId, {
        openrouter_api_key: openrouterKey,
        model_id: modelId,
      }, openrouterKey);
      onGenerate(result);
      onStatusChange('Summary generated successfully');
    } catch (err: any) {
      onStatusChange(`Error: ${err.message}`);
    }
  };

  return (
    <div className={styles.container}>
      <h3>Generate Meeting Outputs</h3>
      <label>OpenRouter API Key (BYOK)</label>
      <input
        type="password"
        value={openrouterKey}
        onChange={(e) => setOpenrouterKey(e.target.value)}
        placeholder="sk-or-v1-..."
        disabled={isLoading}
      />
      <label>Model</label>
      <select
        value={modelId}
        onChange={(e) => setModelId(e.target.value)}
        disabled={isLoading}
        style={{ padding: '8px 10px', borderRadius: 6, background: '#111', color: '#fff', border: '1px solid #333' }}
      >
        {SUMMARY_MODELS.map(m => (
          <option key={m.id} value={m.id}>{m.label}</option>
        ))}
      </select>
      <button
        onClick={handleGenerate}
        disabled={isLoading || !openrouterKey.trim()}
        className={styles.btnPrimary}
      >
        Generate Summary (uses OpenRouter credits)
      </button>
    </div>
  );
}
