/**
 * DocumentEditor - Main collaborative editor using Tiptap
 */
'use client';

import React, { useEffect } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Collaboration from '@tiptap/extension-collaboration';
import CollaborationCursor from '@tiptap/extension-collaboration-cursor';
import { DocumentCollaborationProvider } from '@/lib/document/yjs-provider';
import { AgentPresence } from '@/lib/document/types';
import styles from './DocumentEditor.module.css';

interface DocumentEditorProps {
  provider: DocumentCollaborationProvider | null;
  sectionKey: string;
  userName?: string;
  readOnly?: boolean;
  placeholder?: string;
  onUpdate?: (content: string) => void;
}

export default function DocumentEditor({
  provider,
  sectionKey,
  userName,
  readOnly = false,
  placeholder = 'Start writing...',
  onUpdate,
}: DocumentEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Collaboration.configure({
        document: provider?.getYDoc(),
        field: sectionKey,
      }),
      CollaborationCursor.configure({
        provider: provider?.getProvider() as any,
        user: {
          name: userName || 'Anonymous',
          color: '#3b82f6',
        },
      }),
    ],
    editable: !readOnly,
    content: '',
    onUpdate: ({ editor }) => {
      onUpdate?.(editor.getHTML());
    },
  });

  useEffect(() => {
    if (editor && provider) {
      editor.setEditable(!readOnly);
    }
  }, [editor, provider, readOnly]);

  if (!editor) {
    return <div className={styles.loading}>Loading editor...</div>;
  }

  return (
    <div className={styles.editorWrapper}>
      <EditorContent editor={editor} className={styles.editor} />
    </div>
  );
}
