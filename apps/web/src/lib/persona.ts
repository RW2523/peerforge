/**
 * Display-level persona name mapping.
 *
 * Sessions created before the academic-review rebrand stored legacy role
 * names (e.g. "External Examiner") in the database. New sessions generate
 * the current names, but old data should also render with current wording.
 */
const LEGACY_ROLE_NAMES: Record<string, string> = {
  'external examiner': 'Independent Reviewer',
  'committee examiner': 'Independent Reviewer',
};

export function displayPersona(name?: string | null): string {
  if (!name) return '';
  return LEGACY_ROLE_NAMES[name.trim().toLowerCase()] ?? name;
}
