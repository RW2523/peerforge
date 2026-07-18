/**
 * API client for Arinar backend
 */
import { getAccessToken } from './supabase';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Render a FastAPI error `detail` as a readable message.
 * 422 validation errors return an ARRAY of objects — stringifying them naively
 * produces "[object Object]" in alerts.
 */
function formatErrorDetail(detail: unknown, fallback: string): string {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((d: any) => {
      const loc = Array.isArray(d?.loc) ? d.loc.filter((x: any) => x !== 'body').join('.') : '';
      return d?.msg ? (loc ? `${loc}: ${d.msg}` : d.msg) : JSON.stringify(d);
    });
    return messages.join('; ') || fallback;
  }
  return JSON.stringify(detail);
}

async function getAuthHeaders(): Promise<HeadersInit> {
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

// ============================================================================
// DEBATES DOMAIN (lines 24-220)
// TODO: Extract to api/debates.ts
// ============================================================================

export interface DebateResponse {
  debate_id: string;
  workspace_id: string;
  title: string;
  state: string;
  created_at: string;
}

export interface InterventionRequest {
  message: string;
  tagged_agents?: string[];
}

export async function createDebate(workspaceId: string, title: string): Promise<DebateResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ workspace_id: workspaceId, title }),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to create debate: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getDebate(debateId: string): Promise<any> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get debate: ${response.statusText}`);
  }
  
  return response.json();
}

export async function startDebate(debateId: string, openrouterKey?: string | null): Promise<DebateResponse> {
  const headers = await getAuthHeaders();
  if (openrouterKey) {
    (headers as Record<string, string>)['X-OpenRouter-Key'] = openrouterKey;
  }
  const response = await fetch(`${API_URL}/debates/${debateId}/start`, {
    method: 'POST',
    headers,
  });
  
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? response.statusText;
    throw new Error(`Failed to start debate: ${detail}`);
  }
  
  return response.json();
}

export async function pauseDebate(debateId: string): Promise<DebateResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/pause`, {
    method: 'POST',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to pause debate: ${response.statusText}`);
  }
  
  return response.json();
}

export async function resumeDebate(debateId: string): Promise<DebateResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/resume`, {
    method: 'POST',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to resume debate: ${response.statusText}`);
  }
  
  return response.json();
}

export async function extendDebate(
  debateId: string,
  extendRounds?: number,
  extendMinutes?: number
): Promise<{ debate_id: string; policy_config: any; message: string }> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/extend`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({
      extend_rounds: extendRounds,
      extend_minutes: extendMinutes,
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(`Failed to extend debate: ${error.detail || response.statusText}`);
  }
  
  return response.json();
}

export async function endDebate(debateId: string): Promise<DebateResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/end`, {
    method: 'POST',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to end debate: ${response.statusText}`);
  }
  
  return response.json();
}

