import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import * as api from '@/lib/api';
import {
  SETUP_LIMITS,
  validateTimebox,
  validateRounds,
  validateListItem,
  type SessionLengthMode,
} from '@/lib/setupValidation';
import { EditableListItem } from './EditableListItem';
import styles from './SetupSteps.module.css';

interface BasicInfoStepProps {
  title: string;
  problemStatement: string;
  keyPoints: string[];
  agenda: string[];
  desiredOutcomes: string[];
  timeboxMinutes?: number;
  maxRounds?: number;
  sessionLengthMode: SessionLengthMode;
  yoloMode?: boolean;
  autoTurnDelay?: number;
  onTitleChange: (value: string) => void;
  onProblemChange: (value: string) => void;
  onKeyPointsChange: (value: string[]) => void;
  onAgendaChange: (value: string[]) => void;
  onDesiredOutcomesChange: (value: string[]) => void;
  onTimeboxChange: (value: number | undefined) => void;
  onMaxRoundsChange: (value: number | undefined) => void;
  onSessionLengthModeChange: (mode: SessionLengthMode) => void;
  onYoloModeChange?: (value: boolean) => void;
  onAutoTurnDelayChange?: (value: number) => void;
  isLoading: boolean;
}

export function BasicInfoStep({
  title,
  problemStatement,
  keyPoints,
  agenda,
  desiredOutcomes,
  timeboxMinutes,
  maxRounds,
  sessionLengthMode,
  yoloMode = false,
  autoTurnDelay = 10,
  onTitleChange,
  onProblemChange,
  onKeyPointsChange,
  onAgendaChange,
  onDesiredOutcomesChange,
  onTimeboxChange,
  onMaxRoundsChange,
  onSessionLengthModeChange,
  onYoloModeChange,
  onAutoTurnDelayChange,
  isLoading,
}: BasicInfoStepProps) {
  const router = useRouter();
  const { apiKey } = useOpenRouterKey();
  const [agendaInput, setAgendaInput] = useState('');
  const [outcomeInput, setOutcomeInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [showKeyPoints, setShowKeyPoints] = useState(false);
  const [agendaError, setAgendaError] = useState('');
  const [outcomeError, setOutcomeError] = useState('');
  const [editingAgendaIndex, setEditingAgendaIndex] = useState<number | null>(null);
  const [agendaEditValue, setAgendaEditValue] = useState('');
  const [agendaEditError, setAgendaEditError] = useState('');
  const [editingOutcomeIndex, setEditingOutcomeIndex] = useState<number | null>(null);
  const [outcomeEditValue, setOutcomeEditValue] = useState('');
  const [outcomeEditError, setOutcomeEditError] = useState('');

  useEffect(() => {
    setShowKeyPoints(keyPoints.length > 0);
  }, [keyPoints]);

  useEffect(() => {
    if (editingAgendaIndex !== null && editingAgendaIndex >= agenda.length) {
      setEditingAgendaIndex(null);
      setAgendaEditValue('');
      setAgendaEditError('');
    }
  }, [agenda.length, editingAgendaIndex]);

  useEffect(() => {
    if (editingOutcomeIndex !== null && editingOutcomeIndex >= desiredOutcomes.length) {
      setEditingOutcomeIndex(null);
      setOutcomeEditValue('');
      setOutcomeEditError('');
    }
  }, [desiredOutcomes.length, editingOutcomeIndex]);

  // Live validation hints (BUG-001..005) — Next is gated by the shared
  // validator in setup/page.tsx; these just surface the reason inline.
  const titleTrim = title.trim();
  const abstractTrim = problemStatement.trim();
  const titleError =
    titleTrim.length > 0 && titleTrim.length < SETUP_LIMITS.TITLE_MIN
      ? `Title must be at least ${SETUP_LIMITS.TITLE_MIN} characters.`
      : '';
  const abstractError =
    abstractTrim.length > 0 && abstractTrim.length < SETUP_LIMITS.ABSTRACT_MIN
      ? `Abstract must be at least ${SETUP_LIMITS.ABSTRACT_MIN} characters (currently ${abstractTrim.length}).`
      : '';
  const roundsError = sessionLengthMode === 'rounds' ? validateRounds(maxRounds) : null;
  const timeboxError = sessionLengthMode === 'time' ? validateTimebox(timeboxMinutes) : null;

  const selectRoundsMode = () => {
    if (isLoading || sessionLengthMode === 'rounds') return;
    onSessionLengthModeChange('rounds');
    if (maxRounds === undefined) {
      onMaxRoundsChange(SETUP_LIMITS.ROUNDS_DEFAULT);
    }
  };

  const selectTimeMode = () => {
    if (isLoading || sessionLengthMode === 'time') return;
    onSessionLengthModeChange('time');
    if (timeboxMinutes === undefined) {
      onTimeboxChange(30);
    }
  };

  const handleRoundsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    const raw = e.target.value;
    if (raw === '') {
      onMaxRoundsChange(undefined);
      return;
    }
    const n = Number(raw);
    if (Number.isNaN(n)) {
      onMaxRoundsChange(undefined);
      return;
    }
    onMaxRoundsChange(n);
  };

  const handleRoundsBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.stopPropagation();
    const raw = e.target.value;
    if (raw === '') return;
    const n = Number(raw);
    if (!Number.isFinite(n) || !Number.isInteger(n)) return;
    if (n < SETUP_LIMITS.ROUNDS_MIN) {
      onMaxRoundsChange(SETUP_LIMITS.ROUNDS_MIN);
    } else if (n > SETUP_LIMITS.ROUNDS_MAX) {
      onMaxRoundsChange(SETUP_LIMITS.ROUNDS_MAX);
    }
  };

  const handleAddAgendaItem = () => {
    const trimmed = agendaInput.trim();
    const error = validateListItem(trimmed, agenda, null);
    if (error) {
      setAgendaError(error);
      return;
    }
    onAgendaChange([...agenda, trimmed]);
    setAgendaInput('');
    setAgendaError('');
  };

  const handleRemoveAgendaItem = (index: number) => {
    if (editingAgendaIndex === index) {
      setEditingAgendaIndex(null);
      setAgendaEditValue('');
      setAgendaEditError('');
    }
    onAgendaChange(agenda.filter((_, i) => i !== index));
  };

  const startAgendaEdit = (index: number) => {
    setEditingOutcomeIndex(null);
    setOutcomeEditValue('');
    setOutcomeEditError('');
    setEditingAgendaIndex(index);
    setAgendaEditValue(agenda[index]);
    setAgendaEditError('');
  };

  const saveAgendaEdit = () => {
    if (editingAgendaIndex === null) return;
    const error = validateListItem(agendaEditValue, agenda, editingAgendaIndex);
    if (error) {
      setAgendaEditError(error);
      return;
    }
    const next = [...agenda];
    next[editingAgendaIndex] = agendaEditValue.trim();
    onAgendaChange(next);
    setEditingAgendaIndex(null);
    setAgendaEditValue('');
    setAgendaEditError('');
  };

  const cancelAgendaEdit = () => {
    setEditingAgendaIndex(null);
    setAgendaEditValue('');
    setAgendaEditError('');
  };

  const handleAddOutcome = () => {
    const trimmed = outcomeInput.trim();
    const error = validateListItem(trimmed, desiredOutcomes, null);
    if (error) {
      setOutcomeError(error);
      return;
    }
    onDesiredOutcomesChange([...desiredOutcomes, trimmed]);
    setOutcomeInput('');
    setOutcomeError('');
  };

  const handleRemoveOutcome = (index: number) => {
    if (editingOutcomeIndex === index) {
      setEditingOutcomeIndex(null);
      setOutcomeEditValue('');
      setOutcomeEditError('');
    }
    onDesiredOutcomesChange(desiredOutcomes.filter((_, i) => i !== index));
  };

  const startOutcomeEdit = (index: number) => {
    setEditingAgendaIndex(null);
    setAgendaEditValue('');
    setAgendaEditError('');
    setEditingOutcomeIndex(index);
    setOutcomeEditValue(desiredOutcomes[index]);
    setOutcomeEditError('');
  };

  const saveOutcomeEdit = () => {
    if (editingOutcomeIndex === null) return;
    const error = validateListItem(outcomeEditValue, desiredOutcomes, editingOutcomeIndex);
    if (error) {
      setOutcomeEditError(error);
      return;
    }
    const next = [...desiredOutcomes];
    next[editingOutcomeIndex] = outcomeEditValue.trim();
    onDesiredOutcomesChange(next);
    setEditingOutcomeIndex(null);
    setOutcomeEditValue('');
    setOutcomeEditError('');
  };

  const cancelOutcomeEdit = () => {
    setEditingOutcomeIndex(null);
    setOutcomeEditValue('');
    setOutcomeEditError('');
  };

  const handleImproveProblemStatement = async () => {
    if (!apiKey) {
      router.push('/settings');
      return;
    }

    if (!problemStatement || problemStatement.trim().length < 10) {
      alert('Please enter at least a brief problem statement (10+ characters) to improve');
      return;
    }

    // BUG-006: warn before AI overwrites existing agenda/objectives.
    if (agenda.length > 0 || desiredOutcomes.length > 0) {
      const ok = window.confirm(
        'Refine with AI will replace your current agenda and objectives with AI-generated ones. Continue?'
      );
      if (!ok) return;
    }

    setIsGenerating(true);

    // Set a 25 second timeout (backend times out at 20s)
    const timeoutId = setTimeout(() => {
      setIsGenerating(false);
      alert('Request is taking too long. Please check:\n\n1. Your OpenRouter API key is valid\n2. You have credits at openrouter.ai\n3. Your internet connection is stable');
    }, 25000);
    
    try {
      const result = await api.improveProblemStatement(problemStatement, apiKey);
      clearTimeout(timeoutId);
      
      // Update problem statement
      onProblemChange(result.improved_text);
      
      // Update key points
      onKeyPointsChange(result.key_points);
      if (result.key_points.length > 0) {
        setShowKeyPoints(true);
      }
      
      // Update agenda items if provided (cap length, drop duplicates)
      if (result.agenda_items && result.agenda_items.length > 0) {
        const cleaned = Array.from(
          new Map(
            result.agenda_items
              .map((s) => s.trim())
              .filter((s) => s && s.length <= SETUP_LIMITS.ITEM_MAX)
              .map((s) => [s.toLowerCase(), s])
          ).values()
        );
        onAgendaChange(cleaned);
      }

      // Update desired outcomes if provided (cap length, drop duplicates)
      if (result.desired_outcomes && result.desired_outcomes.length > 0) {
        const cleaned = Array.from(
          new Map(
            result.desired_outcomes
              .map((s) => s.trim())
              .filter((s) => s && s.length <= SETUP_LIMITS.ITEM_MAX)
              .map((s) => [s.toLowerCase(), s])
          ).values()
        );
        onDesiredOutcomesChange(cleaned);
      }

    } catch (err) {
      clearTimeout(timeoutId);
      console.error('Failed to improve problem statement:', err);
      
      // Better error handling
      let errorMsg = 'Failed to improve problem statement';
      if (err instanceof Error) {
        errorMsg = err.message;
      }
      
      // Show helpful error messages
      if (errorMsg.includes('Invalid API key')) {
        alert('❌ Invalid OpenRouter API Key\n\nPlease check your API key in Settings.\nGet a key at: openrouter.ai');
      } else if (errorMsg.includes('insufficient credits')) {
        alert('💳 Insufficient Credits\n\nYour OpenRouter account needs credits.\nAdd credits at: openrouter.ai');
      } else if (errorMsg.includes('slow to respond')) {
        alert('⏱️ AI Service Timeout\n\nOpenRouter is responding slowly.\n\nTry:\n1. Wait a moment and try again\n2. Check openrouter.ai/status\n3. Use a shorter problem statement');
      } else {
        alert(`❌ Error: ${errorMsg}\n\nPlease try again or check the console for details.`);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className={styles.section}>
      <h2>Research Idea &amp; Scope</h2>
      
      <label>Project / Paper Title *</label>
      <input
        type="text"
        value={title}
        onChange={(e) => onTitleChange(e.target.value)}
        placeholder="e.g., Transformer-based models for low-resource NLP"
        disabled={isLoading}
        aria-invalid={!!titleError}
      />
      {titleError
        ? <span className={styles.fieldError}>{titleError}</span>
        : <span className={styles.fieldHint}>At least {SETUP_LIMITS.TITLE_MIN} characters.</span>}

      <label>
        Research Question / Abstract *
        <button
          type="button"
          onClick={handleImproveProblemStatement}
          disabled={isLoading || isGenerating || !problemStatement.trim()}
          className={styles.generateButton}
          title="Use AI to improve this research statement"
        >
    {isGenerating ? (
            <>
              <span className={styles.spinner}>⏳</span> Generating...
            </>
          ) : (
            <>
              ✨ Refine with AI
            </>
          )}
        </button>
      </label>
      <textarea
        value={problemStatement}
        onChange={(e) => onProblemChange(e.target.value)}
        placeholder="Describe your research question, hypothesis, methodology, or what you want reviewed. Include key contributions and open questions."
        rows={4}
        disabled={isLoading || isGenerating}
        aria-invalid={!!abstractError}
      />
      {abstractError
        ? <span className={styles.fieldError}>{abstractError}</span>
        : <span className={styles.fieldHint}>At least {SETUP_LIMITS.ABSTRACT_MIN} characters — the more detail, the better the review.</span>}
      {showKeyPoints && keyPoints.length > 0 && (
        <div className={styles.keyPoints}>
          <div className={styles.keyPointsHeader}>
            <strong>Key Research Points:</strong>
            <button
              type="button"
              onClick={() => setShowKeyPoints(false)}
              className={styles.closeButton}
            >
              ✕
            </button>
          </div>
          <ul>
            {keyPoints.map((point, idx) => (
              <li key={idx}>{point}</li>
            ))}
          </ul>
        </div>
      )}

      <label>Session Agenda (optional)</label>
      <div className={styles.listInput}>
        <input
          type="text"
          value={agendaInput}
          onChange={(e) => { setAgendaInput(e.target.value); if (agendaError) setAgendaError(''); }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleAddAgendaItem();
            }
          }}
          placeholder="Add agenda item and press Enter"
          maxLength={SETUP_LIMITS.ITEM_MAX}
          disabled={isLoading}
        />
        <button 
          type="button" 
          onClick={handleAddAgendaItem}
          disabled={!agendaInput.trim() || isLoading}
          className={styles.addButton}
        >
          + Add
        </button>
      </div>
      {agendaError && <span className={styles.fieldError}>{agendaError}</span>}
      {agenda.length > 0 && (
        <ul className={styles.itemList}>
          {agenda.map((item, index) => (
            <EditableListItem
              key={`${index}-${item}`}
              item={item}
              isEditing={editingAgendaIndex === index}
              editValue={agendaEditValue}
              editError={agendaEditError}
              disabled={isLoading}
              onStartEdit={() => startAgendaEdit(index)}
              onEditValueChange={(value) => {
                setAgendaEditValue(value);
                if (agendaEditError) setAgendaEditError('');
              }}
              onSave={saveAgendaEdit}
              onCancel={cancelAgendaEdit}
              onRemove={() => handleRemoveAgendaItem(index)}
            />
          ))}
        </ul>
      )}

      <label>Session Objectives (optional)</label>
      <div className={styles.listInput}>
        <input
          type="text"
          value={outcomeInput}
          onChange={(e) => { setOutcomeInput(e.target.value); if (outcomeError) setOutcomeError(''); }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleAddOutcome();
            }
          }}
          placeholder="Add desired outcome and press Enter"
          maxLength={SETUP_LIMITS.ITEM_MAX}
          disabled={isLoading}
        />
        <button 
          type="button" 
          onClick={handleAddOutcome}
          disabled={!outcomeInput.trim() || isLoading}
          className={styles.addButton}
        >
          + Add
        </button>
      </div>
      {outcomeError && <span className={styles.fieldError}>{outcomeError}</span>}
      {desiredOutcomes.length > 0 && (
        <ul className={styles.itemList}>
          {desiredOutcomes.map((item, index) => (
            <EditableListItem
              key={`${index}-${item}`}
              item={item}
              isEditing={editingOutcomeIndex === index}
              editValue={outcomeEditValue}
              editError={outcomeEditError}
              disabled={isLoading}
              onStartEdit={() => startOutcomeEdit(index)}
              onEditValueChange={(value) => {
                setOutcomeEditValue(value);
                if (outcomeEditError) setOutcomeEditError('');
              }}
              onSave={saveOutcomeEdit}
              onCancel={cancelOutcomeEdit}
              onRemove={() => handleRemoveOutcome(index)}
            />
          ))}
        </ul>
      )}

      {/* YOLO Mode Toggle */}
      <div className={styles.yoloSection}>
        <div className={styles.yoloHeader}>
          <label className={styles.yoloLabel}>
            <div className={styles.yoloTitle}>
              Auto Mode
              <span className={styles.betaBadge}>AUTO</span>
            </div>
            <div className={styles.yoloDescription}>
              Fully autonomous session — panel members run without manual intervention
            </div>
          </label>
          <label className={styles.toggleSwitch}>
            <input
              type="checkbox"
              checked={yoloMode}
              onChange={(e) => onYoloModeChange?.(e.target.checked)}
              disabled={isLoading}
            />
            <span className={styles.slider}></span>
          </label>
        </div>
        
        {yoloMode && (
          <div className={styles.yoloSettings}>
            <div className={styles.yoloInfo}>
              Review will run automatically without manual intervention
            </div>
            <label>Auto-turn delay (seconds)</label>
            <input
              type="range"
              min="5"
              max="60"
              value={autoTurnDelay}
              onChange={(e) => onAutoTurnDelayChange?.(parseInt(e.target.value))}
              disabled={isLoading}
              className={styles.rangeSlider}
            />
            <div className={styles.sliderValue}>{autoTurnDelay}s between turns</div>
          </div>
        )}
      </div>

      {/* Review Limit Cards */}
      <label>Session Length</label>
      <div className={styles.limitCards}>
        <div 
          className={`${styles.limitCard} ${sessionLengthMode === 'rounds' ? styles.limitCardActive : ''}`}
          onClick={selectRoundsMode}
        >
          <div className={styles.cardIcon}>🔄</div>
          <div className={styles.cardTitle}>Rounds-Based</div>
          <div className={styles.cardDescription}>
            Each agent speaks once per round
          </div>
          {sessionLengthMode === 'rounds' && (
            <>
            <div className={styles.cardInput}>
              <input
                type="number"
                value={maxRounds ?? ''}
                onChange={handleRoundsChange}
                onBlur={handleRoundsBlur}
                placeholder="3"
                disabled={isLoading}
                min={SETUP_LIMITS.ROUNDS_MIN}
                max={SETUP_LIMITS.ROUNDS_MAX}
                step="1"
                onClick={(e) => e.stopPropagation()}
                onMouseDown={(e) => e.stopPropagation()}
              />
              <span>rounds</span>
            </div>
            {roundsError
              ? <span className={styles.fieldError}>{roundsError}</span>
              : <span className={styles.fieldHint}>{SETUP_LIMITS.ROUNDS_MIN}–{SETUP_LIMITS.ROUNDS_MAX} rounds</span>}
            </>
          )}
        </div>

        <div 
          className={`${styles.limitCard} ${sessionLengthMode === 'time' ? styles.limitCardActive : ''}`}
          onClick={selectTimeMode}
        >
          <div className={styles.cardIcon}>⏱️</div>
          <div className={styles.cardTitle}>Time-Based</div>
          <div className={styles.cardDescription}>
            Unlimited rounds within time limit
          </div>
          {sessionLengthMode === 'time' && (
            <>
            <div className={styles.cardInput}>
              <input
                type="number"
                value={timeboxMinutes ?? ''}
                onChange={(e) => {
                  e.stopPropagation();
                  const raw = e.target.value;
                  if (raw === '') { onTimeboxChange(undefined); return; }
                  let n = parseInt(raw, 10);
                  if (Number.isNaN(n)) { onTimeboxChange(undefined); return; }
                  // Clamp to [1, 120] so negatives / huge values can't be entered.
                  n = Math.max(SETUP_LIMITS.TIMEBOX_MIN, Math.min(SETUP_LIMITS.TIMEBOX_MAX, n));
                  onTimeboxChange(n);
                }}
                placeholder="30"
                disabled={isLoading}
                min={SETUP_LIMITS.TIMEBOX_MIN}
                max={SETUP_LIMITS.TIMEBOX_MAX}
                step="1"
                onClick={(e) => e.stopPropagation()}
              />
              <span>minutes</span>
            </div>
            {timeboxError
              ? <span className={styles.fieldError}>{timeboxError}</span>
              : <span className={styles.fieldHint}>{SETUP_LIMITS.TIMEBOX_MIN}–{SETUP_LIMITS.TIMEBOX_MAX} minutes (5–60 recommended).</span>}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
