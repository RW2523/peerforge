import { useCallback, useEffect, useRef, useState } from 'react';
import {
  clearStep1DraftStorage,
  getDefaultStep1State,
  saveStep1Draft,
  type Step1DraftState,
} from '@/lib/step1Draft';

const SAVE_DEBOUNCE_MS = 500;

export function useStep1Draft(state: Step1DraftState) {
  const [draftSaved, setDraftSaved] = useState(false);
  const skipSaveRef = useRef(true);

  useEffect(() => {
    if (skipSaveRef.current) {
      skipSaveRef.current = false;
      return;
    }

    const timer = window.setTimeout(() => {
      saveStep1Draft(state);
      setDraftSaved(true);
    }, SAVE_DEBOUNCE_MS);

    return () => window.clearTimeout(timer);
  }, [state]);

  const suppressNextSave = useCallback(() => {
    skipSaveRef.current = true;
  }, []);

  const clearDraft = useCallback(() => {
    clearStep1DraftStorage();
    skipSaveRef.current = true;
    setDraftSaved(false);
    return getDefaultStep1State();
  }, []);

  return {
    draftSaved,
    clearDraft,
    suppressNextSave,
  };
}
