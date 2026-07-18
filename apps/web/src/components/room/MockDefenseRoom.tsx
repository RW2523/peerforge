'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import styles from './MockDefenseRoom.module.css';
import { displayPersona } from '@/lib/persona';
import AcademicAssessmentCard from './AcademicAssessmentCard';
import { useSpeechSynthesis, roleToVoiceId } from '@/hooks/useSpeechSynthesis';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import {
  analyzeResearch,
  generateDefenseQuestions,
  addFollowUpQuestion,
  suggestPersonas,
  submitAnswer,
  generateReadinessReport,
  getResearchProfile,
  getDefenseQuestions,
  getReadinessReport,
  type ResearchProfile,
  type DefenseQuestion,
  type AnswerEvaluation,
  type ReadinessReport,
  type ReasoningMode,
  type SuggestedPersona,
  type ChallengeSeverity,
  type PracticeMode,
} from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

type Phase =
  | 'setup'
  | 'analyzing'
  | 'suggesting'
  | 'questions'
  | 'defense'
  | 'evaluated'
  | 'report'
  | 'error';

interface ModeOption {
  id: ReasoningMode;
  label: string;
  description: string;
  costHint: string;
}

const MODE_OPTIONS: ModeOption[] = [
  {
    id: 'light',
    label: 'Light',
    description: 'Single fast model for all tasks. Ideal for practice and iteration.',
    costHint: '~$0.01–0.05 / session',
  },
  {
    id: 'medium',
    label: 'Medium',
    description: 'Different models per role. Balanced quality and cost.',
    costHint: '~$0.10–0.40 / session',
  },
  {
    id: 'heavy',
    label: 'Heavy',
    description: 'Frontier models for every activity. Production-grade depth.',
    costHint: '~$1–5 / session',
  },
];

// ── Component ──────────────────────────────────────────────────────────────

interface Props {
  debateId: string;
  openrouterKey: string;
  /** Start with voice mode on (e.g. from the History "Voice" shortcut). */
  initialVoice?: boolean;
}

const SEVERITY_OPTIONS: { id: ChallengeSeverity; label: string; hint: string }[] = [
  { id: 'gentle', label: 'Gentle', hint: 'Supportive, confidence-building' },
  { id: 'standard', label: 'Standard', hint: 'A fair, balanced committee' },
  { id: 'rigorous', label: 'Rigorous', hint: 'Demanding; probes every claim' },
  { id: 'hostile', label: 'Hostile', hint: 'Adversarial worst-case examiner' },
];

const PRACTICE_MODE_OPTIONS: { id: PracticeMode; label: string; hint: string }[] = [
  { id: 'thesis_defense', label: 'Thesis defense', hint: 'Full committee, completed work' },
  { id: 'proposal_defense', label: 'Proposal defense', hint: 'Gap, plan & feasibility' },
  { id: 'conference_qa', label: 'Conference Q&A', hint: 'Sharp, high-level audience' },
  { id: 'journal_review', label: 'Journal review', hint: 'Reviewers assess for publication' },
];

