/**
 * Dialog components for Preflight step
 */

'use client';

import styles from './SetupSteps.module.css';
import { useState, useEffect } from 'react';

interface SkipDialogProps {
  isOpen: boolean;
  skipReason: string;
  onReasonChange: (reason: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export function SkipDialog({
  isOpen,
  skipReason,
  onReasonChange,
  onConfirm,
  onCancel,
}: SkipDialogProps) {
  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay} onClick={onCancel}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h3>Skip agent preparation</h3>
        <p style={{ marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          Provide a reason for skipping this agent's preparation:
        </p>
        <textarea
          value={skipReason}
          onChange={(e) => onReasonChange(e.target.value)}
          placeholder="e.g., Agent model unavailable, network issues, etc."
          className={styles.textarea}
          style={{ marginTop: '1rem', minHeight: '100px' }}
          autoFocus
        />
        <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
          <button onClick={onCancel} className={styles.btnSecondary}>
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={!skipReason.trim()}
            className={styles.btnPrimary}
          >
            Skip agent
          </button>
        </div>
      </div>
    </div>
  );
}

// Legacy prep pack dialog - kept for backwards compatibility but not used
// New PrepPackDialog is in PrepPackDialog.tsx

interface LegacyPrepPackDialogProps {
  isOpen: boolean;
  content: string | null;
  participantName: string;
  participantRole: string;
  meetingTitle?: string;
  meetingPurpose?: string;
  meetingAgenda?: string[];
  desiredOutcomes?: string[];
  materialsCount?: number;
  memoryChunksCount?: number;
  onClose: () => void;
}

export function LegacyPrepPackDialog({ 
  isOpen, 
  content, 
  participantName,
  participantRole,
  meetingTitle,
  meetingPurpose,
  meetingAgenda,
  desiredOutcomes,
  materialsCount = 0,
  memoryChunksCount = 0,
  onClose 
}: LegacyPrepPackDialogProps) {
  if (!isOpen || !content) return null;

  // Parse prep pack content to extract structure
  const parseContent = (rawContent: string) => {
    try {
      // Try to parse as JSON first
      const parsed = JSON.parse(rawContent);
      if (parsed.summary || parsed.key_points) {
        return {
          summary: parsed.summary || '',
          keyPoints: parsed.key_points || [],
          context: parsed.context || '',
          materials: parsed.materials_reviewed || []
        };
      }
    } catch {
      // Fall back to plain text parsing
      const lines = rawContent.split('\n');
      return {
        summary: rawContent.substring(0, 300),
        keyPoints: [],
        context: rawContent,
        materials: []
      };
    }
    return { summary: rawContent, keyPoints: [], context: rawContent, materials: [] };
  };

  const parsedContent = parseContent(content);

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div 
        className={styles.modal} 
        onClick={(e) => e.stopPropagation()} 
        style={{ maxWidth: '800px', maxHeight: '85vh', overflow: 'auto' }}
      >
        {/* Header */}
        <div style={{ 
          borderBottom: '2px solid var(--border)', 
          paddingBottom: '1rem', 
          marginBottom: '1.5rem' 
        }}>
          <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600 }}>
            Preparation Report
          </h2>
          <p style={{ 
            margin: '0.5rem 0 0 0', 
            fontSize: '0.875rem', 
            color: 'var(--text-muted)' 
          }}>
            Agent: <strong>{participantName}</strong> • Role: <strong>{participantRole}</strong>
          </p>
        </div>

