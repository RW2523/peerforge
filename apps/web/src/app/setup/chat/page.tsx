'use client';

/**
 * Conversational session setup.
 *
 * Instead of filling in six steps, the researcher describes what they want
 * reviewed. Each reply carries a full proposal, so the panel on screen is
 * always what would be created — there is no hidden partial state.
 */
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import AppNav from '@/components/layout/AppNav';
import { useWorkspace } from '@/components/WorkspaceProvider';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import * as api from '@/lib/api';
import { SetupProposal, applySetup, converseSetup } from '@/lib/organizations';
import styles from './chat.module.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  grounded?: boolean;
  passages?: number;
}

const OPENER =
  "Tell me what you'd like reviewed. What is the work, and what kind of scrutiny do you want?";

export default function ConversationalSetupPage() {
  const router = useRouter();
  const { workspaceId } = useWorkspace();
  const { apiKey, hasKey } = useOpenRouterKey();

  const [debateId, setDebateId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: OPENER },
  ]);
  const [input, setInput] = useState('');
  const [proposal, setProposal] = useState<SetupProposal | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const feedRef = useRef<HTMLDivElement>(null);

  // A session must exist before anything can be attached to or grounded in it.
  useEffect(() => {
    if (!workspaceId || debateId) return;
    api
      .createDebate(workspaceId, 'Untitled review session')
      .then((d: any) => setDebateId(d.debate_id))
      .catch((err: any) => setError(err?.message ?? 'Could not start a session'));
  }, [workspaceId, debateId]);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, busy]);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy || !debateId) return;

    if (!hasKey) {
      setError('An OpenRouter key is required. Add one in Settings.');
      return;
    }

    setError(null);
    setBusy(true);
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInput('');

    try {
      const result = await converseSetup(debateId, text, history, apiKey);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: result.reply || '(no reply)',
          grounded: result.grounded,
          passages: result.passages_used,
        },
      ]);
      if (result.proposal) setProposal(result.proposal);
      setReady(result.ready);
    } catch (err: any) {
      setError(err?.message ?? 'That turn failed');
    } finally {
      setBusy(false);
    }
  };

  const launch = async () => {
    if (!debateId || !proposal || applying) return;
    setApplying(true);
    setError(null);
    try {
      await applySetup(debateId, proposal);
      router.push(`/room?debate=${debateId}`);
    } catch (err: any) {
      setError(err?.message ?? 'Could not create the session');
      setApplying(false);
    }
  };

  return (
    <>
      <AppNav />
      <main className={styles.wrap}>
        <div className={styles.chat}>
          <header className={styles.head}>
            <h1 className={styles.h1}>Set up a review session</h1>
            <p className={styles.sub}>
              Describe your work in your own words. Upload a document first if you
              want the panel grounded in it.
            </p>
          </header>

          <div className={styles.feed} ref={feedRef} role="log" aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? styles.user : styles.assistant}>
                <div className={styles.bubble}>{m.content}</div>
                {m.role === 'assistant' && m.passages !== undefined && (
                  <div className={styles.meta}>
                    {m.grounded
                      ? `Read ${m.passages} passage${m.passages === 1 ? '' : 's'} from your document`
                      : 'No document consulted'}
                  </div>
                )}
              </div>
            ))}
            {busy && (
              <div className={styles.assistant}>
                <div className={styles.bubble} aria-live="polite">Thinking…</div>
              </div>
            )}
          </div>

          {error && <div className={styles.error} role="alert">{error}</div>}

          <form className={styles.composer} onSubmit={send}>
            <label className={styles.srOnly} htmlFor="setup-input">
              Describe what you want reviewed
            </label>
            <textarea
              id="setup-input"
              className={styles.input}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send(e as any);
              }}
              placeholder="I have a paper on…"
              rows={2}
              disabled={!debateId}
            />
            <button className={styles.send} type="submit" disabled={busy || !input.trim() || !debateId}>
              {busy ? 'Sending…' : 'Send'}
            </button>
          </form>
        </div>

        <aside className={styles.panel}>
          <h2 className={styles.h2}>Proposed session</h2>

          {!proposal ? (
            <p className={styles.muted}>
              Your panel will appear here as we talk, and you can launch it once
              it looks right.
            </p>
          ) : (
            <>
              <div className={styles.field}>
                <span className={styles.label}>Title</span>
                <input
                  className={styles.editable}
                  value={proposal.title}
                  onChange={(e) => setProposal({ ...proposal, title: e.target.value })}
                />
              </div>

              <div className={styles.field}>
                <span className={styles.label}>What the panel evaluates</span>
                <textarea
                  className={styles.editable}
                  rows={3}
                  value={proposal.problem_statement}
                  onChange={(e) =>
                    setProposal({ ...proposal, problem_statement: e.target.value })
                  }
                />
              </div>

              <div className={styles.field}>
                <span className={styles.label}>Reviewers ({proposal.panel.length})</span>
                <ul className={styles.reviewers}>
                  {proposal.panel.map((m, i) => (
                    <li key={i} className={styles.reviewer}>
                      <div className={styles.reviewerName}>{m.name}</div>
                      <div className={styles.reviewerRole}>{m.role}</div>
                      {m.focus && <div className={styles.muted}>{m.focus}</div>}
                    </li>
                  ))}
                </ul>
              </div>

              <div className={styles.field}>
                <span className={styles.label}>Rounds</span>
                <input
                  className={styles.editable}
                  type="number"
                  min={1}
                  max={10}
                  value={proposal.rounds}
                  onChange={(e) =>
                    setProposal({ ...proposal, rounds: Number(e.target.value) || 1 })
                  }
                />
              </div>

              <button
                className={styles.launch}
                onClick={launch}
                disabled={applying || proposal.panel.length < 2}
              >
                {applying ? 'Creating…' : 'Create this session'}
              </button>
              {!ready && (
                <p className={styles.muted}>
                  Keep talking to refine it, or launch now if this already looks right.
                </p>
              )}
              {proposal.panel.length < 2 && (
                <p className={styles.muted}>A panel needs at least two reviewers.</p>
              )}
            </>
          )}
        </aside>
      </main>
    </>
  );
}
