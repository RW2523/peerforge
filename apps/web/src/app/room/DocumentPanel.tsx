/**
 * DocumentPanel - Document view in debate room
 */
'use client';

import React from 'react';
import { useDocumentSync } from '@/lib/hooks/useDocumentSync';
import { useDocument } from '@/lib/hooks/useDocument';
import DocumentEditor from '@/components/document/DocumentEditor';
import DiagramSection from '@/components/document/DiagramSection';
import { SectionType, DocumentSection } from '@/lib/document/types';
import styles from './DocumentPanel.module.css';

interface DocumentPanelProps {
  debateId: string;
  documentId: string | null;
  userId: string;
  userName: string;
}

export default function DocumentPanel({
  debateId,
  documentId,
  userId,
  userName,
}: DocumentPanelProps) {
  const [document, setDocument] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);
  
  // Direct fetch instead of using hook
  React.useEffect(() => {
    if (!documentId) return;
    
    const fetchDoc = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/documents/${documentId}`);
        if (response.ok) {
          const data = await response.json();
          setDocument(data);
          console.log('📄 Document loaded:', data.title, data.sections?.length, 'sections');
        } else {
          console.error('Failed to fetch document:', response.statusText);
        }
      } catch (err) {
        console.error('Document fetch error:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchDoc();
    
    // Poll for updates every 3 seconds
    const interval = setInterval(fetchDoc, 3000);
    return () => clearInterval(interval);
  }, [documentId]);
  
  const { provider, connected, synced } = useDocumentSync(
    documentId,
    userId,
    userName
  );

  if (!documentId) {
    return (
      <div className={styles.panel}>
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>📄</span>
          <h3>No Document</h3>
          <p>Enable documentation in setup to create a shared document</p>
        </div>
      </div>
    );
  }

  if (loading || !document) {
    return (
      <div className={styles.panel}>
        <div className={styles.loading}>
          Loading document... (ID: {documentId})
          <br />
          <small>Check browser console for errors</small>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>{document?.title || 'Document'}</h2>
        <div className={styles.status}>
          <span className={connected ? styles.connected : styles.disconnected}>
            {connected ? '🟢' : '🔴'} {connected ? 'Connected' : 'Disconnected'}
          </span>
          {synced && <span className={styles.synced}>✓ Synced</span>}
        </div>
      </div>

      <div className={styles.sections}>
        {document?.sections.map((section: DocumentSection) => (
          <div key={section.section_id || section.id} className={styles.section}>
            <div className={styles.sectionHeader}>
              <h3>{section.section_title || section.title || 'Untitled Section'}</h3>
              <div className={styles.sectionMeta}>
                {section.assigned_agent_name && (
                  <span className={styles.assignedAgent}>
                    👤 {section.assigned_agent_name}
                  </span>
                )}
                {section.word_limit && (
                  <span className={styles.wordLimit}>
                    {section.word_count || 0}/{section.word_limit} words
                  </span>
                )}
              </div>
            </div>
            
            {section.section_type === 'diagram' ? (
              <DiagramSection
                mermaidCode={section.content || 'graph TD\n  A[Start]-->B[End]'}
                editable={false}
              />
            ) : section.content ? (
              <div style={{
                padding: '16px 0',
                color: '#1a1a1a',
                fontSize: '15px',
                lineHeight: '1.8',
                whiteSpace: 'pre-wrap'
              }}>
                {section.content}
              </div>
            ) : (
              <DocumentEditor
                provider={provider}
                sectionKey={section.section_key || section.key || 'default'}
                userName={userName}
                placeholder={`Write ${(section.section_title || section.title || 'section').toLowerCase()}...`}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