export async function triggerNextTurn(debateId: string, openrouterKey: string): Promise<any> {
  const headers = await getAuthHeaders() as Record<string, string>;
  headers['X-OpenRouter-Key'] = openrouterKey;
  
  const response = await fetch(`${API_URL}/debates/${debateId}/turn/next`, {
    method: 'POST',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to trigger next turn: ${response.statusText}`);
  }
  
  return response.json();
}

export async function concludeDebate(debateId: string, openrouterKey: string): Promise<any> {
  const headers = await getAuthHeaders() as Record<string, string>;
  headers['X-OpenRouter-Key'] = openrouterKey;
  
  const response = await fetch(`${API_URL}/debates/${debateId}/conclude`, {
    method: 'POST',
    headers,
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(`Failed to conclude debate: ${error.detail || response.statusText}`);
  }
  
  return response.json();
}

export async function intervene(debateId: string, request: InterventionRequest): Promise<any> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/intervene`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to intervene: ${response.statusText}`);
  }
  
  return response.json();
}

export function getStreamUrl(debateId: string, since?: number): string {
  const url = new URL(`${API_URL}/debates/${debateId}/events/stream`);
  if (since !== undefined) {
    url.searchParams.set('since', since.toString());
  }
  return url.toString();
}

// M3 Summary endpoints
export interface SummarizeRequest {
  openrouter_api_key: string;
  model_id?: string;
}

export interface ActionItem {
  description: string;
  owner: string;
  priority: 'high' | 'medium' | 'low';
}

export interface SummaryResponse {
  output_id: string;
  debate_id: string;
  summary: string;
  minutes: string;
  action_items: ActionItem[];
  generated_at: string;
  model_used?: string;
}

export async function generateSummary(
  debateId: string,
  request: SummarizeRequest,
  openrouterKey: string
): Promise<SummaryResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/summarize`, {
    method: 'POST',
    headers: {
      ...headers,
      'X-OpenRouter-Key': openrouterKey,
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to generate summary: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getSummary(debateId: string): Promise<SummaryResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/summary`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Summary not generated yet');
    }
    throw new Error(`Failed to get summary: ${response.statusText}`);
  }
  
  return response.json();
}

// M4 Meeting Setup endpoints
// ============================================================================
// AGENTS & SETUP DOMAIN (lines 224-320)
// TODO: Extract to api/agents.ts and api/setup.ts
// ============================================================================

export interface AgentTemplate {
  template_id: string;
  label: string;
  role_title: string;
  category: string;  // e.g. "Product", "Engineering", "Design", "Business", "Wildcards"
  character?: string;  // e.g. "Visionary - Jobs-inspired", "Pragmatic - Data-driven"
  system_prompt: string;
  model_id: string;
  model_config: Record<string, any>;
}

export interface Agent {
  agent_id: string;
  workspace_id: string;
  name: string;
  role_description?: string;
  system_prompt: string;
  model_id: string;
  model_config: Record<string, any>;
  created_at: string;
}

export interface SetupParticipant {
  agent_id?: string;
  name?: string;
  role_description?: string;
  system_prompt?: string;
  model_id?: string;
  model_config?: Record<string, any>;
}

export interface SetupMaterial {
  kind: 'text' | 'link' | 'file_placeholder';
  title?: string;
  body_text?: string;
  url?: string;
}

export interface DebateSetupRequest {
  workspace_id: string;
  title: string;
  problem_statement: string;
  agenda?: string[];
  desired_outcomes?: string[];
  timebox_minutes?: number;
  max_rounds?: number;
  enable_host?: boolean;
  host_model_id?: string;
  participants: SetupParticipant[];
  materials?: SetupMaterial[];
  reasoning_mode?: ReasoningMode;
}

export interface DebateSetupResponse {
  debate_id: string;
  participant_ids: string[];
  material_ids: string[];
}

export async function listAgentTemplates(): Promise<AgentTemplate[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/agent-templates`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to fetch templates: ${response.statusText}`);
  }
  
  return response.json();
}

export async function listAgents(workspaceId: string): Promise<Agent[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/agents?workspace_id=${workspaceId}`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to fetch agents: ${response.statusText}`);
  }
  
  return response.json();
}

export async function setupDebate(request: DebateSetupRequest): Promise<DebateSetupResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/setup`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(formatErrorDetail(error?.detail, `Failed to setup debate: ${response.statusText}`));
  }
  
  return response.json();
}

// OpenRouter account info
// ============================================================================
// OPENROUTER DOMAIN (lines 322-405)
// TODO: Extract to api/openrouter.ts
// ============================================================================

export interface OpenRouterAccountResponse {
  key?: {
    label?: string;
    usage?: number;
    limit?: number | null;
    rate_limit?: any;
    is_free_tier?: boolean;
    is_valid?: boolean;
    validated_via?: string;
  };
  credits?: {
    total_credits?: number | null;
    total_usage?: number | null;
    balance?: number | null;
  } | null;
  models_available?: number;
  has_management_key?: boolean;
  note?: string | null;
}

export interface OpenRouterModel {
  id: string;
  name: string;
  context_length?: number;
  pricing?: {
    prompt: string;
    completion: string;
  };
}

export interface OpenRouterModelListResponse {
  models: OpenRouterModel[];
}

export async function listOpenRouterModels(openrouterKey: string): Promise<OpenRouterModelListResponse> {
  const response = await fetch(`${API_URL}/openrouter/models`, {
    method: 'GET',
    headers: {
      'X-OpenRouter-Key': openrouterKey,
    },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to fetch models: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getOpenRouterAccount(
  openrouterKey: string,
  managementKey?: string | null
): Promise<OpenRouterAccountResponse> {
  const headers: Record<string, string> = {
    'X-OpenRouter-Key': openrouterKey,
  };
  
  if (managementKey) {
    headers['X-OpenRouter-Management-Key'] = managementKey;
  }
  
  const response = await fetch(`${API_URL}/openrouter/account`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? response.statusText;
    if (response.status === 401) {
      throw new Error(`Invalid API key — ${detail}`);
    }
    throw new Error(`Failed to validate key: ${detail}`);
  }
  
  return response.json();
}

// Debates list
export interface DebateListItem {
  debate_id: string;
  workspace_id: string;
  title: string;
  state: string;
  created_at: string;
  updated_at?: string;
  started_at?: string;
  ended_at?: string;
  participant_count?: number;
  message_count?: number;
}

export interface DebateListResponse {
  items: DebateListItem[];
  next_cursor?: string | null;
}

export async function listDebates(
  workspaceId: string,
  limit?: number,
  cursor?: string
): Promise<DebateListResponse> {
  const headers = await getAuthHeaders();
  const params = new URLSearchParams({ workspace_id: workspaceId });
  if (limit) params.append('limit', limit.toString());
  if (cursor) params.append('cursor', cursor);
  
  const response = await fetch(`${API_URL}/debates?${params}`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? response.statusText;
    throw new Error(`Failed to list debates: ${detail}`);
  }

  return response.json();
}

export async function getDebateEvents(debateId: string): Promise<any[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/events`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get events: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getDebateSummary(debateId: string): Promise<any> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/summary`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    if (response.status === 404) {
      return null; // No summary generated yet
    }
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? response.statusText;
    throw new Error(`Failed to get summary: ${detail}`);
  }

  return response.json();
}

// Materials upload and status
// ============================================================================
// MATERIALS DOMAIN (lines 430-510)  
// TODO: Extract to api/materials.ts
// ============================================================================

export interface MaterialUploadResponse {
  material_ids: string[];
  job_ids: string[];
  total_files: number;
}

export type MaterialCategory = 'main_research' | 'research' | 'transcript' | 'supplementary';

export interface MaterialStatus {
  material_id: string;
  title: string;
  kind: string;
  material_category: MaterialCategory;
  is_primary: boolean;
  file_size_bytes?: number;
  file_mime_type?: string;
  processed_status: string;
  processing_metadata: Record<string, any>;
  created_at: string;
  processing_started_at?: string;
  processing_completed_at?: string;
}

export interface MaterialsStatusResponse {
  debate_id: string;
  total_materials: number;
  status_summary: Record<string, number>;
  materials: MaterialStatus[];
}

export async function uploadMaterials(
  debateId: string,
  files: File[],
  openrouterKey?: string | null,
  category: MaterialCategory = 'supplementary',
  isPrimary: boolean = false
): Promise<MaterialUploadResponse> {
  const token = await getAccessToken();
  const formData = new FormData();

  files.forEach(file => {
    formData.append('files', file);
  });
  formData.append('category', category);
  formData.append('is_primary', String(isPrimary));

  const headers: Record<string, string> = {
    'Authorization': token ? `Bearer ${token}` : '',
  };
  if (openrouterKey) {
    headers['X-OpenRouter-Key'] = openrouterKey;
  }

  const response = await fetch(`${API_URL}/debates/${debateId}/materials/upload`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Failed to upload materials: ${response.statusText}`);
  }

  return response.json();
}

// ============================================================================
// TRANSCRIPT ACTION ITEMS & DECISION DEBATES
// ============================================================================

export interface TranscriptActionItem {
  action_id: string;
  material_id?: string | null;
  description: string;
  owner?: string | null;
  priority: 'low' | 'medium' | 'high';
  status: 'extracted' | 'debating' | 'decided';
  decision_debate_id?: string | null;
  decision?: string | null;
  decision_rationale?: string | null;
  seq_order: number;
}

export interface ActionItemDecision {
  action_id: string;
  status: 'debating' | 'decided';
  decision_debate_id?: string | null;
  decision?: string | null;
  decision_rationale?: string | null;
}

export async function extractActionItems(
  debateId: string,
  materialId: string,
  openrouterKey: string
): Promise<TranscriptActionItem[]> {
  const headers = await getAuthHeaders();
  (headers as Record<string, string>)['X-OpenRouter-Key'] = openrouterKey;
  const response = await fetch(
    `${API_URL}/debates/${debateId}/materials/${materialId}/extract-action-items`,
    { method: 'POST', headers }
  );
  if (!response.ok) {
    throw new Error(`Failed to extract action items: ${await response.text()}`);
  }
  return response.json();
}

export async function listActionItems(debateId: string): Promise<TranscriptActionItem[]> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/action-items`, {
    method: 'GET',
    headers,
  });
  if (!response.ok) throw new Error(`Failed to list action items: ${response.statusText}`);
  return response.json();
}

export async function updateActionItem(
  debateId: string,
  actionId: string,
  update: Partial<Pick<TranscriptActionItem, 'description' | 'owner' | 'priority' | 'status'>>
): Promise<TranscriptActionItem> {
  const headers = await getAuthHeaders();
  (headers as Record<string, string>)['Content-Type'] = 'application/json';
  const response = await fetch(`${API_URL}/debates/${debateId}/action-items/${actionId}`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(update),
  });
  if (!response.ok) throw new Error(`Failed to update action item: ${response.statusText}`);
  return response.json();
}

export async function debateActionItem(
  debateId: string,
  actionId: string,
  openrouterKey: string
): Promise<ActionItemDecision> {
  const headers = await getAuthHeaders();
  (headers as Record<string, string>)['X-OpenRouter-Key'] = openrouterKey;
  const response = await fetch(
    `${API_URL}/debates/${debateId}/action-items/${actionId}/debate`,
    { method: 'POST', headers }
  );
  if (!response.ok) throw new Error(`Failed to start decision debate: ${await response.text()}`);
  return response.json();
}

export async function getActionItemDecision(
  debateId: string,
  actionId: string
): Promise<ActionItemDecision> {
  const headers = await getAuthHeaders();
  const response = await fetch(
    `${API_URL}/debates/${debateId}/action-items/${actionId}/decision`,
    { method: 'GET', headers }
  );
  if (!response.ok) throw new Error(`Failed to get decision: ${response.statusText}`);
  return response.json();
}

export async function triggerEmbeddingGeneration(
  debateId: string,
  openrouterKey: string
): Promise<{ debate_id: string; job_id: string | null; message: string }> {
  const headers = await getAuthHeaders();
  (headers as Record<string, string>)['X-OpenRouter-Key'] = openrouterKey;
  const response = await fetch(`${API_URL}/debates/${debateId}/materials/embed`, {
    method: 'POST',
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to trigger embeddings: ${text}`);
  }
  return response.json();
}

export async function getMaterialsStatus(debateId: string): Promise<MaterialsStatusResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/materials/status`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get materials status: ${response.statusText}`);
  }
  
  return response.json();
}

export async function deleteMaterial(
  debateId: string,
  materialId: string
): Promise<{ material_id: string; deleted: boolean }> {
  const headers = await getAuthHeaders();
  const response = await fetch(
    `${API_URL}/debates/${debateId}/materials/${materialId}`,
    { method: 'DELETE', headers }
  );

  if (!response.ok) {
    throw new Error(`Failed to remove material: ${response.statusText}`);
  }

  return response.json();
}

export async function retryMaterial(debateId: string, materialId: string): Promise<any> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/materials/retry`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ material_id: materialId }),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to retry material: ${response.statusText}`);
  }
  
  return response.json();
}

// Memory Import API

// ============================================================================
// MEMORY DOMAIN (lines 513-670)
// TODO: Extract to api/memory.ts  
// ============================================================================

export interface ImportableDebate {
  debate_id: string;
  title: string;
  state: string;
  created_at: string;
  ended_at?: string | null;
  chunk_count: number;
  material_count: number;
  artifact_count: number;
  participant_count: number;
}

export interface ImportableSourcesResponse {
  workspace_id: string;
  debates: ImportableDebate[];
  total_count: number;
}

export interface MemoryPreviewChunk {
  source_type: string;
  title: string;
  chunk_count: number;
  last_updated: string;
}

export interface MemoryPreviewResponse {
  source_debate_id: string;
  source_title: string;
  total_chunks: number;
  breakdown: MemoryPreviewChunk[];
  date_range: {
    start?: string | null;
    end?: string | null;
  };
}

export interface MemoryImportRequest {
  source_debate_ids: string[];
  source_type?: 'debate_full' | 'materials_only';
  scope?: 'all_agents' | 'specific_agents';
  participant_ids?: string[];
  metadata?: Record<string, any>;
}

export interface MemoryImportResponse {
  debate_id: string;
  grants_created: number;
  grant_ids: string[];
}

export interface MemoryGrant {
  grant_id: string;
  source_debate_id?: string | null;
  source_debate_title?: string | null;
  source_artifact_id?: string | null;
  source_artifact_title?: string | null;
  source_type: string;
  scope: string;
  allowed_participant_ids?: string[] | null;
  granted_by: string;
  granted_at: string;
  expires_at?: string | null;
  metadata: Record<string, any>;
}

export interface MemoryGrantsResponse {
  debate_id: string;
  grants: MemoryGrant[];
  total_count: number;
}

export async function listImportableMemorySources(
  workspaceId: string,
  limit?: number
): Promise<ImportableSourcesResponse> {
  const headers = await getAuthHeaders();
  const params = new URLSearchParams();
  if (limit) params.append('limit', limit.toString());
  
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/memory/importable?${params}`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to list importable sources: ${response.statusText}`);
  }
  
  return response.json();
}

export async function previewMemoryImport(
  debateId: string,
  sourceDebateId: string
): Promise<MemoryPreviewResponse> {
  const headers = await getAuthHeaders();
  const params = new URLSearchParams({ source_debate_id: sourceDebateId });
  
  const response = await fetch(`${API_URL}/debates/${debateId}/memory/preview?${params}`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to preview memory import: ${response.statusText}`);
  }
  
  return response.json();
}

export async function importMemory(
  debateId: string,
  request: MemoryImportRequest
): Promise<MemoryImportResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/memory/import`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to import memory: ${response.statusText} - ${errorText}`);
  }
  
  return response.json();
}

