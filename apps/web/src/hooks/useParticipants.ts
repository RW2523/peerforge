/**
 * Participant management hook for setup wizard
 */

import { useState, useCallback } from 'react';
import * as api from '@/lib/api';

export function useParticipants() {
  const [participants, setParticipants] = useState<api.SetupParticipant[]>([]);

  const handleAddFromTemplate = useCallback((template: api.AgentTemplate) => {
    setParticipants(prev => {
      if (prev.length >= 8) {
        alert('Maximum 8 participants allowed');
        return prev;
      }
      return [
        ...prev,
        {
          name: template.label,
          role_description: template.role_title,
          system_prompt: template.system_prompt,
          model_id: template.model_id,
          model_config: template.model_config,
        },
      ];
    });
  }, []);

  const handleAddExisting = useCallback((agent: api.Agent) => {
    setParticipants(prev => {
      if (prev.length >= 8) {
        alert('Maximum 8 participants allowed');
        return prev;
      }
      return [...prev, { 
        agent_id: agent.agent_id,
        name: agent.name,
        role_description: agent.role_description,
        system_prompt: agent.system_prompt,
        model_id: agent.model_id,
        model_config: agent.model_config,
      }];
    });
  }, []);

  const handleUpdate = useCallback((idx: number, updates: Partial<api.SetupParticipant>) => {
    setParticipants(prev => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], ...updates };
      return updated;
    });
  }, []);

  const handleRemove = useCallback((idx: number) => {
    setParticipants(prev => prev.filter((_, i) => i !== idx));
  }, []);

  const handleReorder = useCallback((fromIdx: number, toIdx: number) => {
    setParticipants(prev => {
      const updated = [...prev];
      const [movedItem] = updated.splice(fromIdx, 1);
      updated.splice(toIdx, 0, movedItem);
      return updated;
    });
  }, []);

  return {
    participants,
    setParticipants,
    handleAddFromTemplate,
    handleAddExisting,
    handleUpdate,
    handleRemove,
    handleReorder,
  };
}
