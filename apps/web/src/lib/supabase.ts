/**
 * Supabase client for authentication
 */
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
// Accept either the modern publishable key (sb_publishable_…) or the legacy
// anon JWT key — supabase-js works with both as the client key.
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  '';

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase credentials not configured. Auth will not work.');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/**
 * Get current session access token.
 *
 * In development mode (NEXT_PUBLIC_AUTH_MODE=development) the backend runs
 * with REQUIRE_AUTH=false and accepts any non-empty bearer value.  We return a
 * static dev-bypass token so every API call and WebSocket connection succeeds
 * without a real Supabase session.
 */
export async function getAccessToken(): Promise<string | null> {
  const authMode = process.env.NEXT_PUBLIC_AUTH_MODE;

  if (authMode === 'development') {
    // Prefer an explicit token from env (useful for integration tests), but
    // fall back to a static dev sentinel — the backend ignores it anyway.
    return process.env.NEXT_PUBLIC_TEST_TOKEN || 'dev-bypass-token';
  }

  // Production: use Supabase session
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token || null;
}

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
