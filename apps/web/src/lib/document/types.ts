/**
 * Document Collaboration Types
 * Defines all type definitions for the document system
 */

// ============================================================================
// Core Document Types
// ============================================================================

export interface Document {
  documentId: string;
  debateId: string;
  templateId: string;
  title: string;
  status: DocumentStatus;
  metadata: DocumentMetadata;
  sections: DocumentSection[];
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

export enum DocumentStatus {
  DRAFT = 'draft',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  EXPORTED = 'exported',
}

export interface DocumentMetadata {
  totalWords: number;
  targetWords: number;
  completionPercentage: number;
  lastEditedBy?: string;
  exportFormats?: ExportFormat[];
}

// ============================================================================
// Document Sections
// ============================================================================

export interface DocumentSection {
  section_id?: string;
  id?: string;
  section_key?: string;
  key?: string;
  section_title?: string;
  title?: string;
  section_type?: string;
  type?: SectionType;
  assigned_agent_id?: string;
  assignedAgentId?: string;
  assigned_agent_name?: string;
  assignedAgentName?: string;
  word_limit?: number;
  wordLimit?: number;
  word_count?: number;
  wordCount?: number;
  status?: SectionStatus | string;
  content?: string;
  started_at?: string;
  startedAt?: string;
  completed_at?: string;
  completedAt?: string;
  schema?: JSONSchema;
}

export enum SectionType {
  TEXT = 'text',
  LIST = 'list',
  DIAGRAM = 'diagram',
  TABLE = 'table',
}

export enum SectionStatus {
  PENDING = 'pending',
  ASSIGNED = 'assigned',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  REVIEW = 'review',
}

// ============================================================================
// Templates
// ============================================================================

export interface DocumentTemplate {
  id: string;
  name: string;
  description: string;
  category: TemplateCategory;
  icon: string;
  sections: TemplateSectionDefinition[];
  metadata: TemplateMetadata;
}

export enum TemplateCategory {
  GENERAL = 'general',
  MEDICAL = 'medical',
  LEGAL = 'legal',
  BUSINESS = 'business',
  TECHNICAL = 'technical',
}

export interface TemplateSectionDefinition {
  key: string;
  title: string;
  type: SectionType;
  assignmentStrategy: AssignmentStrategy;
  assignedRole?: string;  // Role name like "surgeon", "attorney"
  wordLimit?: number;
  required: boolean;
  placeholder?: string;
  schema?: JSONSchema;
  order: number;
}

export enum AssignmentStrategy {
  HOST = 'host',           // Assign to Ultimate Host
  ROLE = 'role',           // Assign based on agent role
  MANUAL = 'manual',       // User assigns manually
  AUTO = 'auto',           // System assigns automatically
}

export interface TemplateMetadata {
  estimatedTime: number;   // Minutes
  difficulty: 'easy' | 'medium' | 'hard';
  tags: string[];
  usageCount?: number;
}

// ============================================================================
// JSON Schema (for structured content)
// ============================================================================

export interface JSONSchema {
  type: string;
  properties?: Record<string, JSONSchemaProperty>;
  required?: string[];
  items?: JSONSchema;
}

export interface JSONSchemaProperty {
  type: string;
  description?: string;
  maxLength?: number;
  minLength?: number;
  items?: JSONSchema;
  enum?: string[];
}

// ============================================================================
// Agent Writing
// ============================================================================

export interface AgentWritingTask {
  taskId: string;
  documentId: string;
  sectionId: string;
  agentId: string;
  agentName: string;
  prompt: string;
  wordLimit?: number;
  schema?: JSONSchema;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  createdAt: string;
}

export interface AgentPresence {
  userId: string;
  userName: string;
  userType: 'human' | 'agent';
  color: string;
  cursor?: CursorPosition;
  selection?: SelectionRange;
  activeSectionId?: string;
  lastActive: number;
}

export interface CursorPosition {
  x: number;
  y: number;
  position: number; // Character position in document
}

export interface SelectionRange {
  from: number;
  to: number;
}

// ============================================================================
// Export
// ============================================================================

export enum ExportFormat {
  PDF = 'pdf',
  DOCX = 'docx',
  MARKDOWN = 'markdown',
  HTML = 'html',
}

export interface ExportRequest {
  documentId: string;
  format: ExportFormat;
  includeMetadata: boolean;
  includeDiagrams: boolean;
}

export interface ExportResponse {
  exportId: string;
  documentId: string;
  format: ExportFormat;
  downloadUrl: string;
  expiresAt: string;
  fileSize: number;
}

// ============================================================================
// WebSocket Messages
// ============================================================================

export interface DocumentWSMessage {
  type: DocumentWSMessageType;
  payload: any;
  timestamp: number;
  senderId?: string;
}

export enum DocumentWSMessageType {
  // Yjs sync protocol
  SYNC_STEP_1 = 'sync_step_1',
  SYNC_STEP_2 = 'sync_step_2',
  UPDATE = 'update',
  
  // Awareness (presence)
  AWARENESS = 'awareness',
  
  // Document events
  SECTION_ASSIGNED = 'section_assigned',
  SECTION_STARTED = 'section_started',
  SECTION_COMPLETED = 'section_completed',
  AGENT_WRITING = 'agent_writing',
  
  // Control
  PING = 'ping',
  PONG = 'pong',
}

// ============================================================================
// API Requests/Responses
// ============================================================================

export interface CreateDocumentRequest {
  debateId: string;
  templateId: string;
  title: string;
  customSections?: Partial<TemplateSectionDefinition>[];
}

export interface UpdateDocumentRequest {
  title?: string;
  status?: DocumentStatus;
  metadata?: Partial<DocumentMetadata>;
}

export interface AssignSectionRequest {
  sectionId: string;
  agentId?: string;
  agentName?: string;
}