export default function MockDefenseRoom({ debateId, openrouterKey, initialVoice = false }: Props) {
  const [mode, setMode]       = useState<ReasoningMode>('medium');
  const [severity, setSeverity] = useState<ChallengeSeverity>('standard');
  const [practiceMode, setPracticeMode] = useState<PracticeMode>('thesis_defense');
  const [phase, setPhase]     = useState<Phase>('setup');
  const [error, setError]     = useState('');

  // Voice mode — TTS reads questions/feedback, STT dictates into the answer box.
  const tts = useSpeechSynthesis();
  const stt = useSpeechRecognition();
  const [voiceOn, setVoiceOn] = useState(initialVoice);
  const capturingRef = useRef(false);
  // Delivery tracking (voice mode): accumulate spoken seconds across dictation
  // spans for the current answer, then derive pace / fillers / confidence.
  const speakStartRef = useRef<number | null>(null);
  const speakSecondsRef = useRef(0);
  const [delivery, setDelivery] = useState<{ wpm: number; fillers: number; confidence: number } | null>(null);

  const [profile, setProfile]         = useState<ResearchProfile | null>(null);
  const [personas, setPersonas]       = useState<SuggestedPersona[]>([]);
  const [questions, setQuestions]     = useState<DefenseQuestion[]>([]);
  const [qIndex, setQIndex]           = useState(0);
  const [evaluation, setEvaluation]   = useState<AnswerEvaluation | null>(null);
  const [report, setReport]           = useState<ReadinessReport | null>(null);
  const [answerText, setAnswerText]   = useState('');
  const [submitting, setSubmitting]   = useState(false);
  const [answeredIds, setAnsweredIds] = useState<Set<string>>(new Set());
  const [showProfile, setShowProfile] = useState(false);

  // Restore existing session data on mount
  useEffect(() => {
    (async () => {
      try {
        const p = await getResearchProfile(debateId);
        setProfile(p);
        if (p.status === 'complete') {
          const qRes = await getDefenseQuestions(debateId);
          if (qRes.count > 0) {
            setQuestions(qRes.questions);
            try {
              const r = await getReadinessReport(debateId);
              setReport(r);
              setPhase('report');
            } catch {
              setPhase('questions');
            }
          } else {
            setPhase('setup');
          }
        }
      } catch {
        // no profile yet — remain on setup
      }
    })();
  }, [debateId]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const endSpeakSpan = useCallback(() => {
    if (speakStartRef.current != null) {
      speakSecondsRef.current += (Date.now() - speakStartRef.current) / 1000;
      speakStartRef.current = null;
    }
  }, []);

  const handleAnalyzeAndSuggest = useCallback(async () => {
    if (!openrouterKey) {
      setError('OpenRouter API key is required. Add it in Settings.');
      setPhase('error');
      return;
    }
    setError('');
    setPhase('analyzing');
    try {
      const res = await analyzeResearch(debateId, openrouterKey, mode);
      setProfile(res.profile);

      setPhase('suggesting');
      const pRes = await suggestPersonas(debateId, openrouterKey, mode);
      setPersonas(pRes.personas);

      setPhase('questions');
    } catch (e: any) {
      setError(e.message || 'Analysis failed');
      setPhase('error');
    }
  }, [debateId, openrouterKey, mode]);

  const handleGenerateQuestions = useCallback(async () => {
    setError('');
    setPhase('analyzing');
    try {
      const res = await generateDefenseQuestions(debateId, openrouterKey, 15, mode, '', severity, practiceMode);
      setQuestions(res.questions);
      setQIndex(0);
      setPhase('defense');
    } catch (e: any) {
      setError(e.message || 'Question generation failed');
      setPhase('error');
    }
  }, [debateId, openrouterKey, mode, severity, practiceMode]);

  const handleSubmitAnswer = useCallback(async () => {
    if (!answerText.trim() || submitting) return;
    const q = questions[qIndex];
    if (!q) return;
    setSubmitting(true);
    setError('');
    // Delivery metrics (voice mode only) — pace, fillers, ASR confidence.
    endSpeakSpan();
    const spokenSeconds = speakSecondsRef.current;
    speakSecondsRef.current = 0;  // consume this answer's speaking time so it can't leak to the next
    if (voiceOn && spokenSeconds > 2) {
      const words = answerText.trim().split(/\s+/).filter(Boolean);
      const wpm = Math.round((words.length / spokenSeconds) * 60);
      const fillers = (answerText.toLowerCase().match(
        /\b(um+|uh+|er+|like|you know|basically|actually|kind of|sort of|i mean)\b/g) || []).length;
      setDelivery({ wpm, fillers, confidence: Math.round((stt.confidence || 0) * 100) });
    } else {
      setDelivery(null);
    }
    try {
      const ev = await submitAnswer(debateId, q.question_id, answerText, openrouterKey, mode, '', severity);
      setEvaluation(ev);
      setAnsweredIds(prev => new Set(prev).add(q.question_id));
      setPhase('evaluated');
    } catch (e: any) {
      setError(e.message || 'Evaluation failed');
    } finally {
      setSubmitting(false);
    }
  }, [answerText, debateId, openrouterKey, mode, severity, questions, qIndex, submitting, voiceOn, endSpeakSpan, stt.confidence]);

  const handleNextQuestion = useCallback(() => {
    setAnswerText('');
    setEvaluation(null);
    setDelivery(null);
    speakSecondsRef.current = 0;
    const next = qIndex + 1;
    if (next >= questions.length) {
      setPhase('questions');
    } else {
      setQIndex(next);
      setPhase('defense');
    }
  }, [qIndex, questions.length]);

  // Close the challenge loop: persist the follow-up as a real question and
  // drop the student straight back into answering it (spoken in voice mode).
  const handleAnswerFollowUp = useCallback(async () => {
    if (!evaluation?.follow_up_question) return;
    const parent = questions[qIndex];
    if (!parent) return;
    setSubmitting(true);
    setError('');
    try {
      const fq = await addFollowUpQuestion(debateId, parent.question_id, evaluation.follow_up_question);
      setQuestions(prev => {
        const nextList = [...prev];
        nextList.splice(qIndex + 1, 0, fq);
        return nextList;
      });
      setQIndex(qIndex + 1);
      setAnswerText('');
      setEvaluation(null);
      setDelivery(null);
      speakSecondsRef.current = 0;
      setPhase('defense');
    } catch (e: any) {
      setError(e.message || 'Could not start the follow-up');
    } finally {
      setSubmitting(false);
    }
  }, [evaluation, questions, qIndex, debateId]);

  const handleGenerateReport = useCallback(async () => {
    setError('');
    setPhase('analyzing');
    try {
      const r = await generateReadinessReport(debateId, openrouterKey, mode);
      setReport(r);
      setPhase('report');
    } catch (e: any) {
      setError(e.message || 'Report generation failed');
      setPhase('error');
    }
  }, [debateId, openrouterKey, mode]);

  // ── Shared values ──────────────────────────────────────────────────────────

  const currentQuestion = questions[qIndex] ?? null;
  const answeredCount   = answeredIds.size;
  const modeInfo        = MODE_OPTIONS.find(m => m.id === mode)!;

  // ── Voice behaviours ───────────────────────────────────────────────────────

  const speakCurrentQuestion = useCallback(() => {
    if (!voiceOn || !tts.isSupported || !currentQuestion) return;
    tts.speak(
      `${displayPersona(currentQuestion.persona)} asks: ${currentQuestion.question_text}`,
      roleToVoiceId(currentQuestion.persona),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceOn, currentQuestion, tts.isSupported]);

  // Read the question aloud when it appears; read brief feedback after evaluation.
  useEffect(() => {
    if (phase === 'defense') speakCurrentQuestion();
    else if (phase === 'evaluated' && voiceOn && tts.isSupported && evaluation?.strength) {
      tts.speak(`Here is your feedback. ${evaluation.strength}`, 'advisor');
    }
    return () => { tts.cancel(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tts is a new object each render; the booleans/values it reads are listed
  }, [phase, qIndex, voiceOn, evaluation, tts.isSupported, speakCurrentQuestion]);

  const appendTranscript = useCallback(() => {
    const text = `${stt.finalTranscript} ${stt.interimTranscript}`.trim();
    if (text) setAnswerText(prev => (prev ? `${prev.trimEnd()} ` : '') + text);
    stt.resetTranscript();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stt.finalTranscript, stt.interimTranscript]);

  const handleMicClick = useCallback(() => {
    if (stt.isListening) {
      capturingRef.current = false;
      stt.stopListening();
      endSpeakSpan();
      appendTranscript();
    } else {
      tts.cancel();
      capturingRef.current = true;
      speakStartRef.current = Date.now();
      stt.resetTranscript();
      stt.startListening();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stt.isListening, appendTranscript, endSpeakSpan]);

  // Recognition can end on its own (silence) — capture whatever was said.
  useEffect(() => {
    if (capturingRef.current && !stt.isListening && stt.finalTranscript.trim()) {
      capturingRef.current = false;
      endSpeakSpan();
      appendTranscript();
    }
  }, [stt.isListening, stt.finalTranscript, appendTranscript, endSpeakSpan]);

  const voiceToggle = (
    <button
      className={`${styles.toggleBtn} ${voiceOn ? styles.voiceOn : ''}`}
      onClick={() => {
        if (voiceOn) { tts.cancel(); if (stt.isListening) stt.stopListening(); }
        setVoiceOn(v => !v);
      }}
      title="Voice mode — questions are read aloud and you can dictate answers"
    >
      {voiceOn ? '🎤 Voice on' : '🎤 Voice off'}
    </button>
  );

  // ── Setup ──────────────────────────────────────────────────────────────────

  if (phase === 'setup') {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <h2 className={styles.title}>Practice Q&amp;A Session</h2>
          <p className={styles.subtitle}>
            Select a reasoning mode, then analyse your uploaded research to generate a
            tailored review panel and practice questions.
          </p>
        </div>

        {!openrouterKey && (
          <div className={styles.keyWarning}>
            <span className={styles.keyWarningIcon}>🔑</span>
            <div>
              <strong>API Key Required</strong>
              <p>
                Add your OpenRouter API key in{' '}
                <a href="/settings">Settings</a>
                {' '}to run the AI review session.
              </p>
            </div>
          </div>
        )}

        <div className={styles.section}>
          <div className={styles.sectionTitle}>Reasoning Mode</div>
          <div className={styles.modeGrid}>
            {MODE_OPTIONS.map(opt => (
              <button
                key={opt.id}
                className={`${styles.modeCard} ${mode === opt.id ? styles.modeCardActive : ''}`}
                onClick={() => setMode(opt.id)}
              >
                <div className={styles.modeLabel}>{opt.label}</div>
                <div className={styles.modeDesc}>{opt.description}</div>
                <div className={styles.modeCost}>{opt.costHint}</div>
              </button>
            ))}
          </div>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>What are you rehearsing?</div>
          <p className={styles.hint}>The mode reframes your research for a different evaluation — changing what the panel emphasises.</p>
          <div className={styles.severityRow}>
            {PRACTICE_MODE_OPTIONS.map(opt => (
              <button
                key={opt.id}
                className={`${styles.severityCard} ${practiceMode === opt.id ? styles.severityActive : ''}`}
                onClick={() => setPracticeMode(opt.id)}
              >
                <div className={styles.severityLabel}>{opt.label}</div>
                <div className={styles.severityHint}>{opt.hint}</div>
              </button>
            ))}
          </div>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>Challenge Level</div>
          <p className={styles.hint}>How hard should the panel push? This changes both what they ask and how strictly they grade.</p>
          <div className={styles.severityRow}>
            {SEVERITY_OPTIONS.map(opt => (
              <button
                key={opt.id}
                className={`${styles.severityCard} ${severity === opt.id ? styles.severityActive : ''} ${opt.id === 'hostile' ? styles.severityHostile : ''}`}
                onClick={() => setSeverity(opt.id)}
              >
                <div className={styles.severityLabel}>{opt.label}</div>
                <div className={styles.severityHint}>{opt.hint}</div>
              </button>
            ))}
          </div>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>AI Review Panel Roles</div>
          <p className={styles.hint}>
            After analysis, the system generates 6 panel members tailored to your
            research domain. Each member stays within their assigned role.
          </p>
          <div className={styles.personaPreviewGrid}>
            {[
              { role: 'Advisor',               desc: 'Alignment with research goals' },
              { role: 'Methodology Professor', desc: 'Methods, baselines, validity' },
              { role: 'Domain Expert',         desc: 'Domain correctness, contribution' },
              { role: 'Skeptical Reviewer',    desc: 'Weak claims, unsupported assumptions' },
              { role: 'Friendly Professor',    desc: 'Clarity and confidence-building' },
              { role: 'Independent Reviewer',  desc: 'Impartial, degree-standard scrutiny' },
            ].map(p => (
              <div key={p.role} className={styles.personaPreviewCard}>
                <div className={styles.personaRole}>{p.role}</div>
                <div className={styles.personaDesc}>{p.desc}</div>
              </div>
            ))}
          </div>
        </div>

        <button
          className={styles.primaryBtn}
          onClick={handleAnalyzeAndSuggest}
          disabled={!openrouterKey}
          style={{ opacity: openrouterKey ? 1 : 0.45, cursor: openrouterKey ? 'pointer' : 'not-allowed' }}
        >
          Analyse Research and Build Review Panel
        </button>
      </div>
    );
  }

  // ── Loading ────────────────────────────────────────────────────────────────

  if (phase === 'analyzing' || phase === 'suggesting') {
    const steps = [
      { key: 'analyzing', label: 'Analysing research materials…', detail: 'Extracting research problem, methodology, contributions, and weak areas.' },
      { key: 'suggesting', label: 'Generating reviewer personas…', detail: 'Tailoring 6 AI panel members to your research domain and methodology.' },
    ];
    const current = steps.find(s => s.key === phase) || steps[0];
    return (
      <div className={styles.container}>
        <div className={styles.loadingBox}>
          <div className={styles.spinner} />
          <p className={styles.loadingText}>{current.label}</p>
          <p className={styles.loadingHint}>{modeInfo.label} mode · {current.detail}</p>
          <div style={{ display: 'flex', gap: '8px', marginTop: '20px', justifyContent: 'center' }}>
            {steps.map((s, i) => (
              <div key={s.key} style={{
                width: 10, height: 10, borderRadius: '50%',
                background: s.key === phase ? 'var(--accent, #4f46e5)' : 'var(--border, #ccc)',
                transition: 'background 0.3s',
              }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────────

  if (phase === 'error') {
    return (
      <div className={styles.container}>
        <div className={styles.errorBox}>
          <h3>Something went wrong</h3>
          <p style={{ color: 'var(--text-2)', fontSize: '0.9rem', marginBottom: '16px' }}>{error}</p>
          {error.toLowerCase().includes('key') || error.toLowerCase().includes('unauthorized') ? (
            <a href="/settings" className={styles.settingsLink}>
              🔑 Go to Settings
            </a>
          ) : null}
          <button className={styles.secondaryBtn} onClick={() => { setError(''); setPhase('setup'); }}>
            Back to Setup
          </button>
        </div>
      </div>
    );
  }

  // ── Questions overview ─────────────────────────────────────────────────────

  if (phase === 'questions') {
    return (
      <div className={styles.container}>
        <div className={styles.modeBadgeRow}>
          <span className={styles.modeBadge}>{modeInfo.label}</span>
          {severity !== 'standard' && <span className={styles.sevBadge}>{severity}</span>}
          {voiceToggle}
          {answeredCount > 0 && (
            <span className={styles.progressBadge}>
              {answeredCount} / {questions.length} answered
            </span>
          )}
        </div>

        {/* Suggested review panel */}
        {personas.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Your Review Panel</div>
            <div className={styles.personaGrid}>
              {personas.map((p, i) => (
                <div key={i} className={styles.personaCard}>
                  <div className={styles.personaCardRole}>{displayPersona(p.role)}</div>
                  <div className={styles.personaCardName}>{p.name}</div>
                  <div className={styles.personaCardExpertise}>{p.expertise}</div>
                  <div className={styles.personaCardFocus}>{p.focus_area}</div>
                  <div className={styles.personaModel}>
                    <code>{p.model_id}</code>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Research profile */}
        {profile && (
          <div className={styles.section}>
            <button
              className={styles.toggleBtn}
              onClick={() => setShowProfile(v => !v)}
            >
              {showProfile ? 'Hide' : 'Show'} Research Profile
            </button>
            {showProfile && (
              <div className={styles.profileGrid}>
                {[
                  ['Research Problem', profile.research_problem],
                  ['Hypothesis',       profile.hypothesis],
                  ['Main Claim',       profile.main_claim],
                  ['Methodology',      profile.methodology],
                  ['Results',          profile.results],
                  ['Contribution',     profile.contribution],
                  ['Limitations',      profile.limitations],
                  ['Future Work',      profile.future_work],
                ].map(([label, val]) =>
                  val && val !== 'Insufficient evidence in uploaded materials.' ? (
                    <div key={label as string} className={styles.profileItem}>
                      <div className={styles.profileLabel}>{label}</div>
                      <div className={styles.profileValue}>{val as string}</div>
                    </div>
                  ) : null)}
              </div>
            )}
          </div>
        )}

        {/* Contradiction detector — internal inconsistencies found in the document */}
        {profile?.contradictions && profile.contradictions.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>⚠ Possible Internal Contradictions</div>
            <p className={styles.hint}>
              The panel found statements in your own document that appear to conflict — expect to be
              pressed on these. Resolve them before the real review.
            </p>
            {profile.contradictions.map((c, i) => (
              <div key={i} className={styles.contradiction}>
                <div className={styles.contraPair}>
                  <span className={styles.contraA}>“{c.statement_a}”</span>
                  <span className={styles.contraVs}>vs</span>
                  <span className={styles.contraB}>“{c.statement_b}”</span>
                </div>
                <div className={styles.contraWhy}>{c.explanation}</div>
              </div>
            ))}
          </div>
        )}

        {/* Question list */}
        {questions.length > 0 ? (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>
              Review Questions &mdash; {questions.length} total
            </div>
            <div className={styles.questionList}>
              {questions.map((q, i) => (
                <div
                  key={q.question_id}
                  className={`${styles.questionListItem} ${answeredIds.has(q.question_id) ? styles.answered : ''}`}
                >
                  <div className={styles.qNum}>Q{i + 1}</div>
                  <div className={styles.qMeta}>
                    <span className={styles.qPersona}>{displayPersona(q.persona)}</span>
                    <span className={`${styles.qDiff} ${styles[q.difficulty]}`}>{q.difficulty}</span>
                    <span className={styles.qCat}>{q.category}</span>
                    {answeredIds.has(q.question_id) && (
                      <span className={styles.answeredBadge}>Answered</span>
                    )}
                  </div>
                  <div className={styles.qText}>{q.question_text}</div>
                </div>
              ))}
            </div>

            <div className={styles.actionRow}>
              <button className={styles.primaryBtn} onClick={() => { setQIndex(0); setPhase('defense'); }}>
                Start Q&amp;A
              </button>
              {answeredCount > 0 && (
                <button className={styles.reportBtn} onClick={handleGenerateReport}>
                  Generate Feedback Report
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className={styles.section}>
            <p className={styles.hint}>No questions generated yet.</p>
            <button className={styles.primaryBtn} onClick={handleGenerateQuestions}>
              Generate Review Questions
            </button>
          </div>
        )}
      </div>
    );
  }

  // ── Active Q&A ─────────────────────────────────────────────────────────────

  if (phase === 'defense' && currentQuestion) {
    return (
      <div className={styles.container}>
        <div className={styles.modeBadgeRow}>
          <span className={styles.modeBadge}>{modeInfo.label}</span>
          {severity !== 'standard' && <span className={styles.sevBadge}>{severity}</span>}
          {voiceToggle}
          {voiceOn && tts.isSupported && (
            <button className={styles.toggleBtn} onClick={speakCurrentQuestion} title="Read the question again">
              🔊 Replay
            </button>
          )}
          <span className={styles.qCounter}>
            Question {qIndex + 1} of {questions.length}
          </span>
        </div>

        <div className={styles.questionCard}>
          <div className={styles.personaHeader}>
            <div>
              <div className={styles.activePersonaRole}>{displayPersona(currentQuestion.persona)}</div>
              {personas.find(p => p.role === currentQuestion.persona) && (
                <div className={styles.activePersonaName}>
                  {personas.find(p => p.role === currentQuestion.persona)!.name}
                </div>
              )}
            </div>
            <div className={styles.questionMeta}>
              <span className={`${styles.diffBadge} ${styles[currentQuestion.difficulty]}`}>
                {currentQuestion.difficulty}
              </span>
              <span className={styles.catBadge}>{currentQuestion.category}</span>
            </div>
          </div>

          <p className={styles.questionText}>{currentQuestion.question_text}</p>

          {currentQuestion.source_excerpt && (
            <blockquote className={styles.sourceExcerpt}>
              {currentQuestion.source_excerpt}
            </blockquote>
          )}
        </div>

        <div className={styles.answerSection}>
          <div className={styles.answerLabelRow}>
            <label className={styles.answerLabel}>Your Answer</label>
            {voiceOn && (
              stt.isSupported ? (
                <button
                  className={`${styles.micBtn} ${stt.isListening ? styles.micActive : ''}`}
                  onClick={handleMicClick}
                  disabled={submitting}
                >
                  {stt.isListening ? '⏹ Stop dictating' : '🎙 Dictate answer'}
                </button>
              ) : (
                <span className={styles.voiceHint}>Speech input needs Chrome or Edge — type instead.</span>
              )
            )}
          </div>
          <textarea
            className={styles.answerTextarea}
            value={answerText}
            onChange={e => setAnswerText(e.target.value)}
            placeholder={voiceOn
              ? 'Dictate with the microphone or type. You can edit the transcript before submitting.'
              : 'Type your answer here. Reference your methodology, evidence, and document sources where applicable.'}
            rows={7}
            disabled={submitting}
          />
          {voiceOn && stt.isListening && (
            <div className={styles.liveTranscript}>
              {`${stt.finalTranscript} ${stt.interimTranscript}`.trim() || 'Listening… speak your answer'}
            </div>
          )}
          {voiceOn && stt.error && <div className={styles.inlineError}>{stt.error}</div>}
          <div className={styles.wordCount}>
            {answerText.trim().split(/\s+/).filter(Boolean).length} words
          </div>
        </div>

        {error && <div className={styles.inlineError}>{error}</div>}

        <div className={styles.actionRow}>
          <button
            className={styles.secondaryBtn}
            onClick={() => setPhase('questions')}
            disabled={submitting}
          >
            Back to Questions
          </button>
          <button
            className={styles.primaryBtn}
            onClick={handleSubmitAnswer}
            disabled={submitting || answerText.trim().length < 10}
          >
            {submitting ? 'Reviewing…' : 'Submit Answer'}
          </button>
        </div>
      </div>
    );
  }

  // ── Evaluation result ──────────────────────────────────────────────────────

  if (phase === 'evaluated' && evaluation && currentQuestion) {
    const followUp = evaluation.follow_up_needed && evaluation.follow_up_question;

    return (
      <div className={styles.container}>
        <div className={styles.modeBadgeRow}>
          <span className={styles.modeBadge}>{modeInfo.label}</span>
          {severity !== 'standard' && <span className={styles.sevBadge}>{severity}</span>}
        </div>

        <div className={styles.evalCard}>
          <div className={styles.evalHeader}>
            <div>
              <div className={styles.evalTitle}>Feedback on Your Answer</div>
              <div className={styles.evalQuestion}>{currentQuestion.question_text}</div>
            </div>
          </div>

          <div className={styles.feedbackGrid}>
            <div className={`${styles.feedbackCard} ${styles.strength}`}>
              <h4>What Worked</h4>
              <p>{evaluation.strength}</p>
            </div>
            <div className={`${styles.feedbackCard} ${styles.weakness}`}>
              <h4>Area to Improve</h4>
              <p>{evaluation.weakness}</p>
            </div>
          </div>

          {evaluation.missing_evidence && (
            <div className={styles.missingEvidence}>
              <h4>Missing Evidence</h4>
              <p>{evaluation.missing_evidence}</p>
            </div>
          )}

          {evaluation.suggested_improvement && (
            <div className={styles.improvement}>
              <h4>Suggested Improvement</h4>
              <p>{evaluation.suggested_improvement}</p>
            </div>
          )}

          {delivery && (
            <div className={styles.deliveryCard}>
              <h4>🎙 Delivery (how you said it)</h4>
              <div className={styles.deliveryGrid}>
                {(() => {
                  const pace = delivery.wpm < 110 ? { t: 'A bit slow', c: styles.deliveryWarn }
                    : delivery.wpm > 175 ? { t: 'A bit fast', c: styles.deliveryWarn }
                    : { t: 'Good pace', c: styles.deliveryOk };
                  const fill = delivery.fillers <= 2 ? { t: 'Clean', c: styles.deliveryOk }
                    : delivery.fillers <= 5 ? { t: 'Some fillers', c: styles.deliveryWarn }
                    : { t: 'Many fillers', c: styles.deliveryBad };
                  return (
                    <>
                      <div className={styles.deliveryStat}>
                        <span className={styles.deliveryNum}>{delivery.wpm}</span>
                        <span className={styles.deliveryLbl}>words / min</span>
                        <span className={`${styles.deliveryBand} ${pace.c}`}>{pace.t}</span>
                      </div>
                      <div className={styles.deliveryStat}>
                        <span className={styles.deliveryNum}>{delivery.fillers}</span>
                        <span className={styles.deliveryLbl}>filler words</span>
                        <span className={`${styles.deliveryBand} ${fill.c}`}>{fill.t}</span>
                      </div>
                      {delivery.confidence > 0 && (
                        <div className={styles.deliveryStat}>
                          <span className={styles.deliveryNum}>{delivery.confidence}%</span>
                          <span className={styles.deliveryLbl}>speech clarity</span>
                          <span className={`${styles.deliveryBand} ${delivery.confidence >= 80 ? styles.deliveryOk : styles.deliveryWarn}`}>
                            {delivery.confidence >= 80 ? 'Clear' : 'Muffled'}
                          </span>
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
              <p className={styles.deliveryNote}>Delivery is separate from content — a confident delivery of a weak answer still needs work.</p>
            </div>
          )}

          {followUp && (
            <div className={styles.followUp}>
              <h4>The panel isn&apos;t satisfied — follow-up</h4>
              <p>{evaluation.follow_up_question}</p>
            </div>
          )}
        </div>

        <div className={styles.actionRow}>
          {followUp && (
            <button className={styles.primaryBtn} onClick={handleAnswerFollowUp} disabled={submitting}>
              {submitting ? 'Preparing…' : '🎯 Answer the follow-up'}
            </button>
          )}
          {qIndex + 1 < questions.length ? (
            <button className={followUp ? styles.secondaryBtn : styles.primaryBtn} onClick={handleNextQuestion}>
              {followUp ? 'Skip →' : 'Next Question'}
            </button>
          ) : !followUp ? (
            <button className={styles.reportBtn} onClick={handleGenerateReport}>
              Generate Feedback Report
            </button>
          ) : null}
          <button className={styles.secondaryBtn} onClick={() => setPhase('questions')}>
            Back to Overview
          </button>
        </div>
      </div>
    );
  }

  // ── Readiness report ───────────────────────────────────────────────────────

  if (phase === 'report' && report) {
    // Readiness outlook: derived internally, surfaced only as a qualitative band.
    const v = report.overall_readiness;
    const outlook = typeof v === 'number'
      ? v >= 75
        ? { label: 'On track', cls: styles.outlookStrong, hint: 'You appear well prepared — keep your momentum with a final run-through.' }
        : v >= 50
          ? { label: 'Almost there', cls: styles.outlookAlmost, hint: 'Most answers held up — revisit the improvement plan, then practice again.' }
          : { label: 'Needs more practice', cls: styles.outlookPractice, hint: 'Several answers had gaps — work through the improvement plan below.' }
      : null;

    return (
      <div className={styles.container}>
        <div className={styles.modeBadgeRow}>
          <span className={styles.modeBadge}>{modeInfo.label}</span>
          {severity !== 'standard' && <span className={styles.sevBadge}>{severity}</span>}
        </div>

        <div className={styles.reportHeader}>
          <div>
            <h2 className={styles.reportTitle}>
              Session Feedback Report
              {outlook && <span className={`${styles.outlookChip} ${outlook.cls}`}>{outlook.label}</span>}
            </h2>
            <div className={styles.readinessLabel}>
              {outlook
                ? `${outlook.hint} (Qualitative outlook — not a grade.)`
                : 'Qualitative feedback from your AI review panel — no marks, just what to strengthen next.'}
            </div>
          </div>
        </div>

        {/* Readiness breakdown — the per-axis picture, as qualitative bands
            (no raw marks) instead of hiding the data entirely. */}
        {(() => {
          const axes = [
            ['Research clarity', report.research_clarity],
            ['Methodology defense', report.methodology_score],
            ['Evidence strength', report.evidence_score],
            ['Critical thinking', report.critical_thinking],
            ['Communication', report.communication],
          ].filter(([, v]) => typeof v === 'number') as [string, number][];
          if (axes.length === 0) return null;
          const band = (v: number) =>
            v >= 75 ? { label: 'Strong', cls: styles.axisStrong }
            : v >= 50 ? { label: 'Developing', cls: styles.axisDeveloping }
            : { label: 'Needs work', cls: styles.axisWeak };
          return (
            <div className={styles.section}>
              <div className={styles.sectionTitle}>Readiness Breakdown</div>
              <div className={styles.axisGrid}>
                {axes.map(([label, v]) => {
                  const b = band(v);
                  return (
                    <div key={label} className={styles.axisRow}>
                      <span className={styles.axisLabel}>{label}</span>
                      <span className={styles.axisTrack}>
                        <span className={`${styles.axisFill} ${b.cls}`} style={{ width: `${Math.max(4, v)}%` }} />
                      </span>
                      <span className={`${styles.axisBand} ${b.cls}`}>{b.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}

        <div className={styles.swGrid}>
          {report.strong_answers && report.strong_answers.length > 0 && (
            <div className={styles.section}>
              <div className={styles.sectionTitle}>What Went Well</div>
              {report.strong_answers.map((a: any, i: number) => (
                <div key={i} className={styles.swItem}>
                  <span>
                    {a.question_text || a.question || ''}
                    {a.summary ? ` — ${a.summary}` : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
          {report.weak_answers && report.weak_answers.length > 0 && (
            <div className={styles.section}>
              <div className={styles.sectionTitle}>Answers to Revisit</div>
              {report.weak_answers.map((a: any, i: number) => (
                <div key={i} className={styles.swItemWeak}>
                  <span>
                    {a.question_text || a.question || ''}
                    {a.summary ? ` — ${a.summary}` : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {report.improvement_plan && report.improvement_plan.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Improvement Plan</div>
            <ol className={styles.planList}>
              {report.improvement_plan.map((item: any, i: number) => (
                <li key={i} className={styles.planItem}>
                  {typeof item === 'string'
                    ? item
                    : [item.area, item.action].filter(Boolean).join(' — ') || JSON.stringify(item)}
                </li>
              ))}
            </ol>
          </div>
        )}

        {report.repeated_issues && report.repeated_issues.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Recurring Issues</div>
            <ul className={styles.likelyList}>
              {report.repeated_issues.map((it: any, i: number) => (
                <li key={i}>
                  {typeof it === 'string' ? it : it.issue}
                  {it?.frequency ? <span className={styles.freqBadge}>×{it.frequency}</span> : null}
                </li>
              ))}
            </ul>
          </div>
        )}

        {report.model_answers && report.model_answers.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Model Answers to Study</div>
            <p className={styles.hint}>
              Stronger answers to your weakest questions — grounded in your own methodology and evidence.
            </p>
            {report.model_answers.map((m, i) => (
              <div key={i} className={styles.modelAnswer}>
                <div className={styles.modelQ}>{m.question}</div>
                <p className={styles.modelA}>{m.improved_answer}</p>
                {m.why_stronger && <div className={styles.modelWhy}>Why it's stronger: {m.why_stronger}</div>}
              </div>
            ))}
          </div>
        )}

        {report.likely_questions && report.likely_questions.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Questions a Review Panel May Ask</div>
            <ul className={styles.likelyList}>
              {report.likely_questions.map((q: string, i: number) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </div>
        )}

        {report.next_recommendation && (
          <div className={styles.nextRec}>
            <h4>Next Practice Recommendation</h4>
            <p>{report.next_recommendation}</p>
          </div>
        )}

        <AcademicAssessmentCard key={debateId} debateId={debateId} triggerSource="practice_qa" autoGenerate />

        <div className={styles.actionRow}>
          <button className={styles.secondaryBtn} onClick={() => setPhase('questions')}>
            Back to Questions
          </button>
          <button
            className={styles.primaryBtn}
            onClick={() => {
              setAnsweredIds(new Set());
              setEvaluation(null);
              setPhase('setup');
            }}
          >
            Start New Session
          </button>
        </div>
      </div>
    );
  }

  return null;
}
