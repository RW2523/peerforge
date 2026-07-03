'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useOpenRouterKey } from '@/hooks/useOpenRouterKey';
import * as api from '@/lib/api';
import PracticeJourneyCard from './PracticeJourneyCard';
import AcademicAssessmentCard from './AcademicAssessmentCard';
import styles from './SummaryReport.module.css';

interface SummaryReportProps {
  debateId: string;
  agendaData: {
    items: { id: string; text: string }[];
    outcome: { desired: string; criteria: string[] };
  };
  /** Switches the room to the Practice Q&A tab. */
  onStartPractice?: () => void;
}

interface Summary {
  summary: string;
  minutes_of_meeting?: string;
  minutes?: string;
  action_items: {
    description: string;
    owner: string;
    priority: string;
  }[];
}

export default function SummaryReport({ debateId, agendaData, onStartPractice }: SummaryReportProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const { apiKey, hasKey } = useOpenRouterKey();
  const router = useRouter();

  const generateSummary = async () => {
    if (!apiKey) {
      router.push('/settings');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await api.generateSummary(
        debateId,
        {
          openrouter_api_key: apiKey,
          model_id: 'anthropic/claude-sonnet-4-5',
        },
        apiKey
      );
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate summary');
    } finally {
      setLoading(false);
    }
  };

  if (!summary) {
    return (
      <div className={styles.generateWrap}>
        <PracticeJourneyCard debateId={debateId} onStartPractice={onStartPractice} />
        <AcademicAssessmentCard key={debateId} debateId={debateId} triggerSource="panel_discussion" autoGenerate />
        <div className={styles.generatePanel}>
        <div className={styles.icon} />
        <h3>Generate Feedback Report</h3>
        <p>
          Create a structured feedback report with strengths, areas to improve, and concrete recommendations using AI.
        </p>

        {!apiKey && (
          <div className={styles.warning}>
            <span>⚠</span>
            <span>You need to set your OpenRouter API key first.</span>
          </div>
        )}

        {error && (
          <div className={styles.error}>
            <span>⚠</span>
            <span>{error}</span>
          </div>
        )}

        <button
          onClick={generateSummary}
          disabled={loading}
          className={styles.generateBtn}
        >
          {loading ? 'Generating...' : 'Generate Feedback Report'}
        </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.report}>
      <div className={styles.reportHeader}>
        <h2>Review Session Report</h2>
        <div className={styles.headerActions}>
          <button
            onClick={() => router.push('/history')}
            className={styles.historyBtn}
          >
            📜 View in History
          </button>
          <button
            onClick={() => setSummary(null)}
            className={styles.regenerateBtn}
          >
            Regenerate
          </button>
        </div>
      </div>

      {/* Preparation funnel — the report is not the end of the journey */}
      <PracticeJourneyCard debateId={debateId} onStartPractice={onStartPractice} />

      {/* Ten-dimension academic assessment */}
      <AcademicAssessmentCard key={debateId} debateId={debateId} triggerSource="panel_discussion" autoGenerate />

      {/* Agenda & Outcome Review */}
      {(agendaData.items.length > 0 || agendaData.outcome.desired) && (
        <section className={styles.section}>
          <h3>Session Context</h3>
          
          {agendaData.items.length > 0 && (
            <div className={styles.agendaReview}>
              <h4>Agenda</h4>
              <ol>
                {agendaData.items.map((item, index) => (
                  <li key={item.id}>{item.text}</li>
                ))}
              </ol>
            </div>
          )}

          {agendaData.outcome.desired && (
            <div className={styles.outcomeReview}>
              <h4>Intended Outcome</h4>
              <p>{agendaData.outcome.desired}</p>
              
              {agendaData.outcome.criteria.length > 0 && (
                <>
                  <h5>Success Criteria</h5>
                  <ul>
                    {agendaData.outcome.criteria.map((criterion, index) => (
                      <li key={index}>{criterion}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </section>
      )}

      {/* Summary */}
      <section className={styles.section}>
        <h3>Executive Summary</h3>
        <div className={styles.summaryBox}>
          {summary.summary}
        </div>
      </section>

      {/* Minutes */}
      <section className={styles.section}>
        <h3>Minutes of Meeting</h3>
        <div className={styles.minutesBox}>
          {summary.minutes_of_meeting || summary.minutes || 'No minutes available'}
        </div>
      </section>

      {/* Action Items */}
      <section className={styles.section}>
        <h3>Action Items</h3>
        <div className={styles.actionItems}>
          {summary.action_items && summary.action_items.length > 0 ? (
            summary.action_items.map((item, index) => (
              <div
                key={index}
                className={`${styles.actionItem} ${styles[`priority-${item.priority.toLowerCase()}`]}`}
              >
                <div className={styles.actionDesc}>{item.description}</div>
                <div className={styles.actionMeta}>
                  <span className={styles.owner}>👤 {item.owner}</span>
                  <span className={styles.priority}>
                    {item.priority.toUpperCase()}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <p className={styles.empty}>No action items identified</p>
          )}
        </div>
      </section>
    </div>
  );
}