export async function listMemoryGrants(debateId: string): Promise<MemoryGrantsResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/memory/grants`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to list memory grants: ${response.statusText}`);
  }
  
  return response.json();
}

export async function revokeMemoryGrant(debateId: string, grantId: string): Promise<any> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/memory/grants/${grantId}`, {
    method: 'DELETE',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to revoke memory grant: ${response.statusText}`);
  }
  
  return response.json();
}

// Preflight API

// ============================================================================
// PREFLIGHT DOMAIN (lines 672-785)
// TODO: Extract to api/preflight.ts
// ============================================================================

export interface ParticipantRunStatus {
  participant_run_id: string;
  participant_id: string;
  agent_id?: string;
  status: 'queued' | 'running' | 'success' | 'failed' | 'skipped';
  started_at?: string;
  completed_at?: string;
  error?: string;
  skip_reason?: string;
  prep_pack_knowledge_id?: string;
  metadata?: Record<string, any>;
}

export interface PreflightStartResponse {
  run_id: string;
  debate_id: string;
  status: string;
  participant_count: number;
  participant_runs: Array<{
    participant_run_id: string;
    participant_id: string;
    agent_id?: string;
    status: string;
  }>;
}

export interface PreflightStatusResponse {
  run_id: string;
  debate_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
  participant_runs: ParticipantRunStatus[];
}

