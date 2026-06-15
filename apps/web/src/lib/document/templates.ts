/**
 * Document Template Library
 * Pre-built templates for different debate types
 */

import {
  DocumentTemplate,
  TemplateCategory,
  SectionType,
  AssignmentStrategy,
} from './types';

// ============================================================================
// Template Definitions
// ============================================================================

export const DOCUMENT_TEMPLATES: Record<string, DocumentTemplate> = {
  // General purpose meeting summary
  'meeting-summary': {
    id: 'meeting-summary',
    name: 'Meeting Summary',
    description: 'Concise summary of debate with key points and action items',
    category: TemplateCategory.GENERAL,
    icon: '📝',
    sections: [
      {
        key: 'executive_summary',
        title: 'Executive Summary',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.HOST,
        wordLimit: 150,
        required: true,
        placeholder: 'Brief overview of the debate outcome...',
        order: 1,
      },
      {
        key: 'key_arguments',
        title: 'Key Arguments',
        type: SectionType.LIST,
        assignmentStrategy: AssignmentStrategy.AUTO,
        wordLimit: 300,
        required: true,
        placeholder: 'Main arguments presented during the debate...',
        order: 2,
      },
      {
        key: 'conclusion',
        title: 'Conclusion & Recommendations',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.HOST,
        wordLimit: 200,
        required: true,
        placeholder: 'Final consensus and recommended actions...',
        order: 3,
      },
    ],
    metadata: {
      estimatedTime: 10,
      difficulty: 'easy',
      tags: ['general', 'summary', 'quick'],
    },
  },

  // Medical consultation report
  'medical-consultation': {
    id: 'medical-consultation',
    name: 'Medical Consultation Report',
    description: 'Comprehensive medical analysis with multiple specialist perspectives',
    category: TemplateCategory.MEDICAL,
    icon: '🏥',
    sections: [
      {
        key: 'patient_case',
        title: 'Patient Case Overview',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.MANUAL,
        wordLimit: 100,
        required: true,
        placeholder: 'Brief description of the patient case...',
        order: 1,
      },
      {
        key: 'medical_analysis',
        title: 'Medical Perspective',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.ROLE,
        assignedRole: 'surgeon',
        wordLimit: 300,
        required: true,
        placeholder: 'Medical analysis from surgical perspective...',
        order: 2,
      },
      {
        key: 'risk_assessment',
        title: 'Risk Assessment',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.ROLE,
        assignedRole: 'cardiologist',
        wordLimit: 250,
        required: true,
        placeholder: 'Risk evaluation and considerations...',
        order: 3,
      },
      {
        key: 'treatment_options',
        title: 'Treatment Options',
        type: SectionType.LIST,
        assignmentStrategy: AssignmentStrategy.AUTO,
        wordLimit: 200,
        required: true,
        placeholder: 'Available treatment approaches...',
        order: 4,
      },
      {
        key: 'recommendation',
        title: 'Final Recommendation',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.HOST,
        wordLimit: 150,
        required: true,
        placeholder: 'Consensus recommendation based on all perspectives...',
        order: 5,
      },
    ],
    metadata: {
      estimatedTime: 20,
      difficulty: 'hard',
      tags: ['medical', 'healthcare', 'consultation'],
    },
  },

  // Legal analysis document
  'legal-analysis': {
    id: 'legal-analysis',
    name: 'Legal Analysis',
    description: 'Legal case analysis with precedents and recommendations',
    category: TemplateCategory.LEGAL,
    icon: '⚖️',
    sections: [
      {
        key: 'case_summary',
        title: 'Case Summary',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.MANUAL,
        wordLimit: 150,
        required: true,
        placeholder: 'Overview of the legal case...',
        order: 1,
      },
      {
        key: 'legal_perspective',
        title: 'Legal Analysis',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.ROLE,
        assignedRole: 'attorney',
        wordLimit: 400,
        required: true,
        placeholder: 'Detailed legal analysis...',
        order: 2,
      },
      {
        key: 'precedents',
        title: 'Relevant Precedents',
        type: SectionType.LIST,
        assignmentStrategy: AssignmentStrategy.ROLE,
        assignedRole: 'attorney',
        wordLimit: 250,
        required: false,
        placeholder: 'Similar cases and precedents...',
        order: 3,
      },
      {
        key: 'recommendation',
        title: 'Legal Recommendation',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.HOST,
        wordLimit: 200,
        required: true,
        placeholder: 'Recommended course of action...',
        order: 4,
      },
    ],
    metadata: {
      estimatedTime: 18,
      difficulty: 'hard',
      tags: ['legal', 'case analysis', 'law'],
    },
  },

  // Technical decision document
  'technical-decision': {
    id: 'technical-decision',
    name: 'Technical Decision',
    description: 'Technical architecture or implementation decision documentation',
    category: TemplateCategory.TECHNICAL,
    icon: '💻',
    sections: [
      {
        key: 'problem_statement',
        title: 'Problem Statement',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.MANUAL,
        wordLimit: 150,
        required: true,
        placeholder: 'Define the technical problem or decision...',
        order: 1,
      },
      {
        key: 'technical_analysis',
        title: 'Technical Analysis',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.ROLE,
        assignedRole: 'tech_lead',
        wordLimit: 350,
        required: true,
        placeholder: 'Technical evaluation of options...',
        order: 2,
      },
      {
        key: 'options_comparison',
        title: 'Options Comparison',
        type: SectionType.TABLE,
        assignmentStrategy: AssignmentStrategy.AUTO,
        wordLimit: 300,
        required: true,
        placeholder: 'Compare different technical approaches...',
        order: 3,
      },
      {
        key: 'architecture_diagram',
        title: 'Architecture Diagram',
        type: SectionType.DIAGRAM,
        assignmentStrategy: AssignmentStrategy.ROLE,
        assignedRole: 'tech_lead',
        required: false,
        placeholder: 'Visual architecture representation...',
        order: 4,
      },
      {
        key: 'tradeoffs',
        title: 'Trade-offs & Considerations',
        type: SectionType.LIST,
        assignmentStrategy: AssignmentStrategy.AUTO,
        wordLimit: 250,
        required: true,
        placeholder: 'Pros, cons, and considerations...',
        order: 5,
      },
      {
        key: 'decision',
        title: 'Final Decision & Rationale',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.HOST,
        wordLimit: 200,
        required: true,
        placeholder: 'Selected approach and reasoning...',
        order: 6,
      },
    ],
    metadata: {
      estimatedTime: 25,
      difficulty: 'hard',
      tags: ['technical', 'architecture', 'engineering'],
    },
  },

  // Business strategy document
  'business-strategy': {
    id: 'business-strategy',
    name: 'Business Strategy',
    description: 'Strategic business decision with market analysis and recommendations',
    category: TemplateCategory.BUSINESS,
    icon: '📊',
    sections: [
      {
        key: 'situation_analysis',
        title: 'Situation Analysis',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.MANUAL,
        wordLimit: 200,
        required: true,
        placeholder: 'Current business situation and context...',
        order: 1,
      },
      {
        key: 'market_perspective',
        title: 'Market Perspective',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.ROLE,
        assignedRole: 'business_analyst',
        wordLimit: 300,
        required: true,
        placeholder: 'Market analysis and trends...',
        order: 2,
      },
      {
        key: 'financial_analysis',
        title: 'Financial Analysis',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.ROLE,
        assignedRole: 'cfo',
        wordLimit: 250,
        required: false,
        placeholder: 'Financial implications and projections...',
        order: 3,
      },
      {
        key: 'strategic_options',
        title: 'Strategic Options',
        type: SectionType.LIST,
        assignmentStrategy: AssignmentStrategy.AUTO,
        wordLimit: 300,
        required: true,
        placeholder: 'Available strategic approaches...',
        order: 4,
      },
      {
        key: 'recommendation',
        title: 'Strategic Recommendation',
        type: SectionType.TEXT,
        assignmentStrategy: AssignmentStrategy.HOST,
        wordLimit: 200,
        required: true,
        placeholder: 'Recommended strategy and action plan...',
        order: 5,
      },
    ],
    metadata: {
      estimatedTime: 22,
      difficulty: 'medium',
      tags: ['business', 'strategy', 'planning'],
    },
  },
};

