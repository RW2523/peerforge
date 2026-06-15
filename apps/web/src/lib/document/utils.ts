/**
 * Document Utility Functions
 * Helper functions for document operations
 */

import { Document, DocumentSection, SectionStatus, DocumentStatus } from './types';

// ============================================================================
// Word Count Utilities
// ============================================================================

export function countWords(text: string): number {
  if (!text || text.trim().length === 0) return 0;
  
  // Remove HTML tags if any
  const cleanText = text.replace(/<[^>]*>/g, ' ');
  
  // Split by whitespace and filter empty strings
  const words = cleanText
    .trim()
    .split(/\s+/)
    .filter(word => word.length > 0);
  
  return words.length;
}

export function isWithinWordLimit(text: string, limit?: number): boolean {
  if (!limit) return true;
  return countWords(text) <= limit;
}

export function getWordLimitStatus(
  currentWords: number,
  limit?: number
): 'ok' | 'warning' | 'exceeded' {
  if (!limit) return 'ok';
  
  const percentage = (currentWords / limit) * 100;
  
  if (percentage > 100) return 'exceeded';
  if (percentage > 90) return 'warning';
  return 'ok';
}

// ============================================================================
// Section Progress Utilities
// ============================================================================

export function calculateSectionProgress(section: DocumentSection): number {
  if (section.status === SectionStatus.COMPLETED) return 100;
  if (section.status === SectionStatus.PENDING) return 0;
  
  // If in progress, calculate based on word count
  if (section.wordLimit && (section.wordCount ?? 0) > 0) {
    const progress = ((section.wordCount ?? 0) / section.wordLimit) * 100;
    return Math.min(progress, 95); // Cap at 95% until marked complete
  }
  
  return 25; // Default progress for assigned/in_progress
}

export function calculateDocumentProgress(sections: DocumentSection[]): number {
  if (sections.length === 0) return 0;
  
  const totalProgress = sections.reduce((sum, section) => {
    return sum + calculateSectionProgress(section);
  }, 0);
  
  return Math.round(totalProgress / sections.length);
}

export function getCompletedSectionCount(sections: DocumentSection[]): number {
  return sections.filter(s => s.status === SectionStatus.COMPLETED).length;
}

export function areAllRequiredSectionsComplete(
  sections: DocumentSection[],
  template: { sections: Array<{ key: string; required: boolean }> }
): boolean {
  const requiredKeys = template.sections
    .filter(s => s.required)
    .map(s => s.key);
  
  return requiredKeys.every(key => {
    const section = sections.find(s => s.key === key);
    return section && section.status === SectionStatus.COMPLETED;
  });
}

// ============================================================================
// Document Status Utilities
// ============================================================================

export function shouldMarkDocumentComplete(sections: DocumentSection[]): boolean {
  // All sections should be completed
  return sections.every(s => s.status === SectionStatus.COMPLETED);
}

export function getDocumentStatusColor(status: DocumentStatus): string {
  switch (status) {
    case DocumentStatus.DRAFT:
      return 'text-gray-500';
    case DocumentStatus.IN_PROGRESS:
      return 'text-blue-500';
    case DocumentStatus.COMPLETED:
      return 'text-green-500';
    case DocumentStatus.EXPORTED:
      return 'text-purple-500';
    default:
      return 'text-gray-500';
  }
}

export function getSectionStatusColor(status: SectionStatus): string {
  switch (status) {
    case SectionStatus.PENDING:
      return 'bg-gray-200 text-gray-700';
    case SectionStatus.ASSIGNED:
      return 'bg-yellow-200 text-yellow-800';
    case SectionStatus.IN_PROGRESS:
      return 'bg-blue-200 text-blue-800';
    case SectionStatus.COMPLETED:
      return 'bg-green-200 text-green-800';
    case SectionStatus.REVIEW:
      return 'bg-purple-200 text-purple-800';
    default:
      return 'bg-gray-200 text-gray-700';
  }
}

// ============================================================================
// Time Utilities
// ============================================================================

export function formatTimeAgo(timestamp: string): string {
  const now = new Date();
  const past = new Date(timestamp);
  const seconds = Math.floor((now.getTime() - past.getTime()) / 1000);
  
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}min`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}min` : `${hours}h`;
}

// ============================================================================
// Agent Utilities
// ============================================================================

export function getAgentColor(agentName: string): string {
  // Generate consistent color based on agent name
  const colors = [
    '#3b82f6', // blue
    '#10b981', // green
    '#f59e0b', // amber
    '#ef4444', // red
    '#8b5cf6', // purple
    '#06b6d4', // cyan
    '#ec4899', // pink
    '#f97316', // orange
  ];
  
  const hash = agentName.split('').reduce((acc, char) => {
    return char.charCodeAt(0) + ((acc << 5) - acc);
  }, 0);
  
  return colors[Math.abs(hash) % colors.length];
}

export function getAgentInitials(agentName: string): string {
  return agentName
    .split(' ')
    .map(word => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

// ============================================================================
// Content Sanitization
// ============================================================================

export function sanitizeHtml(html: string): string {
  // Basic HTML sanitization (in production, use a library like DOMPurify)
  const allowedTags = ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'a'];
  const allowedAttributes = ['href', 'target'];
  
  // This is a simplified version - use DOMPurify in production
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = html;
  
  // Remove disallowed tags and attributes
  const walker = document.createTreeWalker(
    tempDiv,
    NodeFilter.SHOW_ELEMENT,
    null
  );
  
  const nodesToRemove: Element[] = [];
  
  while (walker.nextNode()) {
    const element = walker.currentNode as Element;
    
    if (!allowedTags.includes(element.tagName.toLowerCase())) {
      nodesToRemove.push(element);
      continue;
    }
    
    // Remove disallowed attributes
    Array.from(element.attributes).forEach(attr => {
      if (!allowedAttributes.includes(attr.name)) {
        element.removeAttribute(attr.name);
      }
    });
  }
  
  nodesToRemove.forEach(node => node.remove());
  
  return tempDiv.innerHTML;
}

// ============================================================================
// Validation
// ============================================================================

export function validateSectionContent(
  content: string,
  section: DocumentSection
): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  if (!content || content.trim().length === 0) {
    errors.push('Content cannot be empty');
    return { valid: false, errors };
  }
  
  const wordCount = countWords(content);
  
  if (section.wordLimit && wordCount > section.wordLimit) {
    errors.push(`Content exceeds word limit of ${section.wordLimit} (current: ${wordCount})`);
  }
  
  return {
    valid: errors.length === 0,
    errors,
  };
}

// ============================================================================
// Export Utilities
// ============================================================================

export function getExportFileName(
  documentTitle: string,
  format: string
): string {
  const sanitizedTitle = documentTitle
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  
  const timestamp = new Date().toISOString().split('T')[0];
  
  return `${sanitizedTitle}-${timestamp}.${format}`;
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return `${Math.round(bytes / Math.pow(k, i) * 100) / 100} ${sizes[i]}`;
}
