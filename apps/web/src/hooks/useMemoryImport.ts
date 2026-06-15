import { useState } from 'react';
import * as api from '@/lib/api';
import { MemoryImportConfig } from '@/components/setup/MemoryImportStep';

export function useMemoryImport() {
  const [memoryImport, setMemoryImport] = useState<MemoryImportConfig>({
    enabled: false,
    source_debate_ids: [],
    source_type: 'debate_full',
    scope: 'all_agents',
    selected_participant_indices: [],
  });

  const validateMemoryImport = (participants: any[]): string | null => {
    if (!memoryImport.enabled) return null;
    
    if (memoryImport.source_debate_ids.length === 0) {
      return 'Please select at least one past meeting to import or disable Memory Import.';
    }
    
    if (memoryImport.scope === 'specific_agents' && memoryImport.selected_participant_indices.length === 0) {
      return 'Please select at least one participant for Memory Import or choose "All Participants".';
    }
    
    return null;
  };

  const createMemoryGrants = async (
    debateId: string,
    createdParticipantIds: string[]
  ): Promise<boolean> => {
    if (!memoryImport.enabled) return true;
    
    try {
      // Map selected participant indices to actual participant_ids
      let participant_ids: string[] | undefined;
      if (memoryImport.scope === 'specific_agents' && memoryImport.selected_participant_indices.length > 0) {
        participant_ids = memoryImport.selected_participant_indices.map(idx => createdParticipantIds[idx]);
      }
      
      const importRequest: api.MemoryImportRequest = {
        source_debate_ids: memoryImport.source_debate_ids,
        source_type: memoryImport.source_type,
        scope: memoryImport.scope,
        participant_ids: participant_ids,
      };
      
      await api.importMemory(debateId, importRequest);
      return true;
    } catch (importErr: any) {
      const retry = confirm(
        `Debate created but memory import failed: ${importErr.message}\n\nContinue to debate without imported context?`
      );
      return retry;
    }
  };

  return {
    memoryImport,
    setMemoryImport,
    validateMemoryImport,
    createMemoryGrants,
  };
}