export interface PreflightActionResponse {
  participant_run_id: string;
  participant_id: string;
  status: string;
  message: string;
}

export async function startPreflight(debateId: string, openrouterKey?: string | null): Promise<PreflightStartResponse> {
  const headers = await getAuthHeaders();
  
  // Add OpenRouter key if provided (for real AI prep generation)
  if (openrouterKey) {
    (headers as Record<string, string>)['X-OpenRouter-Key'] = openrouterKey;
  }
  
  const response = await fetch(`${API_URL}/debates/${debateId}/preflight/start`, {
    method: 'POST',
    headers,
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to start preflight: ${response.statusText} - ${errorText}`);
  }
  
  return response.json();
}

export async function getPreflightStatus(debateId: string): Promise<PreflightStatusResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/preflight/status`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to get preflight status: ${response.statusText} - ${errorText}`);
  }
  
  return response.json();
}

export async function retryPreflightParticipant(
  debateId: string,
  participantId: string
): Promise<PreflightActionResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/preflight/retry`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ participant_id: participantId }),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to retry preflight: ${response.statusText} - ${errorText}`);
  }
  
  return response.json();
}

export async function skipPreflightParticipant(
  debateId: string,
  participantId: string,
  reason: string
): Promise<PreflightActionResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/preflight/skip`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ participant_id: participantId, reason }),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to skip preflight: ${response.statusText} - ${errorText}`);
  }
  
  return response.json();
}

// ============================================================================
// Workspace Settings
// ============================================================================

// ============================================================================
// WORKSPACE SETTINGS DOMAIN (lines 789-835)
// TODO: Extract to api/workspace.ts
// ============================================================================

export interface WorkspaceModelsRequest {
  embeddings_model_id: string;
  ocr_model_id: string;
}

export interface WorkspaceModelsResponse {
  workspace_id: string;
  embeddings_model_id: string;
  ocr_model_id: string;
  updated_at: string;
}

export async function getWorkspaceModels(workspaceId: string): Promise<WorkspaceModelsResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/settings/models`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to get workspace models: ${response.statusText} - ${errorText}`);
  }
  
  return response.json();
}

export async function updateWorkspaceModels(
  workspaceId: string,
  models: WorkspaceModelsRequest
): Promise<WorkspaceModelsResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/settings/models`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(models),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to update workspace models: ${response.statusText} - ${errorText}`);
  }
  
  return response.json();
}

/**
 * Fetch agent knowledge unit (prep pack) with full content and metadata
 */
export async function getAgentKnowledgeUnit(knowledgeId: string) {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/agent-knowledge/${knowledgeId}`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to fetch knowledge unit: ${error}`);
  }
  
  return response.json();
}

// ============================================================================
// AI ASSIST DOMAIN
// ============================================================================

export interface ImproveProblemStatementResponse {
  improved_text: string;
  key_points: string[];
  agenda_items: string[];
  desired_outcomes: string[];
}

export async function improveProblemStatement(
  inputText: string,
  openrouterKey: string
): Promise<ImproveProblemStatementResponse> {
  const response = await fetch(`${API_URL}/ai/improve-problem-statement`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-OpenRouter-Key': openrouterKey,
    },
    body: JSON.stringify({ input_text: inputText }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to improve problem statement');
  }
  
  return response.json();
}

// ============================================================================
// PARTICIPANTS DOMAIN
// ============================================================================

export async function addParticipantsToDebate(
  debateId: string,
  participants: SetupParticipant[]
): Promise<{ participant_ids: string[] }> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/participants`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ participants }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(formatErrorDetail(error?.detail, `Failed to add participants: ${response.statusText}`));
  }

  return response.json();
}

/**
 * Persist inline TEXT/LINK materials to an existing debate and chunk them for
 * grounding. The wizard creates the debate early, so these are sent at finalize.
 */
export async function addInlineMaterials(
  debateId: string,
  materials: SetupMaterial[],
  openrouterKey?: string | null
): Promise<{ debate_id: string; materials_added: number; chunks_created: number }> {
  const headers = (await getAuthHeaders()) as Record<string, string>;
  if (openrouterKey) headers['X-OpenRouter-Key'] = openrouterKey;
  const response = await fetch(`${API_URL}/debates/${debateId}/materials`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ materials }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(formatErrorDetail(error?.detail, `Failed to add materials: ${response.statusText}`));
  }

  return response.json();
}

// ============================================================================
// AUTONOMOUS DEBATE (YOLO MODE)
// ============================================================================

export async function startAutonomousDebate(
  debateId: string,
  autoTurnDelaySeconds: number = 10,
  openrouterKey: string
): Promise<{ status: string; debate_id: string }> {
  const headers: any = await getAuthHeaders();
  headers['X-OpenRouter-Key'] = openrouterKey;
  
  const response = await fetch(`${API_URL}/api/debates/${debateId}/start-autonomous`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ auto_turn_delay_seconds: autoTurnDelaySeconds }),
  });
  
  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText);
    throw new Error(`Failed to start autonomous debate: ${errorText}`);
  }
  
  return response.json();
}

export async function pauseAutonomousDebate(debateId: string): Promise<{ status: string }> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/api/debates/${debateId}/pause-autonomous`, {
    method: 'POST',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to pause autonomous debate: ${response.statusText}`);
  }
  
  return response.json();
}

