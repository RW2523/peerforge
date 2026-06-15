/**
 * Shared API client utilities
 */
import { getAccessToken } from '../supabase';

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function getAuthHeaders(): Promise<HeadersInit> {
  const token = await getAccessToken();
  
  if (token) {
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }
  
  // No token available
  return {
    'Content-Type': 'application/json',
  };
}
