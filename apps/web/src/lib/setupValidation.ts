/**
 * Shared setup-wizard validation.
 *
 * ONE source of truth used by step navigation, material cards, the request
 * preview, and pre-send filtering — so the UI and the preparation flow can
 * never disagree about what counts as valid (per the bug report's guidance).
 */
import * as api from './api';

export const SETUP_LIMITS = {
  TITLE_MIN: 5,
  ABSTRACT_MIN: 50,
  ITEM_MAX: 200, // agenda / objective item max length
  TEXT_BODY_MIN: 20, // meaningful text-material body
  TIMEBOX_MIN: 1,
  TIMEBOX_MAX: 120,
  ROUNDS_MIN: 1,
  ROUNDS_MAX: 20,
  PANEL_MIN: 2,
  PANEL_MAX: 8,
} as const;

// ── URLs ─────────────────────────────────────────────────────────────────────

export function isValidUrl(url: string): boolean {
  const u = (url || '').trim();
  if (!u) return false;
  try {
    const parsed = new URL(u);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
    // Require a real host: a dotted domain (example.com) or localhost — rejects
    // bare tokens like "abc" that URL() would otherwise accept as a hostname.
    const host = parsed.hostname.toLowerCase();
    return host === 'localhost' || /\.[a-z]{2,}$/.test(host);
  } catch {
    return false;
  }
}

/** Prepend https:// if missing, lowercase host, drop a bare trailing slash. */
export function normalizeUrl(url: string): string {
  let u = (url || '').trim();
  if (!u) return u;
  if (!/^[a-z]+:\/\//i.test(u)) u = 'https://' + u;
  try {
    const parsed = new URL(u);
    parsed.hostname = parsed.hostname.toLowerCase();
    let s = parsed.toString();
    if (parsed.pathname === '/' && !parsed.search && !parsed.hash && s.endsWith('/')) {
      s = s.slice(0, -1);
    }
    return s;
  } catch {
    return u;
  }
}

// ── Materials ────────────────────────────────────────────────────────────────

/** A single material is valid in isolation (no cross-item dedupe here). */
export function isValidMaterial(m: api.SetupMaterial): boolean {
  const body = (m.body_text || '').trim();
  const url = (m.url || '').trim();
  if (m.kind === 'text') return body.length >= SETUP_LIMITS.TEXT_BODY_MIN; // title optional, body required
  if (m.kind === 'link' || m.kind === 'file_placeholder') return isValidUrl(url);
  return false;
}

export interface MaterialIssue {
  index: number;
  issue: string;
}

/**
 * Cross-item validation: per-card validity AND duplicate detection.
 * Returns one issue per problematic card (empty array = all good).
 */
export function validateMaterials(materials: api.SetupMaterial[]): MaterialIssue[] {
  const issues: MaterialIssue[] = [];
  const seenText = new Map<string, number>();
  const seenLink = new Map<string, number>();

  materials.forEach((m, index) => {
    if (m.kind === 'text') {
      const body = (m.body_text || '').trim();
      if (body.length === 0) {
        issues.push({ index, issue: 'Add content for this text material, or remove it.' });
        return;
      }
      if (body.length < SETUP_LIMITS.TEXT_BODY_MIN) {
        issues.push({ index, issue: `Text material needs at least ${SETUP_LIMITS.TEXT_BODY_MIN} characters.` });
        return;
      }
      const norm = body.toLowerCase().replace(/\s+/g, ' ');
      if (seenText.has(norm)) {
        issues.push({ index, issue: 'Duplicate text material — already added.' });
        return;
      }
      seenText.set(norm, index);
    } else if (m.kind === 'link' || m.kind === 'file_placeholder') {
      const url = (m.url || '').trim();
      if (!url) {
        issues.push({ index, issue: 'Add a URL for this link, or remove it.' });
        return;
      }
      if (!isValidUrl(normalizeUrl(url))) {
        issues.push({ index, issue: 'Enter a valid URL, e.g. https://example.com' });
        return;
      }
      const norm = normalizeUrl(url).toLowerCase();
      if (seenLink.has(norm)) {
        issues.push({ index, issue: 'Duplicate link — already added.' });
        return;
      }
      seenLink.set(norm, index);
    }
  });

  return issues;
}

// ── Step 1 numeric fields ────────────────────────────────────────────────────

export function validateTimebox(minutes: number | undefined): string | null {
  if (minutes === undefined || minutes === null || Number.isNaN(minutes)) return 'Enter a session length.';
  if (!Number.isInteger(minutes)) return 'Session length must be a whole number of minutes.';
  if (minutes < SETUP_LIMITS.TIMEBOX_MIN || minutes > SETUP_LIMITS.TIMEBOX_MAX) {
    return `Session length must be between ${SETUP_LIMITS.TIMEBOX_MIN} and ${SETUP_LIMITS.TIMEBOX_MAX} minutes.`;
  }
  return null;
}

export function validateRounds(rounds: number | undefined): string | null {
  if (rounds === undefined || rounds === null || Number.isNaN(rounds)) return 'Enter the number of rounds.';
  if (!Number.isInteger(rounds)) return 'Rounds must be a whole number.';
  if (rounds < SETUP_LIMITS.ROUNDS_MIN || rounds > SETUP_LIMITS.ROUNDS_MAX) {
    return `Number of rounds must be between ${SETUP_LIMITS.ROUNDS_MIN} and ${SETUP_LIMITS.ROUNDS_MAX}.`;
  }
  return null;
}

/** Validate a single agenda/objective list item (add or inline edit). */
export function validateListItem(
  value: string,
  items: string[],
  editingIndex: number | null
): string | null {
  const trimmed = value.trim();
  if (!trimmed) return 'Item cannot be empty.';
  if (trimmed.length > SETUP_LIMITS.ITEM_MAX) {
    return `Keep items under ${SETUP_LIMITS.ITEM_MAX} characters.`;
  }
  const duplicate = items.some(
    (item, index) =>
      index !== editingIndex && item.trim().toLowerCase() === trimmed.toLowerCase()
  );
  if (duplicate) return 'This item is already added.';
  return null;
}

// ── Step-level navigation gate ───────────────────────────────────────────────

export type SessionLengthMode = 'rounds' | 'time';

export interface SetupState {
  title: string;
  problemStatement: string;
  participants: api.SetupParticipant[];
  materials: api.SetupMaterial[];
  timeboxMinutes?: number;
  maxRounds?: number;
  sessionLengthMode?: SessionLengthMode;
}

/** Whether the wizard may advance from `step`. */
export function canAdvance(step: number, s: SetupState): boolean {
  if (step === 1) {
    if (s.title.trim().length < SETUP_LIMITS.TITLE_MIN) return false;
    if (s.problemStatement.trim().length < SETUP_LIMITS.ABSTRACT_MIN) return false;
    const sessionMode = s.sessionLengthMode ?? 'time';
    if (sessionMode === 'rounds') {
      if (validateRounds(s.maxRounds)) return false;
    } else if (validateTimebox(s.timeboxMinutes)) {
      return false;
    }
    return true;
  }
  if (step === 2) {
    // Materials are optional, but any card present must be valid (no duplicates,
    // no empty/partial cards). Zero materials is allowed (warning shown in UI).
    return validateMaterials(s.materials).length === 0;
  }
  if (step === 3) return s.participants.length >= SETUP_LIMITS.PANEL_MIN;
  if (step === 4) return true; // Memory import optional
  if (step === 5) return true; // Literature (optional)
  if (step === 6) return false; // Prepare & Launch: launched via canEnterRoom, not Next
  return true;
}