export async function resumeAutonomousDebate(debateId: string, openrouterKey: string): Promise<{ status: string }> {
  const headers: any = await getAuthHeaders();
  headers['X-OpenRouter-Key'] = openrouterKey;
  
  const response = await fetch(`${API_URL}/api/debates/${debateId}/resume-autonomous`, {
    method: 'POST',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to resume autonomous debate: ${response.statusText}`);
  }
  
  return response.json();
}

export async function deleteDebate(debateId: string): Promise<{ success: boolean }> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}`, {
    method: 'DELETE',
    headers,
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to delete debate: ${errorText}`);
  }
  
  return response.json();
}

export async function getAutonomousStatus(debateId: string): Promise<{
  status: string | null;
  is_running: boolean;
  has_background_task: boolean;
}> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/api/debates/${debateId}/autonomous-status`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get autonomous status: ${response.statusText}`);
  }
  
  return response.json();
}

// ============================================================================
// DOCUMENTS API
// ============================================================================

export async function createDocument(request: any): Promise<any> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/documents`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to create document: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getDocument(documentId: string): Promise<any> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/documents/${documentId}`, {
    method: 'GET',
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get document: ${response.statusText}`);
  }
  
  return response.json();
}

// ============================================================================
// LITERATURE SEARCH (PeerForge)
// ============================================================================

export interface PaperResult {
  title: string;
  authors: string[];
  year: number | null;
  abstract: string;
  url: string;
  doi: string | null;
  venue: string;
  citation_count: number;
  source: string;
}

export interface LiteratureSearchResponse {
  query: string;
  papers: PaperResult[];
  total: number;
  sources_queried: string[];
}

export interface SavedPaper {
  material_id: string;
  title: string;
  source: string;
  url: string;
  doi: string | null;
  year: number | null;
  saved_at: string;
}

export interface SavePapersResponse {
  saved: number;
  material_ids: string[];
}

export async function searchLiterature(
  debateId: string,
  query: string,
  sources?: string[],
  maxPerSource: number = 8,
  maxTotal: number = 25,
): Promise<LiteratureSearchResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/literature/search`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      query,
      sources: sources ?? null,
      max_per_source: maxPerSource,
      max_total: maxTotal,
    }),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => response.statusText);
    throw new Error(`Literature search failed: ${errText}`);
  }

  return response.json();
}

export async function savePapersToContext(
  debateId: string,
  papers: PaperResult[],
  label?: string,
): Promise<SavePapersResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/literature/save`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ papers, label }),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => response.statusText);
    throw new Error(`Failed to save papers: ${errText}`);
  }

  return response.json();
}

export async function listSavedPapers(debateId: string): Promise<{
  papers: SavedPaper[];
  total: number;
}> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/literature`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    throw new Error(`Failed to list saved papers: ${response.statusText}`);
  }

  return response.json();
}

// ---------------------------------------------------------------------------
// Web Search (Tavily)
// ---------------------------------------------------------------------------

export interface WebResult {
  title: string;
  url: string;
  content: string;
  score: number;
  published_date: string | null;
  source_domain: string;
}

export interface WebSearchResponse {
  query: string;
  results: WebResult[];
  total: number;
  search_depth: string;
}

export interface SavedWebResult {
  material_id: string;
  title: string;
  url: string;
  source_domain: string;
  saved_at: string;
}

export async function searchWeb(
  debateId: string,
  query: string,
  options?: {
    maxResults?: number;
    searchDepth?: 'basic' | 'advanced';
    includeDomains?: string[];
    excludeDomains?: string[];
  },
): Promise<WebSearchResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/web/search`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      query,
      max_results: options?.maxResults ?? 10,
      search_depth: options?.searchDepth ?? 'advanced',
      include_domains: options?.includeDomains ?? null,
      exclude_domains: options?.excludeDomains ?? null,
    }),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => response.statusText);
    throw new Error(`Web search failed: ${errText}`);
  }

  return response.json();
}

export async function saveWebResults(
  debateId: string,
  results: WebResult[],
  label?: string,
): Promise<{ saved: number; material_ids: string[] }> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/web/save`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ results, label }),
  });

  if (!response.ok) {
    const errText = await response.text().catch(() => response.statusText);
    throw new Error(`Failed to save web results: ${errText}`);
  }

  return response.json();
}

export async function listSavedWebResults(debateId: string): Promise<{
  results: SavedWebResult[];
  total: number;
}> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/debates/${debateId}/web`, {
    method: 'GET',
    headers,
  });

  if (!response.ok) {
    throw new Error(`Failed to list saved web results: ${response.statusText}`);
  }

  return response.json();
}

// ============================================================================
// ACADEMIC REVIEW PLATFORM API
// ============================================================================

export type ReasoningMode = 'light' | 'medium' | 'heavy';

export interface ReasoningModeInfo {
  label: string;
  description: string;
  default_model: string;
  summary_model: string;
  cost_hint: string;
}

export interface SuggestedPersona {
  name: string;
  role: string;
  expertise: string;
  focus_area: string;
  system_prompt: string;
  model_id: string;
}

export interface ResearchProfile {
  profile_id: string;
  debate_id: string;
  status: 'pending' | 'running' | 'complete' | 'failed';
  research_problem?: string;
  research_gap?: string;
  research_questions?: string[];
  main_claim?: string;
  methodology?: string;
  dataset_details?: string;
  contribution?: string;
  evidence_summary?: string;
  limitations?: string;
  hypothesis?: string;
  key_claims?: string[];
  results?: string;
  future_work?: string;
  contradictions?: { statement_a: string; statement_b: string; explanation: string }[];
  weak_areas?: { area: string; reason: string }[];
  possible_questions?: string[];
  error_message?: string;
  model_used?: string;
  chunk_count?: number;
}

export interface DefenseQuestion {
  question_id: string;
  debate_id: string;
  question_text: string;
  category: string;
  difficulty: 'easy' | 'medium' | 'hard';
  persona: string;
  expected_answer?: string;
  follow_up_rule?: string;
  follow_up_q?: string;
  source_excerpt?: string;
  asked: boolean;
  seq_order: number;
}

export interface AnswerEvaluation {
  answer_id: string;
  question_id: string;
  overall_score: number;
  score_relevance: number;
  score_evidence: number;
  score_clarity: number;
  score_completeness: number;
  score_methodology: number;
  score_critical_thinking: number;
  strength: string;
  weakness: string;
  missing_evidence: string;
  suggested_improvement: string;
  follow_up_needed: boolean;
  follow_up_question?: string;
}

export interface ReadinessReport {
  report_id: string;
  debate_id: string;
  status: string;
  overall_readiness?: number;
  research_clarity?: number;
  methodology_score?: number;
  evidence_score?: number;
  critical_thinking?: number;
  communication?: number;
  strong_answers?: any[];
  weak_answers?: any[];
  repeated_issues?: any[];
  likely_questions?: string[];
  improvement_plan?: any[];
  model_answers?: { question: string; improved_answer: string; why_stronger?: string }[];
  next_recommendation?: string;
  generated_at?: string;
}

