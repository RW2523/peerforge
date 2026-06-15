'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import * as api from '@/lib/api';
import styles from './CreateDebateCard.module.css';

interface CreateDebateCardProps {
  workspaceId: string;
  onDebateCreated?: () => void;
}

export default function CreateDebateCard({ workspaceId, onDebateCreated }: CreateDebateCardProps) {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [problemStatement, setProblemStatement] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = () => {
    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    // Store in sessionStorage to pre-fill setup wizard
    sessionStorage.setItem('debate_draft', JSON.stringify({
      title: title.trim(),
      problemStatement: problemStatement.trim(),
      timestamp: Date.now()
    }));

    // Navigate to setup wizard to assemble panel
    router.push('/setup');
  };

  return (
    <div className={styles.card}>
      <h2>Start a New Review Session</h2>
      <p className={styles.description}>Name your research project and describe the core research question — the more specific, the better the panel preparation</p>

      {error && (
        <div className={styles.error}>
          <span>⚠</span>
          <span>{error}</span>
        </div>
      )}

      <div className={styles.form}>
        <label>
          Project Title
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Transformer-based models for protein structure prediction"
            disabled={loading}
          />
        </label>

        <label>
          Research Question / Abstract <span className={styles.optional}>(optional)</span>
          <textarea
            value={problemStatement}
            onChange={(e) => setProblemStatement(e.target.value)}
            placeholder="Describe your research question, hypothesis, or the work you want reviewed. Include methodology or key contributions if known."
            rows={4}
            disabled={loading}
          />
        </label>

        <button
          onClick={handleCreate}
          disabled={!title.trim()}
          className={styles.btnPrimary}
        >
          Next: Configure Review Panel →
        </button>
      </div>
    </div>
  );
}
