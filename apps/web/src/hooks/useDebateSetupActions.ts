/**
 * Hook for debate setup actions (create, launch)
 * Extracted from setup/page.tsx for maintainability
 */
import { useState } from 'react';
import { keyStore } from '@/lib/openrouterKeyStore';
import { useRouter } from 'next/navigation';
import * as api from '@/lib/api';
import type { SetupParticipant, SetupMaterial } from '@/lib/api';
import { getAccessToken } from '@/lib/supabase';
import { useToast } from '@/components/ui/Toaster';
import { isValidMaterial, normalizeUrl } from '@/lib/setupValidation';

interface UseDebateSetupActionsOptions {
  workspaceId: string | null;
  title: string;
  problemStatement: string;
  agenda?: string[];
  desiredOutcomes?: string[];
  timeboxMinutes?: number;
  maxRounds?: number;
  sessionLengthMode?: 'rounds' | 'time';
  enableHost?: boolean;
  hostModelId?: string;
  yoloMode?: boolean;
  autoTurnDelay?: number;
  enableDocuments?: boolean;
  documentTemplateId?: string;
  documentTitle?: string;
  participants: SetupParticipant[];
  materials: SetupMaterial[];
  selectedMemorySources: string[];
  reasoningMode?: api.ReasoningMode;
}

interface UseDebateSetupActionsReturn {
  isLoading: boolean;
  createdDebateId: string | null;
  createdParticipantIds: string[];
  setCreatedParticipantIds: (ids: string[]) => void;
  handleCreateDebate: () => Promise<{ debateId: string; participantIds: string[] } | null>;
  handleLaunchDebate: (debateId: string, apiKey: string | null) => Promise<void>;
}

