import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import * as api from '@/lib/api';
import {
  SETUP_LIMITS,
  validateTimebox,
  validateRounds,
} from '@/lib/setupValidation';
import styles from './SetupSteps.module.css';

interface BasicInfoStepProps {
  title: string;
  problemStatement: string;
  agenda: string[];
  desiredOutcomes: string[];
  timeboxMinutes?: number;
  maxRounds?: number;
  yoloMode?: boolean;
  autoTurnDelay?: number;
  onTitleChange: (value: string) => void;
  onProblemChange: (value: string) => void;
  onAgendaChange: (value: string[]) => void;
  onDesiredOutcomesChange: (value: string[]) => void;
  onTimeboxChange: (value: number | undefined) => void;
  onMaxRoundsChange: (value: number | undefined) => void;
  onYoloModeChange?: (value: boolean) => void;
  onAutoTurnDelayChange?: (value: number) => void;
  isLoading: boolean;
}

export function BasicInfoStep({
  title,
  problemStatement,
  agenda,
  desiredOutcomes,
  timeboxMinutes,
  maxRounds,
  yoloMode = false,
  autoTurnDelay = 10,
  onTitleChange,
  onProblemChange,
  onAgendaChange,
  onDesiredOutcomesChange,
  onTimeboxChange,
  onMaxRoundsChange,
  onYoloModeChange,
  onAutoTurnDelayChange,
  isLoading,
}: BasicInfoStepProps) {
  const router = useRouter();
  const { apiKey } = useOpenRouterKey();
  const [agendaInput, setAgendaInput] = useState('');
  const [outcomeInput, setOutcomeInput] = useState('');
  const [meetingType, setMeetingType] = useState<'rounds' | 'time'>(maxRounds ? 'rounds' : 'time');
  const [isGenerating, setIsGenerating] = useState(false);
  const [showKeyPoints, setShowKeyPoints] = useState(false);
  const [keyPoints, setKeyPoints] = useState<string[]>([]);
  const [agendaError, setAgendaError] = useState('');
  const [outcomeError, setOutcomeError] = useState('');

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
  const roundsError = meetingType === 'rounds' ? validateRounds(maxRounds) : null;
  const timeboxError = meetingType === 'time' ? validateTimebox(timeboxMinutes) : null;

  const handleAddAgendaItem = () => {
    const item = agendaInput.trim();
    if (!item) return;
    if (item.length > SETUP_LIMITS.ITEM_MAX) {
      setAgendaError(`Keep items under ${SETUP_LIMITS.ITEM_MAX} characters.`);
      return;
    }
    if (agenda.some((a) => a.trim().toLowerCase() === item.toLowerCase())) {
      setAgendaError('This item is already added.');
      return;
    }
    onAgendaChange([...agenda, item]);
    setAgendaInput('');
    setAgendaError('');
  };

  const handleRemoveAgendaItem = (index: number) => {
    onAgendaChange(agenda.filter((_, i) => i !== index));
  };

  const handleAddOutcome = () => {
    const item = outcomeInput.trim();
    if (!item) return;
    if (item.length > SETUP_LIMITS.ITEM_MAX) {
      setOutcomeError(`Keep items under ${SETUP_LIMITS.ITEM_MAX} characters.`);
      return;
    }
    if (desiredOutcomes.some((o) => o.trim().toLowerCase() === item.toLowerCase())) {
      setOutcomeError('This item is already added.');
      return;
    }
    onDesiredOutcomesChange([...desiredOutcomes, item]);
    setOutcomeInput('');
    setOutcomeError('');
  };

  const handleRemoveOutcome = (index: number) => {
    onDesiredOutcomesChange(desiredOutcomes.filter((_, i) => i !== index));
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
      setKeyPoints(result.key_points);
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
            <li key={index}>
              <span>{item}</span>
              <button 
                type="button"
                onClick={() => handleRemoveAgendaItem(index)}
                className={styles.removeButton}
                disabled={isLoading}
              >
                ✕
              </button>
            </li>
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
            <li key={index}>
              <span>{item}</span>
              <button 
                type="button"
                onClick={() => handleRemoveOutcome(index)}
                className={styles.removeButton}
                disabled={isLoading}
              >
                ✕
              </button>
            </li>
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
          className={`${styles.limitCard} ${meetingType === 'rounds' ? styles.limitCardActive : ''}`}
          onClick={() => {
            if (!isLoading) {
              setMeetingType('rounds');
              onTimeboxChange(undefined);
              onMaxRoundsChange(3);
            }
          }}
        >
          <div className={styles.cardIcon}>🔄</div>
          <div className={styles.cardTitle}>Rounds-Based</div>
          <div className={styles.cardDescription}>
            Each agent speaks once per round
          </div>
          {meetingType === 'rounds' && (
            <>
            <div className={styles.cardInput}>
              <input
                type="number"
                value={maxRounds ?? ''}
                onChange={(e) => {
                  e.stopPropagation();
                  const raw = e.target.value;
                  if (raw === '') { onMaxRoundsChange(undefined); return; }
                  let n = parseInt(raw, 10);
                  if (Number.isNaN(n)) { onMaxRoundsChange(undefined); return; }
                  // Clamp to [1, 20] so negatives / huge values can't be entered.
                  n = Math.max(SETUP_LIMITS.ROUNDS_MIN, Math.min(SETUP_LIMITS.ROUNDS_MAX, n));
                  onMaxRoundsChange(n);
                }}
                placeholder="3"
                disabled={isLoading}
                min={SETUP_LIMITS.ROUNDS_MIN}
                max={SETUP_LIMITS.ROUNDS_MAX}
                step="1"
                onClick={(e) => e.stopPropagation()}
              />
              <span>rounds</span>
            </div>
            {roundsError
              ? <span className={styles.fieldError}>{roundsError}</span>
              : <span className={styles.fieldHint}>{SETUP_LIMITS.ROUNDS_MIN}–{SETUP_LIMITS.ROUNDS_MAX} rounds.</span>}
            </>
          )}
        </div>

        <div 
          className={`${styles.limitCard} ${meetingType === 'time' ? styles.limitCardActive : ''}`}
          onClick={() => {
            if (!isLoading) {
              setMeetingType('time');
              onMaxRoundsChange(undefined);
              onTimeboxChange(30);
            }
          }}
        >
          <div className={styles.cardIcon}>⏱️</div>
          <div className={styles.cardTitle}>Time-Based</div>
          <div className={styles.cardDescription}>
            Unlimited rounds within time limit
          </div>
          {meetingType === 'time' && (
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