        {/* Meeting Context */}
        {(meetingTitle || meetingPurpose || meetingAgenda || desiredOutcomes) && (
          <div style={{ 
            marginBottom: '1.5rem',
            padding: '1rem',
            background: 'var(--bg-panel)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
          }}>
            <h3 style={{ 
              margin: '0 0 0.75rem 0', 
              fontSize: '1rem', 
              fontWeight: 600,
              color: 'var(--accent)'
            }}>
              📋 Meeting Context Understanding
            </h3>
            {meetingTitle && (
              <div style={{ marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-1)' }}>Title: </span>
                <span style={{ fontSize: '0.875rem' }}>{meetingTitle}</span>
              </div>
            )}
            {meetingPurpose && (
              <div style={{ marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-1)' }}>Purpose: </span>
                <span style={{ fontSize: '0.875rem' }}>{meetingPurpose}</span>
              </div>
            )}
            {meetingAgenda && meetingAgenda.length > 0 && (
              <div style={{ marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-1)', display: 'block', marginBottom: '0.25rem' }}>
                  Agenda:
                </span>
                <ul style={{ margin: '0', paddingLeft: '1.5rem', fontSize: '0.875rem' }}>
                  {meetingAgenda.map((item, idx) => (
                    <li key={idx} style={{ marginBottom: '0.25rem' }}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {desiredOutcomes && desiredOutcomes.length > 0 && (
              <div>
                <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-1)', display: 'block', marginBottom: '0.25rem' }}>
                  Desired Outcomes:
                </span>
                <ul style={{ margin: '0', paddingLeft: '1.5rem', fontSize: '0.875rem' }}>
                  {desiredOutcomes.map((item, idx) => (
                    <li key={idx} style={{ marginBottom: '0.25rem' }}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Materials Reviewed */}
        {materialsCount > 0 && (
          <div style={{ 
            marginBottom: '1.5rem',
            padding: '1rem',
            background: '#e8f5e9',
            border: '1px solid #4caf50',
            borderRadius: '8px',
          }}>
            <h3 style={{ 
              margin: '0 0 0.5rem 0', 
              fontSize: '1rem', 
              fontWeight: 600,
              color: '#2e7d32'
            }}>
              ✅ Materials Analyzed
            </h3>
            <p style={{ margin: 0, fontSize: '0.875rem', color: '#2e7d32' }}>
              This agent has reviewed and analyzed <strong>{materialsCount} document(s)</strong> to prepare for the meeting.
            </p>
          </div>
        )}

        {/* Preparation Summary */}
        <div style={{ 
          marginBottom: '1.5rem',
          padding: '1rem',
          background: '#e8f5e9',
          border: '2px solid #4caf50',
          borderRadius: '8px',
        }}>
          <h3 style={{ 
            margin: '0 0 0.75rem 0', 
            fontSize: '1rem', 
            fontWeight: 600,
            color: '#2e7d32'
          }}>
            ✅ Preparation Complete
          </h3>
          <div style={{ fontSize: '0.875rem', lineHeight: '1.8', color: '#1b5e20' }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ minWidth: '140px', fontWeight: 600 }}>Status:</span>
              <span style={{ color: '#2e7d32', fontWeight: 600 }}>✓ Ready to participate</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ minWidth: '140px', fontWeight: 600 }}>Materials Analyzed:</span>
              <span>{materialsCount} document(s)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ minWidth: '140px', fontWeight: 600 }}>Memory Chunks:</span>
              <span>{memoryChunksCount} chunk(s) from knowledge base</span>
            </div>
          </div>
        </div>

        {/* Detailed Context */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ 
            margin: '0 0 0.75rem 0', 
            fontSize: '1rem', 
            fontWeight: 600 
          }}>
            📝 Prepared Context
          </h3>
          <pre
            style={{
              padding: '1rem',
              background: 'var(--bg-panel)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              fontSize: '0.875rem',
              fontFamily: 'ui-monospace, monospace',
              whiteSpace: 'pre-wrap',
              wordWrap: 'break-word',
              maxHeight: '300px',
              overflow: 'auto',
              lineHeight: '1.5',
            }}
          >
            {parsedContent.context || content}
          </pre>
        </div>

        {/* Agent Understanding Section */}
        <div style={{ 
          padding: '0.75rem 1rem',
          background: '#e3f2fd',
          border: '1px solid #2196f3',
          borderRadius: '8px',
          fontSize: '0.8125rem',
          color: '#0d47a1',
          marginBottom: '1.5rem'
        }}>
          <strong>💡 Agent's Understanding:</strong> This agent has reviewed the meeting context, analyzed {materialsCount} material(s), 
          and retrieved {memoryChunksCount} relevant memory chunk(s) to prepare for informed participation.
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button onClick={onClose} className={styles.btnPrimary} style={{ minWidth: '120px' }}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
