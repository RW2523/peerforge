'use client';

import { useState, useEffect, useMemo } from 'react';
import * as api from '@/lib/api';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import styles from './ModelSelector.module.css';

interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
  placeholder?: string;
}

export function ModelSelector({ value, onChange, placeholder = 'Select a model...' }: ModelSelectorProps) {
  const { apiKey } = useOpenRouterKey();
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [models, setModels] = useState<api.OpenRouterModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch models when dropdown opens (if not already loaded)
  useEffect(() => {
    if (isOpen && models.length === 0 && apiKey) {
      fetchModels();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, apiKey]);

  const fetchModels = async () => {
    if (!apiKey) {
      setError('OpenRouter API key required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await api.listOpenRouterModels(apiKey);
      setModels(response.models);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load models');
    } finally {
      setLoading(false);
    }
  };

  // Filter models based on search query
  const filteredModels = useMemo(() => {
    if (!searchQuery.trim()) return models;
    
    const query = searchQuery.toLowerCase();
    return models.filter(model => 
      model.id.toLowerCase().includes(query) ||
      model.name?.toLowerCase().includes(query)
    );
  }, [models, searchQuery]);

  // Group models by provider
  const groupedModels = useMemo(() => {
    const groups: Record<string, api.OpenRouterModel[]> = {};
    
    filteredModels.forEach(model => {
      const provider = model.id.split('/')[0] || 'other';
      if (!groups[provider]) {
        groups[provider] = [];
      }
      groups[provider].push(model);
    });
    
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredModels]);

  // Get selected model display name
  const selectedModel = models.find(m => m.id === value);
  const displayValue = selectedModel?.name || value || placeholder;

  const handleSelect = (modelId: string) => {
    onChange(modelId);
    setIsOpen(false);
    setSearchQuery('');
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(`.${styles.modelSelector}`)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  return (
    <div className={styles.modelSelector}>
      <button
        type="button"
        className={styles.selectorButton}
        onClick={() => setIsOpen(!isOpen)}
        disabled={!apiKey}
      >
        <span className={styles.selectedValue}>{displayValue}</span>
        <span className={styles.arrow}>{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className={styles.dropdown}>
          <div className={styles.searchBox}>
            <input
              type="text"
              placeholder="🔍 Search models..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={styles.searchInput}
              autoFocus
            />
          </div>

          {loading && (
            <div className={styles.dropdownMessage}>
              Loading models...
            </div>
          )}

          {error && (
            <div className={styles.dropdownError}>
              {error}
              {!apiKey && (
                <p className={styles.errorHint}>
                  Add your OpenRouter key in Settings first
                </p>
              )}
            </div>
          )}

          {!loading && !error && filteredModels.length === 0 && (
            <div className={styles.dropdownMessage}>
              No models found
            </div>
          )}

          {!loading && !error && filteredModels.length > 0 && (
            <div className={styles.modelsList}>
              {groupedModels.map(([provider, providerModels]) => (
                <div key={provider} className={styles.providerGroup}>
                  <div className={styles.providerLabel}>{provider}</div>
                  {providerModels.map(model => (
                    <button
                      key={model.id}
                      type="button"
                      className={`${styles.modelOption} ${value === model.id ? styles.modelOptionSelected : ''}`}
                      onClick={() => handleSelect(model.id)}
                    >
                      <div className={styles.modelName}>{model.name || model.id}</div>
                      <div className={styles.modelId}>{model.id}</div>
                      {model.context_length && (
                        <div className={styles.modelMeta}>
                          {model.context_length.toLocaleString()} tokens
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
