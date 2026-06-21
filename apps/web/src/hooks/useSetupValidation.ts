/**
 * Setup wizard validation — thin hook over the shared validation module
 * (src/lib/setupValidation.ts) so navigation, material cards, and the
 * request preview all agree on what is valid.
 */

import { canAdvance, type SetupState } from '@/lib/setupValidation';

export function useSetupValidation() {
  const canGoNext = (step: number, state: SetupState): boolean => canAdvance(step, state);
  return { canGoNext };
}
