'use client';

import { useState, useRef, useEffect } from 'react';
import styles from './InterveneComposer.module.css';
import * as api from '@/lib/api';
import { WSCommandType, WSAckMessage } from '@/lib/wsClient';

interface InterveneComposerProps {
  debateId: string;
  participants: { name: string; id: string }[];
  sendCommand?: (command: WSCommandType, payload?: Record<string, any>) => Promise<WSAckMessage>;
}

export default function InterveneComposer({ debateId, participants, sendCommand }: InterveneComposerProps) {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = async () => {
    if (!message.trim() || loading) return;

    setLoading(true);
    setError(null);

    try {
      // Prefer WebSocket if available, fallback to REST
      if (sendCommand) {
        await sendCommand('intervene', {
          message: message.trim(),
          actor: 'Moderator'
        });
      } else {
        await api.intervene(debateId, {
          message: message.trim(),
        });
      }

      setMessage('');
      setShowMentions(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setMessage(value);

    // Check for @ mentions
    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = value.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');

    if (lastAtIndex !== -1 && lastAtIndex === textBeforeCursor.length - 1) {
      setShowMentions(true);
      setMentionFilter('');
    } else if (lastAtIndex !== -1) {
      const afterAt = textBeforeCursor.substring(lastAtIndex + 1);
      if (!/\s/.test(afterAt)) {
        setShowMentions(true);
        setMentionFilter(afterAt);
      } else {
        setShowMentions(false);
      }
    } else {
      setShowMentions(false);
    }
  };

  const insertMention = (name: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const cursorPos = textarea.selectionStart;
    const textBeforeCursor = message.substring(0, cursorPos);
    const textAfterCursor = message.substring(cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');

    const newText =
      message.substring(0, lastAtIndex) +
      `@${name} ` +
      textAfterCursor;

    setMessage(newText);
    setShowMentions(false);

    // Focus back on textarea
    setTimeout(() => {
      textarea.focus();
      const newCursorPos = lastAtIndex + name.length + 2;
      textarea.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  };

  const filteredParticipants = participants.filter((p) =>
    p.name.toLowerCase().includes(mentionFilter.toLowerCase())
  );

  return (
    <div className={styles.composer}>
      {error && (
        <div className={styles.error}>
          <span>⚠</span>
          <span>{error}</span>
        </div>
      )}

      <div className={styles.inputWrapper}>
        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyPress}
          placeholder="Type @ to mention participants, ⌘/Ctrl+Enter to send"
          disabled={loading}
          rows={3}
        />

        {showMentions && filteredParticipants.length > 0 && (
          <div className={styles.mentionDropdown}>
            {filteredParticipants.map((participant) => (
              <button
                key={participant.id}
                className={styles.mentionItem}
                onClick={() => insertMention(participant.name)}
              >
                <span className={styles.mentionIcon}>@</span>
                <span>{participant.name}</span>
              </button>
            ))}
          </div>
        )}

        <div className={styles.actions}>
          <span className={styles.hint}>
            {message.length > 0 && `${message.length} chars`}
          </span>
          <button
            onClick={handleSend}
            disabled={!message.trim() || loading}
            className={styles.sendBtn}
          >
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
