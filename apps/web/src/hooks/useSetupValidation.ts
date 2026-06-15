/**
 * Setup wizard validation helpers
 */

import * as api from '@/lib/api';

export function useSetupValidation() {
  const canGoNext = (
    step: number,
    title: string,
    problemStatement: string,
    participants: api.SetupParticipant[]
  ): boolean => {
    if (step === 1) return Boolean(title.trim() && problemStatement.trim());
    if (step === 3) return participants.length > 0;
    if (step === 4) return true; // Memory import is optional
    if (step === 5) return false; // Preflight step: no next
    return true;
  };

  return { canGoNext };
}