// ============================================================================
// Template Utilities
// ============================================================================

export function getTemplate(templateId: string): DocumentTemplate | null {
  return DOCUMENT_TEMPLATES[templateId] || null;
}

export function getAllTemplates(): DocumentTemplate[] {
  return Object.values(DOCUMENT_TEMPLATES);
}

export function getTemplatesByCategory(category: TemplateCategory): DocumentTemplate[] {
  return getAllTemplates().filter(t => t.category === category);
}

export function getTemplateCategories(): TemplateCategory[] {
  return Object.values(TemplateCategory);
}

// Helper to get role-specific templates
export function getTemplatesForRole(role: string): DocumentTemplate[] {
  return getAllTemplates().filter(template =>
    template.sections.some(
      section => section.assignedRole?.toLowerCase() === role.toLowerCase()
    )
  );
}

// Helper to estimate total word limit for a template
export function calculateTemplateWordCount(template: DocumentTemplate): number {
  return template.sections.reduce((sum, section) => {
    return sum + (section.wordLimit || 0);
  }, 0);
}

// Helper to validate template structure
export function validateTemplate(template: DocumentTemplate): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!template.id || !template.name) {
    errors.push('Template must have id and name');
  }

  if (!template.sections || template.sections.length === 0) {
    errors.push('Template must have at least one section');
  }

  const requiredSections = template.sections.filter(s => s.required);
  if (requiredSections.length === 0) {
    errors.push('Template must have at least one required section');
  }

  // Check for duplicate section keys
  const keys = template.sections.map(s => s.key);
  const duplicates = keys.filter((key, index) => keys.indexOf(key) !== index);
  if (duplicates.length > 0) {
    errors.push(`Duplicate section keys: ${duplicates.join(', ')}`);
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}
