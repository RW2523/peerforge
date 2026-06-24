import {
  SETUP_LIMITS,
  type SessionLengthMode,
  validateRounds,
  validateTimebox,
} from '@/lib/setupValidation';

export const STEP1_DRAFT_STORAGE_KEY = 'peerforge_review_setup_step1_draft';

export interface Step1Draft {
  version: 1;
  title: string;
  problemStatement: string;
  keyPoints: string[];
  agenda: string[];
  desiredOutcomes: string[];
  yoloMode: boolean;
  autoTurnDelay: number;
  sessionLengthMode: SessionLengthMode;
  timeboxMinutes?: number;
  maxRounds?: number;
  savedAt: string;
}

export interface Step1DraftState {
  title: string;
  problemStatement: string;
  keyPoints: string[];
  agenda: string[];
  desiredOutcomes: string[];
  yoloMode: boolean;
  autoTurnDelay: number;
  sessionLengthMode: SessionLengthMode;
  timeboxMinutes?: number;
  maxRounds?: number;
}

export function getDefaultStep1State(): Step1DraftState {
  return {
    title: '',
    problemStatement: '',
    keyPoints: [],
    agenda: [],
    desiredOutcomes: [],
    yoloMode: false,
    autoTurnDelay: 10,
    sessionLengthMode: 'time',
    timeboxMinutes: 30,
    maxRounds: undefined,
  };
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function sanitizeStringArray(value: unknown): string[] {
  if (!isStringArray(value)) return [];
  return value
    .map((item) => item.trim())
    .filter((item) => item.length > 0 && item.length <= SETUP_LIMITS.ITEM_MAX);
}

function sanitizeOptionalInt(
  value: unknown,
  min: number,
  max: number
): number | undefined {
  if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isInteger(value)) {
    return undefined;
  }
  if (value < min || value > max) return undefined;
  return value;
}

export function parseStep1Draft(raw: string): Step1Draft | null {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return null;

    const data = parsed as Partial<Step1Draft>;
    if (data.version !== 1) return null;
    if (typeof data.title !== 'string') return null;
    if (typeof data.problemStatement !== 'string') return null;
    if (typeof data.yoloMode !== 'boolean') return null;
    if (typeof data.autoTurnDelay !== 'number' || !Number.isFinite(data.autoTurnDelay)) {
      return null;
    }
    if (data.sessionLengthMode !== 'rounds' && data.sessionLengthMode !== 'time') {
      return null;
    }

    const autoTurnDelay = Math.min(60, Math.max(5, Math.round(data.autoTurnDelay)));
    const timeboxMinutes = sanitizeOptionalInt(
      data.timeboxMinutes,
      SETUP_LIMITS.TIMEBOX_MIN,
      SETUP_LIMITS.TIMEBOX_MAX
    );
    const maxRounds = sanitizeOptionalInt(
      data.maxRounds,
      SETUP_LIMITS.ROUNDS_MIN,
      SETUP_LIMITS.ROUNDS_MAX
    );

    const sessionLengthMode = data.sessionLengthMode;
    const resolvedMaxRounds =
      sessionLengthMode === 'rounds'
        ? maxRounds ?? SETUP_LIMITS.ROUNDS_MIN
        : maxRounds;
    const resolvedTimebox =
      sessionLengthMode === 'time'
        ? timeboxMinutes ?? 30
        : timeboxMinutes;

    if (sessionLengthMode === 'rounds' && validateRounds(resolvedMaxRounds)) {
      return null;
    }
    if (sessionLengthMode === 'time' && validateTimebox(resolvedTimebox)) {
      return null;
    }

    return {
      version: 1,
      title: data.title,
      problemStatement: data.problemStatement,
      keyPoints: sanitizeStringArray(data.keyPoints),
      agenda: sanitizeStringArray(data.agenda),
      desiredOutcomes: sanitizeStringArray(data.desiredOutcomes),
      yoloMode: data.yoloMode,
      autoTurnDelay,
      sessionLengthMode,
      timeboxMinutes: resolvedTimebox,
      maxRounds: resolvedMaxRounds,
      savedAt: typeof data.savedAt === 'string' ? data.savedAt : new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

export function loadStep1Draft(): Step1Draft | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(STEP1_DRAFT_STORAGE_KEY);
  if (!raw) return null;
  const draft = parseStep1Draft(raw);
  if (!draft) {
    localStorage.removeItem(STEP1_DRAFT_STORAGE_KEY);
  }
  return draft;
}

export function saveStep1Draft(state: Step1DraftState): void {
  if (typeof window === 'undefined') return;

  const draft: Step1Draft = {
    version: 1,
    title: state.title,
    problemStatement: state.problemStatement,
    keyPoints: state.keyPoints,
    agenda: state.agenda,
    desiredOutcomes: state.desiredOutcomes,
    yoloMode: state.yoloMode,
    autoTurnDelay: state.autoTurnDelay,
    sessionLengthMode: state.sessionLengthMode,
    timeboxMinutes: state.timeboxMinutes,
    maxRounds: state.maxRounds,
    savedAt: new Date().toISOString(),
  };

  localStorage.setItem(STEP1_DRAFT_STORAGE_KEY, JSON.stringify(draft));
}

export function clearStep1DraftStorage(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(STEP1_DRAFT_STORAGE_KEY);
}

export function step1DraftToState(draft: Step1Draft): Step1DraftState {
  return {
    title: draft.title,
    problemStatement: draft.problemStatement,
    keyPoints: draft.keyPoints,
    agenda: draft.agenda,
    desiredOutcomes: draft.desiredOutcomes,
    yoloMode: draft.yoloMode,
    autoTurnDelay: draft.autoTurnDelay,
    sessionLengthMode: draft.sessionLengthMode,
    timeboxMinutes: draft.timeboxMinutes,
    maxRounds: draft.maxRounds,
  };
}
