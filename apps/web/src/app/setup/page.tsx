'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import * as api from '@/lib/api';
import { BasicInfoStep } from '@/components/setup/BasicInfoStep';
import { MaterialsStep } from '@/components/setup/MaterialsStep';
import { ParticipantsStep } from '@/components/setup/ParticipantsStep';
import { MemoryImportStep } from '@/components/setup/MemoryImportStep';
import { PreflightStep } from '@/components/setup/PreflightStep';
import { LiteratureStep } from '@/components/setup/LiteratureStep';
import { ReviewStep } from '@/components/setup/ReviewStep';
import { SetupStepper } from '@/components/setup/SetupStepper';
import { useMemoryImport } from '@/hooks/useMemoryImport';
import { isValidMaterial, normalizeUrl } from '@/lib/setupValidation';
import { useSetupValidation } from '@/hooks/useSetupValidation';
import { useParticipants } from '@/hooks/useParticipants';
import { useMaterials } from '@/hooks/useMaterials';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import { useDebateSetupActions } from '@/hooks/useDebateSetupActions';
import { useStep1Draft } from '@/hooks/useStep1Draft';
import { loadStep1Draft, step1DraftToState } from '@/lib/step1Draft';
import styles from './setup.module.css';

export default function SetupPage() {
  const router = useRouter();
  const { apiKey } = useOpenRouterKey();
  const [step, setStep] = useState(1);
  const [canEnterRoom, setCanEnterRoom] = useState(false);
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  
  // Step 1: Basic Info
  const [title, setTitle] = useState('');
  const [problemStatement, setProblemStatement] = useState('');
  const [keyPoints, setKeyPoints] = useState<string[]>([]);
  const [agenda, setAgenda] = useState<string[]>([]);
  const [desiredOutcomes, setDesiredOutcomes] = useState<string[]>([]);
  const [timeboxMinutes, setTimeboxMinutes] = useState<number | undefined>(30);
  const [maxRounds, setMaxRounds] = useState<number | undefined>(undefined);
  const [sessionLengthMode, setSessionLengthMode] = useState<'rounds' | 'time'>('time');
  
  // YOLO Mode Configuration
  const [yoloMode, setYoloMode] = useState(false);
  const [autoTurnDelay, setAutoTurnDelay] = useState(10);
  
  // Reasoning Mode
  const [reasoningMode, setReasoningMode] = useState<api.ReasoningMode>('medium');

  // Host Configuration
  const [enableHost, setEnableHost] = useState(false);
  const [hostModelId, setHostModelId] = useState('openai/gpt-4o-mini');
  
  // Document Configuration
  const [enableDocuments, setEnableDocuments] = useState(false);
  const [documentTemplateId, setDocumentTemplateId] = useState('meeting-summary');
  const [documentTitle, setDocumentTitle] = useState('');

  const step1DraftState = useMemo(
    () => ({
      title,
      problemStatement,
      keyPoints,
      agenda,
      desiredOutcomes,
      yoloMode,
      autoTurnDelay,
      sessionLengthMode,
      timeboxMinutes,
      maxRounds,
    }),
    [
      title,
      problemStatement,
      keyPoints,
      agenda,
      desiredOutcomes,
      yoloMode,
      autoTurnDelay,
      sessionLengthMode,
      timeboxMinutes,
      maxRounds,
    ]
  );

  const { draftSaved, clearDraft, suppressNextSave } = useStep1Draft(step1DraftState);

  const applyStep1State = useCallback(
    (state: ReturnType<typeof step1DraftToState>) => {
      setTitle(state.title);
      setProblemStatement(state.problemStatement);
      setKeyPoints(state.keyPoints);
      setAgenda(state.agenda);
      setDesiredOutcomes(state.desiredOutcomes);
      setYoloMode(state.yoloMode);
      setAutoTurnDelay(state.autoTurnDelay);
      setSessionLengthMode(state.sessionLengthMode);
      setTimeboxMinutes(state.timeboxMinutes);
      setMaxRounds(state.maxRounds);
    },
    []
  );

  const handleClearDraft = useCallback(() => {
    const defaults = clearDraft();
    applyStep1State(defaults);
  }, [applyStep1State, clearDraft]);

  // Restore Step 1 draft from localStorage; home-page draft overrides title/abstract.
  useEffect(() => {
    const savedDraft = loadStep1Draft();
    if (savedDraft) {
      applyStep1State(step1DraftToState(savedDraft));
    }

    const homeDraft = sessionStorage.getItem('debate_draft');
    if (homeDraft) {
      try {
        const data = JSON.parse(homeDraft);
        setTitle(data.title || '');
        setProblemStatement(data.problemStatement || '');
        sessionStorage.removeItem('debate_draft');
      } catch (e) {
        console.error('Failed to parse debate draft:', e);
      }
    }

    suppressNextSave();
  }, [applyStep1State, suppressNextSave]);
  
  // Step 2: Materials
  const {
    materials,
    handleAdd: handleAddMaterial,
    handleUpdate: handleUpdateMaterial,
    handleRemove: handleRemoveMaterial,
  } = useMaterials();
  const [uploadedFiles, setUploadedFiles] = useState<api.MaterialStatus[]>([]);
  
  // Step 3: Participants
  const {
    participants,
    setParticipants,
    handleAddFromTemplate: handleAddParticipantFromTemplate,
    handleAddExisting: handleAddExistingAgent,
    handleUpdate: handleUpdateParticipant,
    handleRemove: handleRemoveParticipant,
    handleReorder: handleReorderParticipant,
  } = useParticipants();
  const [templates, setTemplates] = useState<api.AgentTemplate[]>([]);
  const [agents, setAgents] = useState<api.Agent[]>([]);
  
  // Step 4: Memory Import
  const { memoryImport, setMemoryImport, validateMemoryImport, createMemoryGrants } = useMemoryImport();
  
  // Validation
  const { canGoNext: validateStep } = useSetupValidation();
  
  const workspaceId = '00000000-0000-0000-0000-000000000101';

  // Debate setup actions (create, launch)
  const {
    isLoading,
    createdDebateId,
    createdParticipantIds,
    setCreatedParticipantIds,
    handleCreateDebate: createDebate,
    handleLaunchDebate,
  } = useDebateSetupActions({
    workspaceId,
    title,
    problemStatement,
    enableDocuments,
    documentTemplateId,
    documentTitle,
    agenda,
    desiredOutcomes,
    timeboxMinutes,
    maxRounds,
    sessionLengthMode,
    enableHost,
    hostModelId,
    yoloMode,
    autoTurnDelay,
    participants,
    materials,
    selectedMemorySources: memoryImport.source_debate_ids,
    reasoningMode,
  });
  const steps = [
    { id: 1, label: 'Research Topic' },
    { id: 2, label: 'Materials' },
    { id: 3, label: 'Review Panel' },
    { id: 4, label: 'Prior Sessions' },
    { id: 5, label: 'Literature' },
    { id: 6, label: 'Prepare & Launch' },
  ];

  useEffect(() => {
    const loadData = async () => {
      try {
        console.log('Loading templates and agents...');
        const [templatesData, agentsData] = await Promise.all([
          api.listAgentTemplates(),
          api.listAgents(workspaceId),
        ]);
        console.log('Templates loaded:', templatesData.length);
        console.log('Agents loaded:', agentsData.length);
        setTemplates(templatesData);
        setAgents(agentsData);
      } catch (err: any) {
        console.error('Failed to load templates/agents:', err);
        alert(`Failed to load templates/agents: ${err.message}`);
      }
    };
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Create debate early (after step 1) to enable file uploads
  const handleCreateDebateEarly = async () => {
    if (createdDebateId) {
      // Debate already exists — reload its materials then proceed
      try {
        const status = await api.getMaterialsStatus(createdDebateId);
        setUploadedFiles(status.materials);
      } catch { /* ignore */ }
      setStep(2);
      return;
    }
    
    const result = await createDebate();
    if (result) {
      setStep(2);
    }
  };

  const handleCreateDebate = async () => {
    // Validate participants exist
    if (participants.length === 0) {
      alert('Please add at least one participant before continuing');
      return;
    }
    
    // Validate memory import
    const memoryError = validateMemoryImport(participants);
    if (memoryError) {
      alert(memoryError);
      return;
    }

    let result;
    
    // If debate already exists (from step 2 file uploads), just add participants.
    // Use the hook's createdParticipantIds (authoritative across calls) — the
    // local participantIds can desync and cause a duplicate debate to be created.
    if (createdDebateId && createdParticipantIds.length === 0) {
      try {
        const addResult = await api.addParticipantsToDebate(createdDebateId, participants);
        setParticipantIds(addResult.participant_ids);
        setCreatedParticipantIds(addResult.participant_ids); // Update hook state
        result = { debateId: createdDebateId, participantIds: addResult.participant_ids };
      } catch (err: any) {
        alert(`Failed to add participants: ${err.message}`);
        return;
      }
    } else {
      // Otherwise create debate with participants (or recreate if participants changed)
      result = await createDebate();
      if (result) {
        setParticipantIds(result.participantIds);
      }
    }
    if (result) {
      // Persist inline text/link materials (added in Step 2) and chunk them so
      // the review panel can actually use them — the debate was created early
      // (Step 1) before these existed, so they are sent here.
      try {
        const inline = materials
          .map((m) =>
            m.kind === 'link' || m.kind === 'file_placeholder'
              ? { ...m, url: normalizeUrl(m.url || '') }
              : m
          )
          .filter(isValidMaterial);
        if (inline.length > 0) {
          await api.addInlineMaterials(result.debateId, inline, apiKey);
        }
      } catch (matErr: any) {
        console.warn('Failed to persist inline materials:', matErr);
      }

      // Create memory grants if enabled, then advance to Literature step
      const shouldContinue = await createMemoryGrants(result.debateId, result.participantIds);
      if (shouldContinue) {
        setStep(5); // Literature step
      }
    }
  };

  const handleLaunchAfterPreflight = () => {
    if (createdDebateId) {
      handleLaunchDebate(createdDebateId, apiKey);
    }
  };

  const canGoNext = () => validateStep(step, {
    title,
    problemStatement,
    participants,
    materials,
    uploadedFiles,
    timeboxMinutes,
    maxRounds,
    sessionLengthMode,
  });

  return (
    <>
      <AppNav />
      <div className={styles.container}>
      <header className={styles.header}>
        <h1>New Review Session</h1>
        <p className={styles.subtitle}>Configure your AI review panel</p>
      </header>

      {!apiKey && (
        <div style={{
          backgroundColor: 'var(--surface-2)',
          border: '1px solid var(--warning, #ffc107)',
          borderRadius: '8px',
          padding: '16px 20px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span style={{ fontSize: '18px' }}>🔑</span>
          <div>
            <strong>OpenRouter API Key Required</strong>
            <p style={{ margin: '4px 0 0 0', color: 'var(--text-2)', fontSize: '14px' }}>
              Add your OpenRouter API key in <a href="/settings" style={{ color: 'var(--accent)', textDecoration: 'underline', fontWeight: 600 }}>Settings</a> before launching the review session. AI panel members need this key to participate.
            </p>
          </div>
        </div>
      )}

      <div className={styles.wizard}>
        <SetupStepper steps={steps} currentStep={step} />

        <div className={styles.content}>
          {step === 1 && (
            <BasicInfoStep
              title={title}
              problemStatement={problemStatement}
              keyPoints={keyPoints}
              agenda={agenda}
              desiredOutcomes={desiredOutcomes}
              timeboxMinutes={timeboxMinutes}
              maxRounds={maxRounds}
              sessionLengthMode={sessionLengthMode}
              onSessionLengthModeChange={setSessionLengthMode}
              yoloMode={yoloMode}
              autoTurnDelay={autoTurnDelay}
              onTitleChange={setTitle}
              onProblemChange={setProblemStatement}
              onKeyPointsChange={setKeyPoints}
              onAgendaChange={setAgenda}
              onDesiredOutcomesChange={setDesiredOutcomes}
              onTimeboxChange={setTimeboxMinutes}
              onMaxRoundsChange={setMaxRounds}
              onYoloModeChange={setYoloMode}
              onAutoTurnDelayChange={setAutoTurnDelay}
              isLoading={isLoading}
            />
          )}

          {step === 2 && (
            <MaterialsStep
              debateId={createdDebateId || undefined}
              materials={materials}
              onAdd={handleAddMaterial}
              onUpdate={handleUpdateMaterial}
              onRemove={handleRemoveMaterial}
              uploadedFiles={uploadedFiles}
              onFilesUploaded={(files) => setUploadedFiles(files)}
            />
          )}

          {step === 3 && (
          <>
            <ReasoningModeSelector mode={reasoningMode} onChange={setReasoningMode} />
            <ParticipantsStep
              participants={participants}
              templates={templates}
              agents={agents}
              sessionTitle={title}
              sessionAbstract={problemStatement}
              enableHost={enableHost}
              hostModelId={hostModelId}
              enableDocuments={enableDocuments}
              documentTemplateId={documentTemplateId}
              documentTitle={documentTitle}
              onEnableHostChange={setEnableHost}
              onHostModelChange={setHostModelId}
              onEnableDocumentsChange={setEnableDocuments}
              onDocumentTemplateChange={setDocumentTemplateId}
              onDocumentTitleChange={setDocumentTitle}
              onAddFromTemplate={handleAddParticipantFromTemplate}
              onAddExisting={handleAddExistingAgent}
              onUpdate={handleUpdateParticipant}
              onRemove={handleRemoveParticipant}
              onReorder={handleReorderParticipant}
            />
          </>
          )}

          {step === 4 && (
            <MemoryImportStep
              workspaceId={workspaceId}
              participants={participants}
              memoryImport={memoryImport}
              onUpdate={setMemoryImport}
            />
          )}

          {step === 5 && (
            <LiteratureStep
              debateId={createdDebateId}
              researchQuestion={problemStatement}
              onCanContinueChange={setCanEnterRoom}
            />
          )}

          {step === 6 && (
            <>
              <PreflightStep
                debateId={createdDebateId}
                participants={participants}
                participantIds={createdParticipantIds}
                onCanContinueChange={setCanEnterRoom}
                meetingTitle={title}
                meetingPurpose={problemStatement}
                meetingAgenda={agenda}
                desiredOutcomes={desiredOutcomes}
              />
              <ReviewStep
                title={title}
                problemStatement={problemStatement}
                timeboxMinutes={timeboxMinutes}
                yoloMode={yoloMode}
                autoTurnDelay={autoTurnDelay}
                materials={materials}
                participants={participants}
                workspaceId={workspaceId}
              />
            </>
          )}
        </div>

        <div className={styles.navigation}>
          {step > 1 && (
            <button 
              onClick={() => {
                if (step === 6) {
                  setStep(5); // Back to Literature from Prepare & Launch
                } else {
                  setStep(step - 1);
                }
              }} 
              disabled={isLoading}
              className={styles.btnPrevious}
            >
              <span className={styles.btnIcon}>←</span>
              <span>Previous</span>
            </button>
          )}
          
          <div style={{ flex: 1 }} />
          
          {step === 1 && (
            <div className={styles.step1NavGroup}>
              {draftSaved && (
                <button
                  type="button"
                  onClick={handleClearDraft}
                  className={styles.btnClearDraft}
                  disabled={isLoading}
                >
                  Clear draft
                </button>
              )}
              <button
                onClick={handleCreateDebateEarly}
                disabled={!canGoNext() || isLoading}
                className={styles.btnNext}
              >
                <span>{isLoading ? 'Creating...' : 'Next'}</span>
                <span className={styles.btnIcon}>→</span>
              </button>
            </div>
          )}
          
          {step > 1 && step < 4 && (
            <button
              onClick={() => setStep(step + 1)}
              disabled={!canGoNext() || isLoading}
              className={styles.btnNext}
            >
              <span>Next</span>
              <span className={styles.btnIcon}>→</span>
            </button>
          )}
          
          {step === 4 && (
            <button
              onClick={handleCreateDebate}
              disabled={!canGoNext() || isLoading}
              className={styles.btnNext}
            >
              <span>{isLoading ? 'Creating...' : 'Continue to Literature Search'}</span>
              <span className={styles.btnIcon}>→</span>
            </button>
          )}

          {step === 5 && (
            <button
              onClick={() => setStep(6)}
              disabled={isLoading}
              className={styles.btnNext}
            >
              <span>Continue to Prepare &amp; Launch</span>
              <span className={styles.btnIcon}>→</span>
            </button>
          )}
          
          {step === 6 && (
            <button
              onClick={handleLaunchAfterPreflight}
              disabled={isLoading || !canEnterRoom || !apiKey}
              className={styles.btnLaunch}
              title={!apiKey ? 'Add OpenRouter API key in Settings first' : !canEnterRoom ? 'Complete panel preparation first' : ''}
            >
              <span className={styles.launchIcon} />
              <span>
                {isLoading ? 'Loading...' : !apiKey ? 'API Key Required' : 'Launch Review Session'}
              </span>
            </button>
          )}
        </div>
      </div>
      </div>
    </>
  );
}

// ── Reasoning Mode Selector (inline) ──────────────────────────────────────

const MODE_OPTS = [
  { id: 'light'  as api.ReasoningMode, label: 'Light',  hint: 'Single fast model for all tasks' },
  { id: 'medium' as api.ReasoningMode, label: 'Medium', hint: 'Role-aware balanced models' },
  { id: 'heavy'  as api.ReasoningMode, label: 'Heavy',  hint: 'Frontier models for every activity' },
];

function ReasoningModeSelector({
  mode,
  onChange,
}: {
  mode: api.ReasoningMode;
  onChange: (m: api.ReasoningMode) => void;
}) {
  return (
    <div style={{
      marginBottom: 24, padding: 16,
      border: '1px solid var(--border-medium)',
      borderRadius: 'var(--radius-lg)',
      background: 'var(--surface-1)',
    }}>
      <h3 style={{ margin: '0 0 4px', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-0)', letterSpacing: '-0.01em' }}>
        Reasoning Mode
      </h3>
      <p style={{ margin: '0 0 14px', fontSize: '0.8rem', color: 'var(--text-2)', lineHeight: 1.5 }}>
        Controls which AI models are used for agent turns, analysis, evaluation, and reports.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {MODE_OPTS.map(opt => (
          <button
            key={opt.id}
            onClick={() => onChange(opt.id)}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4,
              padding: '12px 14px',
              border: `1px solid ${mode === opt.id ? 'var(--accent)' : 'var(--border-medium)'}`,
              borderRadius: 'var(--radius-md)',
              background: mode === opt.id ? 'var(--accent-subtle)' : 'var(--surface-2)',
              cursor: 'pointer',
              transition: 'border-color 150ms, background 150ms',
              textAlign: 'left',
            }}
          >
            <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-0)' }}>{opt.label}</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-3)', lineHeight: 1.4 }}>{opt.hint}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