export function useDebateSetupActions(
  options: UseDebateSetupActionsOptions
): UseDebateSetupActionsReturn {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const toast = useToast();
  const [createdDebateId, setCreatedDebateId] = useState<string | null>(null);
  const [createdParticipantIds, setCreatedParticipantIds] = useState<string[]>([]);

  const handleCreateDebate = async () => {
    if (!options.workspaceId) {
      toast.notify('Still loading your workspace — try again in a moment.');
      return null;
    }
    const {
      workspaceId,
      title,
      problemStatement,
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
      selectedMemorySources,
      reasoningMode,
    } = options;

    // Allow creating debate without participants initially (for file uploads)
    // Validation happens later at preflight
    setIsLoading(true);
    try {
      // Only send valid materials, with link URLs normalized — prevents empty/
      // invalid cards from reaching the backend and skewing material counts.
      const cleanMaterials = (materials || [])
        .map((m) =>
          m.kind === 'link' || m.kind === 'file_placeholder'
            ? { ...m, url: normalizeUrl(m.url || '') }
            : m
        )
        .filter(isValidMaterial);

      // 1. Create debate (returns participant_ids)
      // Host is NOT a participant - it's stored in policy_config
      const setupResponse = await api.setupDebate({
        workspace_id: workspaceId,
        title,
        problem_statement: problemStatement,
        agenda: agenda && agenda.length > 0 ? agenda : undefined,
        desired_outcomes: desiredOutcomes && desiredOutcomes.length > 0 ? desiredOutcomes : undefined,
        timebox_minutes: timeboxMinutes || 30,
        max_rounds: sessionLengthMode === 'rounds' ? maxRounds : undefined,
        enable_host: enableHost || false,
        host_model_id: enableHost ? (hostModelId || 'openai/gpt-4o-mini') : undefined,
        participants: participants,
        materials: cleanMaterials.length > 0 ? cleanMaterials : undefined,
        reasoning_mode: reasoningMode || 'medium',
      });

      const { debate_id, participant_ids } = setupResponse;
      setCreatedDebateId(debate_id);
      setCreatedParticipantIds(participant_ids);

      // 2. Import memory if selected — grant to ALL agents (scope defaults to
      // 'all_agents', which requires participant_ids to be null/omitted).
      if (selectedMemorySources && selectedMemorySources.length > 0) {
        try {
          await api.importMemory(debate_id, {
            source_debate_ids: selectedMemorySources,
            scope: 'all_agents',
          });
          console.log('Memory imported successfully');
        } catch (memErr: any) {
          console.error('Memory import failed:', memErr);
          toast.notify(`Past-session memory could not be imported (${memErr.message}). The session will run without it.`);
        }
      }

      // 3. Create document if enabled
      if (options.enableDocuments) {
        try {
          const { getAllTemplates } = await import('@/lib/document/templates');
          const templates = getAllTemplates();
          const selectedTemplate = templates.find(t => t.id === options.documentTemplateId);
          
          if (selectedTemplate) {
            const docTitle = options.documentTitle || `${title} - ${selectedTemplate.name}`;
            await api.createDocument({
              debate_id: debate_id,
              template_id: options.documentTemplateId || 'meeting-summary',
              title: docTitle,
              custom_sections: selectedTemplate.sections,
            });
            console.log('✅ Document created successfully');
          }
        } catch (docErr: any) {
          console.error('Document creation failed:', docErr);
          toast.notify(`The shared document could not be created (${docErr.message}). The session will run without it.`);
        }
      }

      return { debateId: debate_id, participantIds: participant_ids };
    } catch (err: any) {
      toast.error(`Could not create the session: ${err.message}`);
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const handleLaunchDebate = async (debateId: string, apiKey: string | null) => {
    // Prevent double-clicks causing duplicate launches
    if (isLoading) {
      console.log('⚠️ Launch already in progress, ignoring duplicate click');
      return;
    }

    // Validate auth token before launching (required for WebSocket connection)
    try {
      const authToken = await getAccessToken();
      if (!authToken) {
        // This used to instruct the person using the product to edit a
        // .env.local file they have never seen.
        toast.error('You are signed out. Sign in again to start this session.');
        return;
      }
    } catch (err: any) {
      toast.error(`Could not confirm you are signed in: ${err.message}`);
      return;
    }

    // Validate API key before launching
    if (!keyStore.hasKey()) {
      toast.error('An OpenRouter API key is needed before the panel can run.', {
        label: 'Open Settings',
        onClick: () => { window.location.href = '/settings'; },
      });
      return;
    }

    // Test API key validity by making a quick validation call
    // SKIP validation for now - it's timing out and blocking launches
    // The debate will fail naturally if API key is invalid
    console.log('⚠️ Skipping API key validation (was causing timeouts)');
    
    // try {
    //   await api.getOpenRouterAccount(apiKey);
    // } catch (err: any) {
    //   alert(
    //     `⚠️ Invalid OpenRouter API Key\n\nYour API key failed validation: ${err.message}\n\nPlease update your API key in Settings before launching the debate.`
    //   );
    //   return;
    // }

    if (!debateId) {
      toast.error('This session has not been created yet — finish the setup steps first.');
      return;
    }

    setIsLoading(true);

    try {
      // Fetch current debate state first to avoid re-starting an already-running debate
      let currentState: string | null = null;
      try {
        const current = await api.getDebate(debateId);
        currentState = current.state;
      } catch { /* ignore — getDebate failing shouldn't block launch */ }

      if (currentState === 'ended') {
        toast.error('This review session has already ended. Start a new one to continue.');
        return;
      }

      // Only call startDebate if not already running/paused
      if (currentState === 'pending' || currentState === null) {
        // Pass key so the backend can queue embedding backfill immediately
        await api.startDebate(debateId, apiKey);
      } else {
        console.log(`Debate already in state "${currentState}", skipping startDebate`);
      }

      // Check if YOLO mode is enabled
      if (options.yoloMode) {
        if (!keyStore.hasKey()) {
          throw new Error('OpenRouter API key required for YOLO mode. Please add it in Settings.');
        }
        await api.startAutonomousDebate(debateId, options.autoTurnDelay || 10, apiKey);
        console.log('🚀 YOLO Mode activated!');
      } else {
        // Trigger first agent turn in manual mode (non-fatal if it fails — user can trigger from room)
        try {
          await api.triggerNextTurn(debateId, apiKey);
        } catch (turnErr: any) {
          console.warn('First turn trigger failed (non-fatal):', turnErr.message);
        }
      }

      // Navigate to room
      router.push(`/room?debate_id=${debateId}`);
    } catch (err: any) {
      console.error('Failed to start debate:', err);
      toast.error(`Could not start the session: ${err.message || 'unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  return {
    isLoading,
    createdDebateId,
    createdParticipantIds,
    setCreatedParticipantIds,
    handleCreateDebate,
    handleLaunchDebate,
  };
}
