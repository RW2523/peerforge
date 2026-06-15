/**
 * Event type definitions
 * Generated manually from event schemas
 * These provide TypeScript types for all debate events
 */

export type SenderType = 'agent' | 'human' | 'system';

export type EventType =
  // Core message events
  | 'agent_message'
  | 'human_message'
  | 'agent_question'
  | 'agent_rebuttal'
  | 'intervention'
  | 'debate_summary'
  | 'evidence_request'
  | 'evidence_response'
  | 'summary_update'
  | 'decision_candidate'
  | 'decision_finalized'
  // Nudge protocol
  | 'pre_turn_nudge'
  | 'nudge_approved'
  | 'nudge_rejected'
  // Research protocol
  | 'research_request'
  | 'research_result'
  | 'research_denied'
  // Knowledge import
  | 'knowledge_imported'
  | 'knowledge_rejected'
  // Response handling
  | 'unknown_response'
  // Tool calling
  | 'tool_call_request'
  | 'tool_call_result'
  | 'tool_call_denied'
  // Voice
  | 'voice_transcript_partial'
  | 'voice_transcript_final'
  | 'voice_tts_started'
  | 'voice_tts_completed';

export interface CitationRef {
  source_id: string;
  excerpt?: string;
  url?: string;
}

export interface BaseEvent {
  event_id: string;
  debate_id: string;
  event_type: EventType;
  sender_type: SenderType;
  sender_id?: string;
  mentions?: string[];
  thread_id?: string;
  content: Record<string, any>;
  citation_refs?: CitationRef[];
  priority?: number;
  created_at: string;
}

export interface AgentMessageContent {
  message: string;
  model_id?: string;
  tokens_used?: number;
  verbosity_level?: 'brief' | 'standard' | 'deep_dive';
}

export interface AgentMessageEvent extends BaseEvent {
  event_type: 'agent_message';
  sender_type: 'agent';
  content: AgentMessageContent;
}

export interface InterventionContent {
  intent: 'clarify' | 'challenge' | 're_scope' | 'request_evidence' | 'decision_check';
  question_or_instruction: string;
  target_agents?: string[];
  blocking?: boolean;
}

export interface InterventionEvent extends BaseEvent {
  event_type: 'intervention';
  content: InterventionContent;
}

export interface DebateSummaryContent {
  summary: string;
  action_item_count: number;
}

export interface DebateSummaryEvent extends BaseEvent {
  event_type: 'debate_summary';
  sender_type: 'system';
  content: DebateSummaryContent;
}

export interface PreTurnNudgeContent {
  reason: 'urgent_correction' | 'new_evidence' | 'direct_challenge' | 'critical_risk';
  target_message_id?: string;
  proposed_response_brief: string;
}

export interface PreTurnNudgeEvent extends BaseEvent {
  event_type: 'pre_turn_nudge';
  sender_type: 'agent';
  content: PreTurnNudgeContent;
}

export interface ResearchRequestContent {
  query: string;
  justification: string;
  domains?: string[];
}

export interface ResearchRequestEvent extends BaseEvent {
  event_type: 'research_request';
  sender_type: 'agent';
  content: ResearchRequestContent;
}

export interface ResearchResultContent {
  request_id: string;
  results: Array<{
    source_url: string;
    title?: string;
    snippet: string;
    fetched_at?: string;
  }>;
}

export interface ResearchResultEvent extends BaseEvent {
  event_type: 'research_result';
  sender_type: 'system';
  content: ResearchResultContent;
}

export interface ResearchDeniedContent {
  request_id: string;
  reason: 'policy_disabled' | 'permission_denied' | 'domain_blocked' | 'rate_limit_exceeded' | 'requires_approval';
  details?: string;
}

export interface ResearchDeniedEvent extends BaseEvent {
  event_type: 'research_denied';
  sender_type: 'system';
  content: ResearchDeniedContent;
}

export interface ToolCallRequestContent {
  tool_name: string;
  args: Record<string, any>;
  justification: string;
}

export interface ToolCallRequestEvent extends BaseEvent {
  event_type: 'tool_call_request';
  sender_type: 'agent';
  content: ToolCallRequestContent;
}

export interface ToolCallResultContent {
  request_id: string;
  result: Record<string, any>;
  metadata?: {
    execution_time_ms?: number;
    tool_version?: string;
  };
}

export interface ToolCallResultEvent extends BaseEvent {
  event_type: 'tool_call_result';
  sender_type: 'system';
  content: ToolCallResultContent;
}

export interface ToolCallDeniedContent {
  request_id: string;
  reason: 'policy_disabled' | 'permission_denied' | 'tool_unavailable' | 'requires_approval';
  details?: string;
}

export interface ToolCallDeniedEvent extends BaseEvent {
  event_type: 'tool_call_denied';
  sender_type: 'system';
  content: ToolCallDeniedContent;
}

export interface KnowledgeImportedContent {
  source_type: 'document' | 'url' | 'database' | 'api';
  knowledge_id: string;
  summary?: string;
  metadata?: Record<string, any>;
}

export interface KnowledgeImportedEvent extends BaseEvent {
  event_type: 'knowledge_imported';
  sender_type: 'system';
  content: KnowledgeImportedContent;
}

export interface KnowledgeRejectedContent {
  source_type: 'document' | 'url' | 'database' | 'api';
  reason: 'invalid_format' | 'access_denied' | 'policy_violation' | 'size_exceeded';
  details?: string;
}

export interface KnowledgeRejectedEvent extends BaseEvent {
  event_type: 'knowledge_rejected';
  sender_type: 'system';
  content: KnowledgeRejectedContent;
}

export interface UnknownResponseContent {
  question_id: string;
  reason: 'no_knowledge_source' | 'insufficient_confidence' | 'requires_research' | 'out_of_scope';
  suggested_action?: string;
}

export interface UnknownResponseEvent extends BaseEvent {
  event_type: 'unknown_response';
  sender_type: 'agent';
  content: UnknownResponseContent;
}

export interface VoiceTranscriptPartialContent {
  transcript_id: string;
  text: string;
  is_final: false;
}

export interface VoiceTranscriptPartialEvent extends BaseEvent {
  event_type: 'voice_transcript_partial';
  content: VoiceTranscriptPartialContent;
}

export interface VoiceTranscriptFinalContent {
  transcript_id: string;
  text: string;
  is_final: true;
  confidence?: number;
  language?: string;
}

export interface VoiceTranscriptFinalEvent extends BaseEvent {
  event_type: 'voice_transcript_final';
  content: VoiceTranscriptFinalContent;
}

export type DebateEvent =
  | AgentMessageEvent
  | InterventionEvent
  | PreTurnNudgeEvent
  | ResearchRequestEvent
  | ResearchResultEvent
  | ResearchDeniedEvent
  | ToolCallRequestEvent
  | ToolCallResultEvent
  | ToolCallDeniedEvent
  | KnowledgeImportedEvent
  | KnowledgeRejectedEvent
  | UnknownResponseEvent
  | VoiceTranscriptPartialEvent
  | VoiceTranscriptFinalEvent
  | BaseEvent;
