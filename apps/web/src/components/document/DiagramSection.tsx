/**
 * DiagramSection - Mermaid diagram renderer for agent-generated diagrams
 */
'use client';

import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import styles from './DiagramSection.module.css';

interface DiagramSectionProps {
  mermaidCode: string;
  editable?: boolean;
  onUpdate?: (code: string) => void;
}

export default function DiagramSection({
  mermaidCode,
  editable = false,
  onUpdate,
}: DiagramSectionProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [code, setCode] = useState(mermaidCode);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: true,
      theme: 'dark',
      themeVariables: {
        primaryColor: '#3b82f6',
        primaryTextColor: '#fff',
        primaryBorderColor: '#2563eb',
        lineColor: '#64748b',
        secondaryColor: '#8b5cf6',
        tertiaryColor: '#10b981',
      },
    });
  }, []);

  useEffect(() => {
    if (!containerRef.current || !code || isEditing) return;

    const renderDiagram = async () => {
      try {
        setError(null);
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, code);
        
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to render diagram');
      }
    };

    renderDiagram();
  }, [code, isEditing]);

  const handleSave = () => {
    onUpdate?.(code);
    setIsEditing(false);
  };

  if (isEditing) {
    return (
      <div className={styles.editContainer}>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className={styles.codeEditor}
          rows={12}
        />
        <div className={styles.editActions}>
          <button onClick={handleSave} className={styles.btnSave}>
            Save
          </button>
          <button
            onClick={() => {
              setCode(mermaidCode);
              setIsEditing(false);
            }}
            className={styles.btnCancel}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {error ? (
        <div className={styles.error}>
          <span>⚠️ Invalid diagram syntax</span>
          <pre>{error}</pre>
        </div>
      ) : (
        <div ref={containerRef} className={styles.diagram} />
      )}
      
      {editable && (
        <button
          onClick={() => setIsEditing(true)}
          className={styles.btnEdit}
        >
          ✏️ Edit Code
        </button>
      )}
    </div>
  );
}