async function defenseHeaders(openrouterKey?: string): Promise<HeadersInit> {
  const base = await getAuthHeaders() as Record<string, string>;
  if (openrouterKey) base['X-OpenRouter-Key'] = openrouterKey;
  return base;
}

export async function getReasoningModes(): Promise<Record<ReasoningMode, ReasoningModeInfo>> {
  const response = await fetch(`${API_URL}/reasoning-modes`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  const data = await response.json();
  return data.modes;
}

export async function analyzeResearch(
  debateId: string,
  openrouterKey: string,
  mode: ReasoningMode = 'medium',
  modelId = ''
): Promise<{ status: string; profile: ResearchProfile; mode_used: string }> {
  const response = await fetch(`${API_URL}/debates/${debateId}/analyze-research`, {
    method: 'POST',
    headers: await defenseHeaders(openrouterKey),
    body: JSON.stringify({ model_id: modelId, mode }),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export async function suggestPersonas(
  debateId: string,
  openrouterKey: string,
  mode: ReasoningMode = 'medium'
): Promise<{ personas: SuggestedPersona[]; mode: string; mode_info: ReasoningModeInfo }> {
  const response = await fetch(`${API_URL}/debates/${debateId}/suggest-personas`, {
    method: 'POST',
    headers: await defenseHeaders(openrouterKey),
    body: JSON.stringify({ mode }),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export async function getResearchProfile(debateId: string): Promise<ResearchProfile> {
  const response = await fetch(`${API_URL}/debates/${debateId}/research-profile`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) {
    if (response.status === 404) throw new Error('not_found');
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export type ChallengeSeverity = 'gentle' | 'standard' | 'rigorous' | 'hostile';
export type PracticeMode = 'thesis_defense' | 'proposal_defense' | 'conference_qa' | 'journal_review';

export async function generateDefenseQuestions(
  debateId: string,
  openrouterKey: string,
  nQuestions = 15,
  mode: ReasoningMode = 'medium',
  modelId = '',
  severity: ChallengeSeverity = 'standard',
  practiceMode: PracticeMode = 'thesis_defense'
): Promise<{ count: number; questions: DefenseQuestion[]; mode_used: string }> {
  const response = await fetch(`${API_URL}/debates/${debateId}/defense-questions/generate`, {
    method: 'POST',
    headers: await defenseHeaders(openrouterKey),
    body: JSON.stringify({ n_questions: nQuestions, model_id: modelId, mode, severity, practice_mode: practiceMode }),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export async function addFollowUpQuestion(
  debateId: string,
  parentQuestionId: string,
  questionText: string
): Promise<DefenseQuestion> {
  const response = await fetch(`${API_URL}/debates/${debateId}/defense-questions/follow-up`, {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: JSON.stringify({ parent_question_id: parentQuestionId, question_text: questionText }),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export async function getDefenseQuestions(
  debateId: string,
  unansweredOnly = false
): Promise<{ count: number; questions: DefenseQuestion[] }> {
  const params = unansweredOnly ? '?unanswered_only=true' : '';
  const response = await fetch(`${API_URL}/debates/${debateId}/defense-questions${params}`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

export async function submitAnswer(
  debateId: string,
  questionId: string,
  answerText: string,
  openrouterKey: string,
  mode: ReasoningMode = 'medium',
  modelId = '',
  severity: ChallengeSeverity = 'standard'
): Promise<AnswerEvaluation> {
  const response = await fetch(`${API_URL}/debates/${debateId}/answers`, {
    method: 'POST',
    headers: await defenseHeaders(openrouterKey),
    body: JSON.stringify({ question_id: questionId, answer_text: answerText, model_id: modelId, mode, severity }),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export async function getAnswers(debateId: string): Promise<{ count: number; answers: any[] }> {
  const response = await fetch(`${API_URL}/debates/${debateId}/answers`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

export async function generateReadinessReport(
  debateId: string,
  openrouterKey: string,
  mode: ReasoningMode = 'medium',
  modelId = ''
): Promise<ReadinessReport> {
  const response = await fetch(`${API_URL}/debates/${debateId}/readiness-report`, {
    method: 'POST',
    headers: await defenseHeaders(openrouterKey),
    body: JSON.stringify({ model_id: modelId, mode }),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export async function getReadinessReport(debateId: string): Promise<ReadinessReport> {
  const response = await fetch(`${API_URL}/debates/${debateId}/readiness-report`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) {
    if (response.status === 404) throw new Error('not_found');
    throw new Error(response.statusText);
  }
  return response.json();
}

// ============================================================================
// PRESENTATION COACH (concept 7.6)
// ============================================================================

export interface DeckSlide {
  slide_num: number;
  title: string;
  body_words: number;
  notes_words: number;
  bullet_count: number;
  text: string;
  flags: string[];
}

export interface DeckData {
  material_id: string;
  deck_title: string;
  slide_count: number;
  estimated_minutes: number;
  deck_flags: string[];
  slides: DeckSlide[];
}

export interface DeckCoach {
  overall_impression: string;
  structure_feedback: string;
  clarity_feedback: string;
  slide_suggestions: { slide_num: number; suggestion: string }[];
  strongest_slide?: { slide_num: number; why: string };
  likely_audience_questions: string[];
}

export async function getPresentationDeck(debateId: string): Promise<DeckData> {
  const response = await fetch(`${API_URL}/debates/${debateId}/presentation/deck`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export async function coachPresentation(
  debateId: string,
  openrouterKey: string,
  mode: ReasoningMode = 'light',
): Promise<DeckData & { coach: DeckCoach }> {
  const headers = await getAuthHeaders() as Record<string, string>;
  headers['X-OpenRouter-Key'] = openrouterKey;
  const response = await fetch(`${API_URL}/debates/${debateId}/presentation/coach`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ mode }),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

// ============================================================================
// COMMITTEE TWIN (Pillar 2)
// ============================================================================

export interface TwinPaper {
  title: string;
  year: number | null;
  venue: string;
  citation_count: number;
  url: string;
  doi: string | null;
  source: string;
  quote: string;
}

export interface CommitteeTwin {
  twin_id: string;
  name: string;
  affiliation: string;
  role: string;
  corpus_found: boolean;
  paper_count: number;
  chunks_ingested: number;
  papers: TwinPaper[];
  system_prompt: string;
  model_id: string;
  note: string | null;
}

export interface CommitteeTwinResponse {
  debate_id: string;
  twins: CommitteeTwin[];
  summary: { requested: number; built: number; with_corpus: number; papers_ingested: number };
}

export async function buildCommitteeTwins(
  debateId: string,
  reviewers: { name: string; affiliation?: string; role?: string }[],
  topicHint = '',
  maxPapersPerReviewer = 5,
): Promise<CommitteeTwinResponse> {
  const response = await fetch(`${API_URL}/debates/${debateId}/committee-twins`, {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: JSON.stringify({
      reviewers,
      topic_hint: topicHint,
      max_papers_per_reviewer: maxPapersPerReviewer,
      mode: 'light',
    }),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

// ============================================================================
// READINESS CERTIFICATE (Pillar 3)
// ============================================================================

export interface CertDimension {
  key: string;
  label: string;
  what: string;
  first_score: number;
  latest_score: number;
  delta: number;
  band: string;
  latest_comment: string;
  points: { at: string | null; trigger: string; score: number; comment: string }[];
}

export interface CertEvidenceAnswer {
  answer_id: string;
  question_id: string | null;
  question_text: string;
  category: string | null;
  persona: string | null;
  answer_score: number | null;
  strength: string;
  weakness: string;
  answered_at: string | null;
  source: {
    chunk_id: string;
    excerpt: string;
    sha256: string | null;
    sha256_verified: boolean;
    page_num: number | null;
  } | null;
}

export interface ReadinessCertificate {
  certificate_id: string;
  issued_at: string;
  session: { debate_id: string; title: string; workspace_id: string; created_at: string | null };
  overall: {
    first_score: number | null;
    latest_score: number | null;
    delta: number;
    band: string;
    assessment_count: number;
  };
  dimensions: CertDimension[];
  evidence: {
    answers: CertEvidenceAnswer[];
    panel_events: { count: number; sequence_from: number | null; sequence_to: number | null };
  };
  anchor: { algorithm: string; hash: string; certificate_id: string };
}

export async function getCertificate(debateId: string): Promise<ReadinessCertificate & { issued?: boolean }> {
  const response = await fetch(`${API_URL}/debates/${debateId}/certificate`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export interface IssuedCertificate {
  certificate_id: string;
  issued_at: string | null;
  anchor_hash: string;
  algorithm: string;
  key_id: string;
  verify_path: string;
}

export async function issueCertificate(debateId: string): Promise<IssuedCertificate> {
  const response = await fetch(`${API_URL}/debates/${debateId}/certificate/issue`, {
    method: 'POST',
    headers: await getAuthHeaders(),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

export interface CertificateVerification {
  certificate_id: string;
  issued_at: string;
  algorithm: string;
  anchor_hash: string;
  key_id: string;
  public_key: string;
  summary: {
    title: string;
    overall: { first_score: number | null; latest_score: number | null; delta: number; band: string; assessment_count: number };
    dimensions: { key: string; label: string; first_score: number; latest_score: number; delta: number; band: string }[];
    evidence_counts: { answers: number; panel_events: number };
  };
  checks: {
    signature_valid: boolean;
    hash_matches_payload: boolean;
    live_check_available: boolean;
    evidence_unchanged_since_issue: boolean | null;
  };
  verdict: 'VALID' | 'INVALID';
}

export interface ReadinessOverviewSession {
  debate_id: string;
  title: string;
  state: string;
  created_at: string | null;
  first_score: number | null;
  latest_score: number | null;
  delta: number | null;
  band: string | null;
  assessment_count: number;
  answer_count: number;
  last_assessed_at: string | null;
  certificate_id: string | null;
  certificate_issued_at: string | null;
}

export async function getReadinessOverview(
  workspaceId: string,
): Promise<{ workspace_id: string; sessions: ReadinessOverviewSession[]; total: number }> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/readiness-overview`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

export interface StudentSession {
  debate_id: string;
  title: string;
  latest_score: number | null;
  band: string | null;
  answer_count: number;
  department_id: string | null;
}
export interface StudentOverview {
  student: string;
  session_count: number;
  avg_score: number | null;
  band: string | null;
  at_risk: boolean;
  sessions: StudentSession[];
}
export interface StudentsOverview {
  workspace_id: string;
  students: StudentOverview[];
  student_count: number;
  at_risk_count: number;
  common_weak_areas: { area: string; count: number }[];
}

export async function getStudentsOverview(
  workspaceId: string,
  departmentId?: string
): Promise<StudentsOverview> {
  const qs = departmentId ? `?department_id=${encodeURIComponent(departmentId)}` : '';
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/students-overview${qs}`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

// ── Departments & invites (institutional layer) ─────────────────────────────

export interface Department {
  department_id: string;
  name: string;
  session_count: number;
}

export async function listDepartments(workspaceId: string): Promise<{ departments: Department[] }> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/departments`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

export async function createDepartment(
  workspaceId: string,
  name: string
): Promise<{ department_id: string; name: string }> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/departments`, {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || response.statusText);
  }
  return response.json();
}

export async function setDebateDepartment(
  debateId: string,
  departmentId: string | null
): Promise<void> {
  const response = await fetch(`${API_URL}/debates/${debateId}/department`, {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: JSON.stringify({ department_id: departmentId }),
  });
  if (!response.ok) throw new Error(response.statusText);
}

export interface InviteResult {
  invite_token: string;
  role: string;
  expires_at: string;
  accept_path: string;
}

export async function createInvite(
  workspaceId: string,
  role: 'advisor' | 'student'
): Promise<InviteResult> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/invites`, {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: JSON.stringify({ role }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || response.statusText);
  }
  return response.json();
}

export async function setStudentLabel(debateId: string, label: string): Promise<void> {
  const response = await fetch(`${API_URL}/debates/${debateId}/student-label`, {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: JSON.stringify({ student_label: label }),
  });
  if (!response.ok) throw new Error(response.statusText);
}

export async function acceptInvite(token: string): Promise<{ workspace_id: string; role: string; joined: boolean }> {
  const response = await fetch(`${API_URL}/invites/${encodeURIComponent(token)}/accept`, {
    method: 'POST',
    headers: await getAuthHeaders(),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || response.statusText);
  }
  return response.json();
}

// ── Billing / plans (paywall) ───────────────────────────────────────────────

export interface PlanFeatures {
  advisor_console: boolean; certificates: boolean; presentation_coach: boolean;
  departments: boolean; invites: boolean; sso: boolean;
}
export interface PlanLimits {
  max_sessions: number | null;
  max_materials_per_session: number | null;
}
export interface Plan {
  plan: string;
  rank: number;
  label: string;
  price_hint: string;
  blurb: string;
  features: PlanFeatures;
  limits: PlanLimits;
}
export interface Me {
  user_id: string;
  workspace_id: string;
  role: string;
  email: string | null;
  plan: Plan;
}
export interface BillingInfo {
  workspace_id: string;
  current: Plan;
  plans: Plan[];
  usage: { sessions: { used: number; limit: number | null }; materials_per_session_limit: number | null };
  payment_enabled: boolean;
}

export async function getMe(): Promise<Me> {
  const response = await fetch(`${API_URL}/me`, { headers: await getAuthHeaders() });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

export async function getBilling(workspaceId: string): Promise<BillingInfo> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/billing`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

export async function changePlan(workspaceId: string, plan: string): Promise<BillingInfo['current']> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/billing/plan`, {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: JSON.stringify({ plan }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || response.statusText);
  }
  const data = await response.json();
  return data.current;
}

/** Start a Stripe checkout (only when payment_enabled). Returns hosted URL. */
export async function startCheckout(workspaceId: string, plan: string): Promise<string> {
  const response = await fetch(`${API_URL}/workspaces/${workspaceId}/billing/checkout`, {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: JSON.stringify({ plan }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || response.statusText);
  }
  const data = await response.json();
  return data.checkout_url;
}

/** PUBLIC — no auth header on purpose; anyone with the link can verify. */
export async function getCertificateVerification(certificateId: string): Promise<CertificateVerification> {
  const response = await fetch(`${API_URL}/verify/${encodeURIComponent(certificateId)}`);
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

// ============================================================================
// PROVENANCE / GLASS-BOX
// ============================================================================

export interface ProvenanceSource {
  chunk_id: string;
  material_id: string | null;
  doc_title: string;
  page_num: number | null;
  char_start: number | null;
  char_end: number | null;
  sha256: string | null;
  sha256_verified: boolean;
  chunk_text: string;
  highlight: { start: number; end: number } | null;
}

export interface ProvenanceClaim {
  claim_id: string;
  type: string;
  persona: string;
  category: string;
  difficulty: string;
  text: string;
  excerpt: string;
  grounded: boolean;
  answered: boolean;
  source: ProvenanceSource | null;
}

export interface ProvenanceResponse {
  debate_id: string;
  materials: { material_id: string; title: string; kind: string; file_mime_type?: string | null; chunk_count: number }[];
  claims: ProvenanceClaim[];
  summary: {
    total_claims: number;
    grounded: number;
    gaps: number;
    sha256_verified: number;
    grounded_pct: number;
  };
}

export async function getProvenance(debateId: string): Promise<ProvenanceResponse> {
  const response = await fetch(`${API_URL}/debates/${debateId}/provenance`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

export interface UngroundedCitationDemo {
  claim: string;
  model: string;
  answer: string;
  had_document_access: boolean;
}

/** Trust-comparison demo: what a model says when asked for the manuscript
 *  source of a critique WITHOUT being given the manuscript. */
export async function demoUngroundedCitation(
  debateId: string,
  claim: string,
  openrouterKey: string,
): Promise<UngroundedCitationDemo> {
  const headers = await getAuthHeaders() as Record<string, string>;
  headers['X-OpenRouter-Key'] = openrouterKey;
  const response = await fetch(`${API_URL}/debates/${debateId}/demo/ungrounded-citation`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ claim }),
  });
  if (!response.ok) {
    const b = await response.json().catch(() => null);
    throw new Error(b?.detail ?? response.statusText);
  }
  return response.json();
}

// ============================================================================
// AI PANEL SUGGESTION
// ============================================================================

export interface PanelSuggestion {
  template_id: string;
  reason: string;
}

export async function suggestPanelTemplates(
  title: string,
  abstract: string,
  templates: AgentTemplate[],
  openrouterKey: string,
  n: number = 5,
): Promise<{ suggestions: PanelSuggestion[]; model_used: string }> {
  const response = await fetch(`${API_URL}/ai/suggest-panel`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-OpenRouter-Key': openrouterKey,
    },
    body: JSON.stringify({
      title,
      abstract,
      n,
      templates: templates.map(t => ({
        template_id: t.template_id,
        label: t.label,
        role_title: t.role_title,
        category: t.category,
        character: t.character || '',
      })),
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to suggest panel');
  }

  return response.json();
}

// ============================================================================
// ACADEMIC ASSESSMENT MATRIX (10 dimensions)
// ============================================================================

export interface AssessmentDimension {
  key: string;
  label: string;
  score: number;
  comment: string;
}

export interface AcademicAssessment {
  assessment_id: string;
  debate_id: string;
  trigger_source: string;
  dimensions: AssessmentDimension[];
  overall_score: number;
  overall_remarks: string;
  basis?: {
    has_profile?: boolean;
    answer_count?: number;
    message_count?: number;
    has_summary?: boolean;
  };
  model_used?: string;
  generated_at?: string;
}

export async function generateAcademicAssessment(
  debateId: string,
  openrouterKey: string,
  triggerSource: string = 'manual',
  mode: ReasoningMode = 'light',
): Promise<AcademicAssessment> {
  const headers = await getAuthHeaders() as Record<string, string>;
  headers['X-OpenRouter-Key'] = openrouterKey;
  const response = await fetch(`${API_URL}/debates/${debateId}/assessment/generate`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ mode, trigger_source: triggerSource, model_id: '' }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? response.statusText);
  }
  return response.json();
}

export async function getAcademicAssessment(debateId: string): Promise<AcademicAssessment> {
  const response = await fetch(`${API_URL}/debates/${debateId}/assessment`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) {
    if (response.status === 404) throw new Error('not_found');
    throw new Error(response.statusText);
  }
  return response.json();
}

// ============================================================================
// ACCOUNT-STORED OPENROUTER KEY (encrypted server-side)
// ============================================================================

export interface AccountKeyStatus {
  connected: boolean;
  masked: string | null;
}

export async function getAccountOpenRouterKey(): Promise<AccountKeyStatus> {
  const response = await fetch(`${API_URL}/me/openrouter-key`, {
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}

export async function saveAccountOpenRouterKey(apiKey: string): Promise<AccountKeyStatus> {
  const response = await fetch(`${API_URL}/me/openrouter-key`, {
    method: 'PUT',
    headers: await getAuthHeaders(),
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(formatErrorDetail(body?.detail, 'Failed to save key'));
  }
  return response.json();
}

export async function deleteAccountOpenRouterKey(): Promise<AccountKeyStatus> {
  const response = await fetch(`${API_URL}/me/openrouter-key`, {
    method: 'DELETE',
    headers: await getAuthHeaders(),
  });
  if (!response.ok) throw new Error(response.statusText);
  return response.json();
}
