'use client';

/**
 * CommitteeTwinBuilder — Pillar 2 (the moat).
 *
 * Name the people who'll actually sit on your panel. PeerForge pulls their REAL
 * publications, ingests them as grounded corpus, and builds a twin specialised
 * on each reviewer's own work — so the twin can quote their actual papers back
 * at you. You rehearse the specific review, not a generic one.
 */
import { useState } from 'react';
import { buildCommitteeTwins, CommitteeTwin, CommitteeTwinResponse } from '@/lib/api';
import styles from './CommitteeTwinBuilder.module.css';

interface Props {
  debateId: string;
}

interface Row {
  name: string;
  affiliation: string;
}

function TwinCard({ twin }: { twin: CommitteeTwin }) {
  const [showPrompt, setShowPrompt] = useState(false);
  return (
    <div className={styles.twin}>
      <div className={styles.twinHead}>
        <div>
          <span className={styles.twinName}>{twin.name}</span>
          {twin.affiliation && <span className={styles.twinAff}> · {twin.affiliation}</span>}
          <div className={styles.twinRole}>{twin.role}</div>
        </div>
        {twin.corpus_found ? (
          <span className={styles.corpusOk}>
            ✓ {twin.paper_count} paper(s) · {twin.chunks_ingested} chunks
          </span>
        ) : (
          <span className={styles.corpusNone}>no indexed corpus</span>
        )}
      </div>

      {twin.corpus_found ? (
        <>
          <ul className={styles.papers}>
            {twin.papers.map((p, i) => (
              <li key={i} className={styles.paper}>
                <span className={styles.paperTitle}>
                  {p.url ? (
                    <a href={p.url} target="_blank" rel="noreferrer">
                      {p.title}
                    </a>
                  ) : (
                    p.title
                  )}
                </span>
                <span className={styles.paperMeta}>
                  {p.year ?? 'n.d.'} · {p.venue || p.source}
                  {p.citation_count > 0 && ` · ${p.citation_count} cites`}
                </span>
              </li>
            ))}
          </ul>
          <button className={styles.promptToggle} onClick={() => setShowPrompt((s) => !s)}>
            {showPrompt ? 'Hide' : 'Show'} how this twin will interrogate you
          </button>
          {showPrompt && <pre className={styles.prompt}>{twin.system_prompt}</pre>}
        </>
      ) : (
        <p className={styles.note}>{twin.note}</p>
      )}
    </div>
  );
}

export default function CommitteeTwinBuilder({ debateId }: Props) {
  const [rows, setRows] = useState<Row[]>([{ name: '', affiliation: '' }]);
  const [topicHint, setTopicHint] = useState('');
  const [result, setResult] = useState<CommitteeTwinResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((r) => r.map((row, idx) => (idx === i ? { ...row, ...patch } : row)));
  const addRow = () => setRows((r) => (r.length >= 6 ? r : [...r, { name: '', affiliation: '' }]));
  const removeRow = (i: number) => setRows((r) => r.filter((_, idx) => idx !== i));

  const canBuild = rows.some((r) => r.name.trim().length >= 2) && !loading;

  const build = async () => {
    setLoading(true);
    setError(null);
    try {
      const reviewers = rows
        .filter((r) => r.name.trim().length >= 2)
        .map((r) => ({ name: r.name.trim(), affiliation: r.affiliation.trim() }));
      const res = await buildCommitteeTwins(debateId, reviewers, topicHint.trim());
      setResult(res);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.wrap}>
      <header className={styles.header}>
        <h3 className={styles.title}>Committee Twin</h3>
        <p className={styles.subtitle}>
          Name the reviewers who&apos;ll actually sit on your panel. PeerForge pulls their real
          publications and builds a twin that questions you from <em>their</em> body of work.
        </p>
      </header>

      <div className={styles.form}>
        {rows.map((row, i) => (
          <div key={i} className={styles.row}>
            <input
              className={styles.input}
              placeholder="Reviewer name (e.g. Yoshua Bengio)"
              value={row.name}
              onChange={(e) => setRow(i, { name: e.target.value })}
            />
            <input
              className={styles.input}
              placeholder="Affiliation (optional)"
              value={row.affiliation}
              onChange={(e) => setRow(i, { affiliation: e.target.value })}
            />
            {rows.length > 1 && (
              <button className={styles.removeBtn} onClick={() => removeRow(i)} title="Remove">
                ✕
              </button>
            )}
          </div>
        ))}
        <div className={styles.controls}>
          {rows.length < 6 && (
            <button className={styles.addBtn} onClick={addRow}>
              + Add reviewer
            </button>
          )}
          <input
            className={styles.hintInput}
            placeholder="Topic focus (optional) — biases toward their relevant papers"
            value={topicHint}
            onChange={(e) => setTopicHint(e.target.value)}
          />
          <button className={styles.buildBtn} disabled={!canBuild} onClick={build}>
            {loading ? 'Pulling publications…' : 'Build twins'}
          </button>
        </div>
      </div>

      {error && <div className={styles.error}>Could not build twins: {error}</div>}

      {result && (
        <div className={styles.results}>
          <div className={styles.summary}>
            Built <strong>{result.summary.built}</strong> twin(s) —{' '}
            <strong>{result.summary.with_corpus}</strong> grounded in a real corpus,{' '}
            {result.summary.papers_ingested} papers ingested.
          </div>
          {result.twins.map((t) => (
            <TwinCard key={t.twin_id} twin={t} />
          ))}
        </div>
      )}
    </div>
  );
}
