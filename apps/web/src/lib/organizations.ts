/**
 * Organization, course, invitation and seat calls.
 *
 * Kept out of lib/api.ts, which is already 2,200 lines and carries seven
 * "extract me" markers of its own.
 */
import { getAccessToken } from './supabase';
import { getActiveWorkspaceId } from './workspace';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type OrgRole = 'org_admin' | 'professor' | 'ta' | 'student';

export interface Organization {
  org_id: string;
  org_role: OrgRole;
  name: string | null;
  slug: string | null;
}

export interface OrgMember {
  user_id: string;
  role: OrgRole;
  email: string | null;
  display_name: string | null;
  joined_at: string;
}

export interface Course {
  workspace_id: string;
  name: string;
  slug: string;
  description: string | null;
  created_at: string;
}

export interface Invitation {
  invite_id: string;
  email: string;
  role: OrgRole;
  workspace_id: string | null;
  state: 'pending' | 'accepted' | 'expired' | 'revoked';
  expires_at: string;
  created_at: string;
}

export interface Seats {
  org_id: string;
  plan: string;
  seats_purchased: number;
  seats_used: number;
  seats_available: number | null;
  period_end: string | null;
}

export interface CreatedInvitation {
  invite_id: string;
  email: string;
  role: OrgRole;
  token: string;
  invite_url: string;
  expires_at: string;
  email_delivered: boolean;
  delivery: { delivered: boolean; transport: string; detail: string };
}

async function headers(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) h['Authorization'] = `Bearer ${token}`;
  const ws = getActiveWorkspaceId();
  if (ws) h['X-Workspace-Id'] = ws;
  return h;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: await headers() });

  if (!response.ok) {
    // A non-JSON body (a proxy's HTML error page) would otherwise throw a
    // confusing SyntaxError instead of the real status.
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      /* keep the status-based message */
    }
    throw new Error(detail);
  }

  return response.json();
}

export const listMyOrganizations = () =>
  request<{ organizations: Organization[] }>('/me/organizations');

export const createOrganization = (name: string) =>
  request<{ org_id: string; name: string; slug: string; your_role: OrgRole }>(
    '/organizations',
    { method: 'POST', body: JSON.stringify({ name }) }
  );

export const listMembers = (orgId: string) =>
  request<{ members: OrgMember[]; count: number }>(`/organizations/${orgId}/members`);

export const updateMemberRole = (orgId: string, userId: string, role: OrgRole) =>
  request<{ role: OrgRole }>(`/organizations/${orgId}/members/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  });

export const removeMember = (orgId: string, userId: string) =>
  request<{ removed: boolean }>(`/organizations/${orgId}/members/${userId}`, {
    method: 'DELETE',
  });

export const listCourses = (orgId: string) =>
  request<{ courses: Course[] }>(`/organizations/${orgId}/courses`);

export const createCourse = (orgId: string, name: string, description?: string) =>
  request<Course & { your_role: string }>(`/organizations/${orgId}/courses`, {
    method: 'POST',
    body: JSON.stringify({ name, description: description || null }),
  });

export const listInvitations = (orgId: string) =>
  request<{ invitations: Invitation[] }>(`/organizations/${orgId}/invitations`);

export const createInvitation = (
  orgId: string,
  email: string,
  role: OrgRole,
  workspaceId?: string | null
) =>
  request<CreatedInvitation>(`/organizations/${orgId}/invitations`, {
    method: 'POST',
    body: JSON.stringify({ email, role, workspace_id: workspaceId || null }),
  });

export const revokeInvitation = (orgId: string, inviteId: string) =>
  request<{ revoked: boolean }>(`/organizations/${orgId}/invitations/${inviteId}`, {
    method: 'DELETE',
  });

export const acceptInvitation = (token: string) =>
  request<{ org_id: string; workspace_id: string | null; role: OrgRole; accepted: boolean }>(
    `/invitations/${token}/accept`,
    { method: 'POST' }
  );

export const getSeats = (orgId: string) =>
  request<Seats>(`/organizations/${orgId}/seats`);

export const updateSeats = (orgId: string, seatsPurchased: number, plan?: string) =>
  request<Seats>(`/organizations/${orgId}/seats`, {
    method: 'PUT',
    body: JSON.stringify({ seats_purchased: seatsPurchased, plan: plan || null }),
  });

// ── Conversational setup ────────────────────────────────────────────────────

export interface PanelProposalMember {
  name: string;
  role: string;
  focus?: string;
}

export interface SetupProposal {
  title: string;
  problem_statement: string;
  panel: PanelProposalMember[];
  rounds: number;
}

export interface ConverseResult {
  reply: string;
  ready: boolean;
  proposal: SetupProposal | null;
  grounded: boolean;
  passages_used: number;
}

export const converseSetup = async (
  debateId: string,
  message: string,
  history: { role: string; content: string }[],
  openrouterKey: string,
  modelId?: string
): Promise<ConverseResult> => {
  const base = await headers();
  const response = await fetch(`${API_URL}/debates/${debateId}/setup/converse`, {
    method: 'POST',
    headers: { ...base, 'X-OpenRouter-Key': openrouterKey },
    body: JSON.stringify({ message, history, model_id: modelId || null }),
  });
  if (!response.ok) {
    let detail = `Setup request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      /* keep the status-based message */
    }
    throw new Error(detail);
  }
  return response.json();
};

export const applySetup = (debateId: string, proposal: SetupProposal, modelId?: string) =>
  request<{ debate_id: string; participant_ids: string[]; ready_to_start: boolean }>(
    `/debates/${debateId}/setup/apply`,
    { method: 'POST', body: JSON.stringify({ ...proposal, model_id: modelId || null }) }
  );

// ── Cohort and bulk enrolment ───────────────────────────────────────────────

export interface CohortPerson {
  user_id: string | null;
  role: OrgRole;
  email: string | null;
  display_name: string | null;
  sessions: number;
  sessions_completed: number;
  last_activity: string | null;
  latest_score: number | null;
  score_delta: number | null;
  not_started: boolean;
  invite_state?: 'pending' | 'expired';
}

export interface Cohort {
  org_id: string;
  workspace_id: string | null;
  people: CohortPerson[];
  summary: {
    members: number;
    invited_not_joined: number;
    students: number;
    students_not_started: number;
    sessions_total: number;
  };
}

export interface BulkInviteResult {
  submitted: number;
  counts: Record<string, number>;
  emails_delivered: number;
  results: { email: string; state: string; invite_url?: string; detail?: string | null }[];
}

export const getCohort = (orgId: string, workspaceId?: string | null) =>
  request<Cohort>(
    `/organizations/${orgId}/cohort${workspaceId ? `?workspace_id=${workspaceId}` : ''}`
  );

export const inviteBulk = (
  orgId: string,
  emails: string,
  role: OrgRole,
  workspaceId?: string | null
) =>
  request<BulkInviteResult>(`/organizations/${orgId}/invitations/bulk`, {
    method: 'POST',
    body: JSON.stringify({ emails, role, workspace_id: workspaceId || null }),
  });
