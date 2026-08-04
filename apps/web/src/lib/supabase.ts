/**
 * Supabase client for authentication
 *
 * Three modes, via NEXT_PUBLIC_AUTH_MODE:
 *
 *   'disabled'    — this deployment has no sign-in at all, on purpose. There
 *                   is no login page and everyone is the same user. Honoured
 *                   in production builds, because it is a deliberate choice
 *                   rather than a leftover.
 *   'development' — local convenience bypass. Refused in a production build,
 *                   so a stray env var cannot silently un-gate a real deploy.
 *   anything else — real Supabase sessions.
 *
 * The distinction matters: 'disabled' is someone saying "open by design",
 * 'development' left on in production is someone making a mistake. Collapsing
 * them into one flag means you cannot tell those apart, and the safe handling
 * of each is opposite.
 */
import { createClient } from '@supabase/supabase-js';

/** True when this build intentionally ships without any sign-in. */
export const AUTH_DISABLED = process.env.NEXT_PUBLIC_AUTH_MODE === 'disabled';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
// Accept either the modern publishable key (sb_publishable_…) or the legacy
// anon JWT key — supabase-js works with both as the client key.
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  '';

if (!AUTH_DISABLED && (!supabaseUrl || !supabaseAnonKey)) {
  // Silent when auth is off by design — there is nothing to configure and the
  // warning only trained people to ignore the console.
  console.warn('Supabase credentials not configured. Auth will not work.');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/**
 * Get current session access token.
 *
 * With auth disabled there is no session to get: the backend runs with
 * REQUIRE_AUTH=false and ignores the value, so a static sentinel keeps every
 * API call and WebSocket connection working without a sign-in that does not
 * exist.
 */
export async function getAccessToken(): Promise<string | null> {
  const authMode = process.env.NEXT_PUBLIC_AUTH_MODE;

  if (AUTH_DISABLED) {
    return 'anonymous';
  }

  if (authMode === 'development') {
    // The bypass is refused in a production build. Otherwise a stray
    // NEXT_PUBLIC_AUTH_MODE=development in a deploy environment would make
    // every visitor "authenticate" as nobody — failing open, silently.
    // Falling through to the real session instead fails closed: no session
    // means no token, and the API answers 401.
    if (process.env.NODE_ENV === 'production') {
      console.error(
        'NEXT_PUBLIC_AUTH_MODE=development is set in a production build. ' +
          'The dev bypass is ignored; sign-in is required.'
      );
    } else {
      // Prefer an explicit token from env (useful for integration tests), but
      // fall back to a static dev sentinel — the backend ignores it anyway.
      return process.env.NEXT_PUBLIC_TEST_TOKEN || 'dev-bypass-token';
    }
  }

  // Production: use Supabase session.
  //
  // Never allowed to throw. When the Supabase URL is unreachable — an https
  // page reaching for http://localhost:54321 is blocked outright — this
  // rejects with "Failed to fetch", and because every request awaits this
  // first, that error surfaced as the failure of whatever the user was doing.
  // Uploading a document reported "Failed to fetch" without a single byte
  // having been sent to our own API, which was up and answering.
  try {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || null;
  } catch (err) {
    console.warn('Could not read a Supabase session; continuing without a token', err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Sign-in helpers.
//
// Nothing calls these while NEXT_PUBLIC_AUTH_MODE=disabled — the login page and
// its routes were removed. They are kept deliberately as the seam for turning
// authentication back on: point NEXT_PUBLIC_SUPABASE_URL at a real project,
// drop the 'disabled' mode, and rebuild a login page around them.
// ---------------------------------------------------------------------------

/**
 * Sign in with email and password
 */
export async function signInWithPassword(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });
  
  if (error) throw error;
  return data;
}

/**
 * Sign in with magic link
 */
export async function signInWithMagicLink(email: string) {
  const { data, error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${window.location.origin}/setup`,
    },
  });
  
  if (error) throw error;
  return data;
}

/**
 * Sign out
 */
export async function signOut() {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}

/**
 * Get current user
 */
export async function getCurrentUser() {
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}
