import { useState } from 'react';
import * as api from '@/lib/api';
import { keyStore } from '@/lib/openrouterKeyStore';
import { ModelSelector } from './ModelSelector';
import styles from './SetupSteps.module.css';

interface ParticipantsStepProps {
  participants: api.SetupParticipant[];
  templates: api.AgentTemplate[];
  agents: api.Agent[];
  /** Session title + abstract — used by the AI panel suggester. */
  sessionTitle?: string;
  sessionAbstract?: string;
  enableHost: boolean;
  hostModelId?: string;
  enableDocuments?: boolean;
  documentTemplateId?: string;
  documentTitle?: string;
  onEnableHostChange: (enabled: boolean) => void;
  onHostModelChange: (modelId: string) => void;
  onEnableDocumentsChange?: (enabled: boolean) => void;
  onDocumentTemplateChange?: (templateId: string) => void;
  onDocumentTitleChange?: (title: string) => void;
  onAddFromTemplate: (template: api.AgentTemplate) => void;
  onAddExisting: (agent: api.Agent) => void;
  onUpdate: (idx: number, updates: Partial<api.SetupParticipant>) => void;
  onRemove: (idx: number) => void;
  onReorder?: (fromIdx: number, toIdx: number) => void;
}

export function ParticipantsStep({
  participants,
  templates,
  agents,
  sessionTitle,
  sessionAbstract,
  enableHost,
  hostModelId,
  enableDocuments,
  documentTemplateId,
  documentTitle,
  onEnableHostChange,
  onHostModelChange,
  onEnableDocumentsChange,
  onDocumentTemplateChange,
  onDocumentTitleChange,
  onAddFromTemplate,
  onAddExisting,
  onUpdate,
  onRemove,
  onReorder,
}: ParticipantsStepProps) {
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [showAllTemplates, setShowAllTemplates] = useState(false);
  const [showAllAgents, setShowAllAgents] = useState(false);
  const [agentSearchQuery, setAgentSearchQuery] = useState('');
  const [suggesting, setSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<
    { template: api.AgentTemplate; reason: string }[] | null
  >(null);

  const handleMoveUp = (idx: number) => {
    if (idx > 0 && onReorder) {
      onReorder(idx, idx - 1);
    }
  };

  const handleMoveDown = (idx: number) => {
    if (idx < participants.length - 1 && onReorder) {
      onReorder(idx, idx + 1);
    }
  };

  // Get unique categories (excluding Facilitator since we hide Ultimate Host)
  const categories = ['All', ...Array.from(new Set(templates
    .filter(t => t.category !== 'Facilitator')
    .map(t => t.category)))];
  
  // Filter templates by category and exclude Ultimate Host
  const availableTemplates = templates.filter(t => 
    t.template_id !== 'ultimate-host' && 
    t.role_title !== 'Ultimate Host' &&
    t.label !== 'Ultimate Host (Neutral Moderator)'
  );
  
  const filteredTemplates = selectedCategory === 'All' 
    ? availableTemplates 
    : availableTemplates.filter(t => t.category === selectedCategory);
  
  // Limit templates shown initially (show 6, then "Show more" button)
  const displayedTemplates = showAllTemplates ? filteredTemplates : filteredTemplates.slice(0, 6);
  
  // Filter and limit agents (exclude inline/test agents and Ultimate Host)
  const filteredAgents = agents.filter(agent => 
    agent.name.toLowerCase().includes(agentSearchQuery.toLowerCase()) &&
    !agent.name.includes('(Inline)') &&  // Exclude inline template instances
    !agent.name.includes('Ultimate Host') &&
    agent.name !== 'Test PM Agent' &&
    agent.name !== 'Persistent PM'
  );
  const displayedAgents = showAllAgents ? filteredAgents : filteredAgents.slice(0, 6);
  
  // Check if template is already selected
  const isTemplateSelected = (templateId: string) => {
    return participants.some(p => 
      p.name && templates.find(t => 
        t.template_id === templateId && 
        t.label === p.name
      )
    );
  };
  
  // Check if agent is already selected
  const isAgentSelected = (agentId: string) => {
    return participants.some(p => p.agent_id === agentId);
  };

  // ── AI panel suggestion ────────────────────────────────────────────────
  const handleSuggestPanel = async () => {
    setSuggestError(null);
    const key = keyStore.getKey();
    if (!key) {
      setSuggestError('Add your OpenRouter API key in Settings to use AI suggestions.');
      return;
    }
    if (!(sessionTitle || '').trim() && !(sessionAbstract || '').trim()) {
      setSuggestError('Fill in the research title and abstract in Step 1 first.');
      return;
    }
    setSuggesting(true);
    try {
      const res = await api.suggestPanelTemplates(
        sessionTitle || '',
        sessionAbstract || '',
        availableTemplates,
        key,
        5,
      );
      const matched = res.suggestions
        .map(s => {
          const template = availableTemplates.find(t => t.template_id === s.template_id);
          return template ? { template, reason: s.reason } : null;
        })
        .filter((x): x is { template: api.AgentTemplate; reason: string } => x !== null);
      setSuggestions(matched);
      // Auto-select the suggested templates (respect the 8-member cap)
      let slots = 8 - participants.length;
      for (const { template } of matched) {
        if (slots <= 0) break;
        if (!isTemplateSelected(template.template_id)) {
          onAddFromTemplate(template);
          slots -= 1;
        }
      }
    } catch (e) {
      setSuggestError(e instanceof Error ? e.message : 'Suggestion failed');
    } finally {
      setSuggesting(false);
    }
  };

  return (
    <div className={styles.section}>
      <h2>Select AI Panel Members ({participants.length}/8)</h2>
      <p className={styles.hint}>
        Assemble your review panel. Mix domain experts, methodologists, skeptical reviewers, and independent reviewers for thorough preparation.
        <strong> Min 2, Max 8 panel members.</strong>
      </p>

      {/* Compact Ultimate Host Toggle */}
      <div className={styles.hostConfigCompact}>
        <div className={styles.hostToggleRow}>
          <label htmlFor="enable-host" className={styles.hostToggleLabel}>
            <span className={styles.hostIcon} />
            <span className={styles.hostName}>Enable Panel Chair</span>
            <span className={styles.hostHint}>Neutral chair synthesizes all panel positions and delivers final recommendation</span>
          </label>
          
          <div className={styles.hostControls}>
            {enableHost && (
              <select
                value={hostModelId || 'openai/gpt-4o-mini'}
                onChange={(e) => onHostModelChange(e.target.value)}
                className={styles.hostModelSelectCompact}
                title="Host AI Model"
              >
                <option value="anthropic/claude-sonnet-4-5">Claude Sonnet 4.5 (recommended)</option>
                <option value="openai/gpt-4o-mini">GPT-4o Mini</option>
                <option value="openai/gpt-4o">GPT-4o</option>
                <option value="anthropic/claude-3-haiku">Claude 3 Haiku (fast)</option>
                <option value="google/gemini-flash-1.5">Gemini Flash 1.5</option>
                <option value="meta-llama/llama-3.1-8b-instruct">Llama 3.1 8B</option>
                <option value="google/gemini-pro-1.5">Gemini Pro 1.5</option>
              </select>
            )}
            
            <label className={styles.toggleSwitch}>
              <input
                type="checkbox"
                id="enable-host"
                checked={enableHost}
                onChange={(e) => onEnableHostChange(e.target.checked)}
              />
              <span className={styles.slider}></span>
            </label>
          </div>
        </div>
      </div>

      {/* Document Collaboration Toggle */}
      <div className={styles.hostConfigCompact} style={{marginTop: '16px'}}>
        <div className={styles.hostToggleRow}>
          <label htmlFor="enable-documents" className={styles.hostToggleLabel}>
            <span className={styles.hostIcon} />
            <span className={styles.hostName}>Enable Document Collaboration</span>
            <span className={styles.hostHint}>Agents write structured documents together with diagrams</span>
          </label>
          
          <div className={styles.hostControls}>
            {enableDocuments && (
              <>
                <select
                  value={documentTemplateId || 'meeting-summary'}
                  onChange={(e) => onDocumentTemplateChange?.(e.target.value)}
                  className={styles.hostModelSelectCompact}
                  title="Document Template"
                  style={{marginRight: '8px'}}
                >
                  <option value="meeting-summary">Session Feedback Report</option>
                  <option value="medical-consultation">Research Summary</option>
                  <option value="technical-decision">Technical Review</option>
                  <option value="business-strategy">Methodology Assessment</option>
                </select>
                <input
                  type="text"
                  value={documentTitle || ''}
                  onChange={(e) => onDocumentTitleChange?.(e.target.value)}
                  placeholder="Document title..."
                  className={styles.hostModelSelectCompact}
                  style={{width: '180px', marginRight: '8px'}}
                />
              </>
            )}
            
            <label className={styles.toggleSwitch}>
              <input
                type="checkbox"
                id="enable-documents"
                checked={enableDocuments || false}
                onChange={(e) => onEnableDocumentsChange?.(e.target.checked)}
              />
              <span className={styles.slider}></span>
            </label>
          </div>
        </div>
      </div>

      <div className={styles.twoColumnLayout}>
        {/* LEFT: Selection Panel */}
        <div className={styles.selectionPanel}>
          {/* Agent Templates */}
          <div className={styles.templates}>
            <div className={styles.templateHeader}>
              <h3>Agent Templates</h3>
              <button
                onClick={handleSuggestPanel}
                disabled={suggesting || participants.length >= 8}
                className={styles.suggestPanelBtn}
                title="AI reads your title and abstract and picks the 5 most relevant panel members"
              >
                {suggesting ? '✨ Matching panel to your research…' : '✨ Suggest Panel from Title & Abstract'}
              </button>
              <div className={styles.categoryFilter}>
                {categories.map((category) => (
                  <button
                    key={category}
                    onClick={() => setSelectedCategory(category)}
                    className={`${styles.categoryBtn} ${selectedCategory === category ? styles.categoryBtnActive : ''}`}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>

            {suggestError && <div className={styles.error}>{suggestError}</div>}

            {suggestions && suggestions.length > 0 && (
              <div className={styles.suggestionBox}>
                <div className={styles.suggestionTitle}>
                  ✨ Suggested for your research (auto-selected):
                </div>
                <ul className={styles.suggestionList}>
                  {suggestions.map(({ template, reason }) => (
                    <li key={template.template_id}>
                      <strong>{template.label}</strong> — {reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className={styles.templateGrid}>
              {displayedTemplates.map((template) => {
                const isSelected = isTemplateSelected(template.template_id);
                return (
                  <button
                    key={template.template_id}
                    onClick={() => onAddFromTemplate(template)}
                    className={`${styles.templateCard} ${isSelected ? styles.templateCardSelected : ''}`}
                    disabled={participants.length >= 8 || isSelected}
                    title={isSelected ? 'Already selected' : 'Click to add'}
                  >
                    {isSelected && <div className={styles.selectedBadge}>✓</div>}
                    <div className={styles.templateLabel}>{template.label}</div>
                    <div className={styles.templateRole}>{template.role_title}</div>
                    {template.character && (
                      <div className={styles.templateCharacter}>{template.character}</div>
                    )}
                  </button>
                );
              })}
            </div>
            {filteredTemplates.length > 6 && (
              <button
                onClick={() => setShowAllTemplates(!showAllTemplates)}
                className={styles.showMoreBtn}
              >
                {showAllTemplates ? '↑ Show Less' : `↓ Show ${filteredTemplates.length - 6} More Templates`}
              </button>
            )}
          </div>

          {/* Existing Agents */}
          {agents.length > 0 && (
            <div className={styles.templates}>
              <div className={styles.templateHeader}>
                <h3>Existing Agents ({agents.length})</h3>
                <input
                  type="text"
                  placeholder="🔍 Search agents..."
                  value={agentSearchQuery}
                  onChange={(e) => setAgentSearchQuery(e.target.value)}
                  className={styles.searchInput}
                />
              </div>
              <div className={styles.templateGrid}>
                {displayedAgents.map((agent) => {
                  const isSelected = isAgentSelected(agent.agent_id);
                  return (
                    <button
                      key={agent.agent_id}
                      onClick={() => onAddExisting(agent)}
                      className={`${styles.templateCard} ${isSelected ? styles.templateCardSelected : ''}`}
                      disabled={participants.length >= 8 || isSelected}
                      title={isSelected ? 'Already selected' : 'Click to add'}
                    >
                      {isSelected && <div className={styles.selectedBadge}>✓</div>}
                      <div className={styles.templateLabel}>{agent.name}</div>
                      <div className={styles.templateRole}>{agent.role_description || 'Custom Agent'}</div>
                    </button>
                  );
                })}
              </div>
              {filteredAgents.length > 6 && (
                <button
                  onClick={() => setShowAllAgents(!showAllAgents)}
                  className={styles.showMoreBtn}
                >
                  {showAllAgents ? '↑ Show Less' : `↓ Show ${filteredAgents.length - 6} More Agents`}
                </button>
              )}
            </div>
          )}
        </div>

        {/* RIGHT: Selected Participants (Sticky) */}
        <div className={styles.selectedPanel}>
          <div className={styles.selectedPanelSticky}>
            <h3>Selected Participants ({participants.length}/8)</h3>
            {participants.length > 1 && (
              <p className={styles.orderHint}>💡 Use ↑/↓ arrows to define turn order</p>
            )}
            
            {participants.length === 0 && (
              <div className={styles.emptyState}>
                <div className={styles.emptyIcon}>👥</div>
                <p>No participants selected yet</p>
                <span className={styles.emptyHint}>Click templates on the left to add</span>
              </div>
            )}

          {participants
            .filter(p => p.name !== 'Ultimate Host')
              .map((participant, idx) => (
              <div key={idx} className={styles.selectedParticipantCard}>
                <div className={styles.cardHeader}>
                  <div className={styles.participantHeaderLeft}>
                    <span className={styles.turnOrderBadge}>#{idx + 1}</span>
                    <span className={styles.participantName}>
                      {participant.agent_id ? `📌 ${participant.name}` : participant.name}
                    </span>
                  </div>
                  <div className={styles.cardActions}>
                    {onReorder && participants.length > 1 && (
                      <div className={styles.orderControls}>
                        <button
                          onClick={() => handleMoveUp(idx)}
                          disabled={idx === 0}
                          className={styles.btnOrder}
                          title="Move up in turn order"
                        >
                          ↑
                        </button>
                        <button
                          onClick={() => handleMoveDown(idx)}
                          disabled={idx === participants.length - 1}
                          className={styles.btnOrder}
                          title="Move down in turn order"
                        >
                          ↓
                        </button>
                      </div>
                    )}
                    <button
                      onClick={() => setEditingIdx(editingIdx === idx ? null : idx)}
                      className={styles.btnEditInline}
                      title="Edit participant"
                    >
                      {editingIdx === idx ? '✕' : '✏️'}
                    </button>
                    <button 
                      onClick={() => onRemove(idx)} 
                      className={styles.btnRemoveInline}
                      title="Remove participant"
                    >
                      ×
                    </button>
                  </div>
                </div>
                
                {editingIdx === idx && (
                  <div className={styles.editorPanelInline}>
                    {participant.agent_id && (
                      <div className={styles.agentIdBadge}>
                        📌 Editing Existing Agent - Changes are for this debate only
                      </div>
                    )}
                    
                    <label>Name</label>
                    <input
                      type="text"
                      value={participant.name || ''}
                      onChange={(e) => onUpdate(idx, { name: e.target.value })}
                      placeholder="Agent Name"
                      disabled={!!participant.agent_id}
                    />
                    
                    <label>System Prompt</label>
                    <textarea
                      value={participant.system_prompt || ''}
                      onChange={(e) => onUpdate(idx, { system_prompt: e.target.value })}
                      placeholder="You are..."
                      rows={4}
                    />
                    
                    <label>Model</label>
                    <ModelSelector
                      value={participant.model_id || ''}
                      onChange={(modelId) => onUpdate(idx, { model_id: modelId })}
                      placeholder="Select AI model..."
                    />
                    
                    <label>Temperature (0.0 - 2.0)</label>
                    <input
                      type="range"
                      min="0"
                      max="2"
                      step="0.1"
                      value={participant.model_config?.temperature ?? 0.7}
                      onChange={(e) => {
                        const temperature = parseFloat(e.target.value);
                        onUpdate(idx, {
                          model_config: {
                            ...(participant.model_config || {}),
                            temperature
                          }
                        });
                      }}
                      className={styles.tempSlider}
                    />
                    <div className={styles.tempValue}>
                      {(participant.model_config?.temperature ?? 0.7).toFixed(1)}
                    </div>
                    
                    <label>Advanced Config (JSON)</label>
                    <textarea
                      value={JSON.stringify(participant.model_config || {temperature: 0.7}, null, 2)}
                      onChange={(e) => {
                        try {
                          onUpdate(idx, { model_config: JSON.parse(e.target.value) });
                        } catch {}
                      }}
                      rows={3}
                      placeholder='{"temperature": 0.7, "max_tokens": 1000}'
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
