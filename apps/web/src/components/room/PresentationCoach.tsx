'use client';

/**
 * PresentationCoach — concept 7.6 (deck analysis + rehearsal).
 *
 * Three experiences on the session's uploaded .pptx:
 *  1. Overview  — per-slide structure metrics with honest flags (walls of text,
 *                 bullet overload, missing notes, no conclusion).
 *  2. Coach     — LLM feedback grounded in the extracted slide text: structure,
 *                 clarity, per-slide suggestions, likely audience questions.
 *  3. Rehearsal — present slide by slide against the clock; with the mic on,
 *                 per-slide pace and filler words are measured. Ends in a run
 *                 report with per-slide timing flags.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  getPresentationDeck, coachPresentation,
  type DeckData, type DeckCoach,
} from '@/lib/api';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import styles from './PresentationCoach.module.css';

interface Props {
  debateId: string;
  openrouterKey: string;
}

const FLAG_LABEL: Record<string, string> = {
  wall_of_text: 'Wall of text',
  bullet_overload: 'Too many bullets',
  no_speaker_notes: 'No notes',
  empty_slide: 'Empty slide',
  no_conclusion_slide: 'No conclusion slide',
  mostly_missing_notes: 'Most slides lack speaker notes',
};

interface SlideRun {
  slide_num: number;
  seconds: number;
  words: number;
  fillers: number;
}

const FILLER_RE = /\b(um+|uh+|er+|like|you know|basically|actually|kind of|sort of|i mean)\b/g;

export default function PresentationCoach({ debateId, openrouterKey }: Props) {
  const router = useRouter();
  // keepAlive: a rehearsal has natural pauses — never auto-stop on silence,
  // and survive the browser's own recognition-session limits.
  const stt = useSpeechRecognition({ keepAlive: true });

  const [deck, setDeck] = useState<DeckData | null>(null);
  const [coach, setCoach] = useState<DeckCoach | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [coaching, setCoaching] = useState(false);
  const [view, setView] = useState<'overview' | 'present' | 'report'>('overview');

  // Rehearsal state
  const [slideIdx, setSlideIdx] = useState(0);
  const [showNotes, setShowNotes] = useState(true);
  const [micOn, setMicOn] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [runs, setRuns] = useState<SlideRun[]>([]);
  const slideStartRef = useRef(0);
  const wordsAtSlideStartRef = useRef(0);
  const transcriptRef = useRef('');
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getPresentationDeck(debateId)
      .then(setDeck)
      .catch((e) => setError(String(e?.message || e)));
  }, [debateId]);

  // Keep a live copy of the accumulated transcript for per-slide word deltas.
  useEffect(() => {
    transcriptRef.current = `${stt.finalTranscript} ${stt.interimTranscript}`.trim();
  }, [stt.finalTranscript, stt.interimTranscript]);

  const wordCount = (s: string) => s.split(/\s+/).filter(Boolean).length;

  const startRun = useCallback(() => {
    setRuns([]);
    setSlideIdx(0);
    setElapsed(0);
    slideStartRef.current = Date.now();
    wordsAtSlideStartRef.current = 0;
    stt.resetTranscript();
    if (micOn && stt.isSupported) stt.startListening();
    setView('present');
    if (tickRef.current) clearInterval(tickRef.current);
    tickRef.current = setInterval(() => {
      setElapsed(Math.round((Date.now() - slideStartRef.current) / 1000));
    }, 1000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [micOn, stt.isSupported]);

  const snapshotSlide = useCallback((slideNum: number): SlideRun => {
    const seconds = Math.max(1, Math.round((Date.now() - slideStartRef.current) / 1000));
    const totalWords = wordCount(transcriptRef.current);
    const words = Math.max(0, totalWords - wordsAtSlideStartRef.current);
    const spokenSlice = transcriptRef.current
      .split(/\s+/).slice(wordsAtSlideStartRef.current).join(' ').toLowerCase();
    const fillers = (spokenSlice.match(FILLER_RE) || []).length;
    wordsAtSlideStartRef.current = totalWords;
    slideStartRef.current = Date.now();
    return { slide_num: slideNum, seconds, words, fillers };
  }, []);

  const nextSlide = useCallback(() => {
    if (!deck) return;
    const run = snapshotSlide(deck.slides[slideIdx].slide_num);
    setRuns((r) => [...r, run]);
    if (slideIdx + 1 >= deck.slides.length) {
      if (tickRef.current) clearInterval(tickRef.current);
      if (stt.isListening) stt.stopListening();
      setView('report');
    } else {
      setSlideIdx(slideIdx + 1);
      setElapsed(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deck, slideIdx, snapshotSlide, stt.isListening]);

  const endRun = useCallback(() => {
    if (!deck) return;
    const run = snapshotSlide(deck.slides[slideIdx].slide_num);
    setRuns((r) => [...r, run]);
    if (tickRef.current) clearInterval(tickRef.current);
    if (stt.isListening) stt.stopListening();
    setView('report');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deck, slideIdx, snapshotSlide, stt.isListening]);

  // On unmount (e.g. switching room tabs mid-rehearsal): kill the timer AND
  // release the microphone — recognition must not outlive the component.
  const sttStopRef = useRef(stt.stopListening);
  sttStopRef.current = stt.stopListening;
  useEffect(() => () => {
    if (tickRef.current) clearInterval(tickRef.current);
    sttStopRef.current();
  }, []);

  const runCoach = useCallback(async () => {
    if (!openrouterKey) { setError('Add your OpenRouter API key in Settings first.'); return; }
    setCoaching(true);
    setError(null);
    try {
      const res = await coachPresentation(debateId, openrouterKey, 'light');
      setCoach(res.coach);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setCoaching(false);
    }
  }, [debateId, openrouterKey]);

  if (error && !deck) {
    return (
      <div className={styles.state}>
        {error.includes('No slide deck')
          ? <>No slide deck uploaded yet. Add your <strong>.pptx</strong> in the session&apos;s materials (New Session → Materials), then come back to rehearse it.</>
          : <>Could not load the deck: {error}</>}
      </div>
    );
  }
  if (!deck) return <div className={styles.state}>Loading deck…</div>;

  /* ── Rehearsal view ─────────────────────────────────────────────────────── */
  if (view === 'present') {
    const slide = deck.slides[slideIdx];
    if (!slide) {
      return <div className={styles.state}>This deck has no slides to rehearse.</div>;
    }
    const pace = elapsed > 150 ? styles.timeOver : elapsed > 90 ? styles.timeWarn : styles.timeOk;
    return (
      <div className={styles.wrap}>
        <div className={styles.presentTop}>
          <span>Slide {slideIdx + 1} / {deck.slide_count}</span>
          <span className={`${styles.timer} ${pace}`}>{Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}</span>
          {micOn && stt.isListening && <span className={styles.micLive}>● listening</span>}
        </div>
        <div className={styles.slideCard}>
          <h2 className={styles.slideTitle}>{slide.title || `Slide ${slide.slide_num}`}</h2>
          <pre className={styles.slideBody}>{slide.text.split('\n').slice(1).join('\n')}</pre>
        </div>
        {showNotes && slide.notes_words > 0 && (
          <div className={styles.notesHint}>Your notes are folded into the slide text above.</div>
        )}
        <div className={styles.actionRow}>
          <button className={styles.primaryBtn} onClick={nextSlide}>
            {slideIdx + 1 >= deck.slides.length ? 'Finish run' : 'Next slide →'}
          </button>
          <button className={styles.secondaryBtn} onClick={endRun}>End early</button>
          <button className={styles.secondaryBtn} onClick={() => setShowNotes(v => !v)}>
            {showNotes ? 'Hide' : 'Show'} notes
          </button>
        </div>
      </div>
    );
  }

  /* ── Run report ─────────────────────────────────────────────────────────── */
  if (view === 'report') {
    const total = runs.reduce((a, r) => a + r.seconds, 0);
    const totalWords = runs.reduce((a, r) => a + r.words, 0);
    const totalFillers = runs.reduce((a, r) => a + r.fillers, 0);
    return (
      <div className={styles.wrap}>
        <h3 className={styles.title}>Rehearsal Run Report</h3>
        <p className={styles.subtitle}>
          {Math.floor(total / 60)}m {total % 60}s across {runs.length} slide(s)
          {totalWords > 0 && ` · ${totalWords} words${total > 0 ? ` · ${Math.round((totalWords / total) * 60)} wpm` : ''} · ${totalFillers} filler(s)`}
        </p>
        <table className={styles.runTable}>
          <thead><tr><th>Slide</th><th>Time</th><th>Pacing</th>{totalWords > 0 && <><th>Words</th><th>Fillers</th></>}</tr></thead>
          <tbody>
            {runs.map((r) => {
              const p = r.seconds < 30 ? { t: 'Rushed', c: styles.timeWarn }
                : r.seconds > 150 ? { t: 'Too long', c: styles.timeOver }
                : { t: 'Good', c: styles.timeOk };
              const title = deck.slides.find(s => s.slide_num === r.slide_num)?.title || '';
              return (
                <tr key={r.slide_num}>
                  <td className={styles.runSlide}>{r.slide_num}. {title.slice(0, 40)}</td>
                  <td>{r.seconds}s</td>
                  <td className={p.c}>{p.t}</td>
                  {totalWords > 0 && <><td>{r.words}</td><td>{r.fillers}</td></>}
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className={styles.actionRow}>
          <button className={styles.primaryBtn} onClick={startRun}>Rehearse again</button>
          <button className={styles.secondaryBtn} onClick={() => setView('overview')}>Back to deck</button>
          <button
            className={styles.secondaryBtn}
            onClick={() => router.push(`/room?debate_id=${debateId}&tab=defense`)}
            title="Generate conference-style audience questions in Practice Q&A (pick the Conference Q&A mode)"
          >
            🎯 Practice audience questions
          </button>
        </div>
      </div>
    );
  }

  /* ── Overview ───────────────────────────────────────────────────────────── */
  return (
    <div className={styles.wrap}>
      <header className={styles.header}>
        <div>
          <h3 className={styles.title}>🎤 {deck.deck_title}</h3>
          <p className={styles.subtitle}>
            {deck.slide_count} slides · ~{deck.estimated_minutes} min at conference pace
          </p>
          {deck.deck_flags.length > 0 && (
            <div className={styles.flagRow}>
              {deck.deck_flags.map(f => <span key={f} className={styles.deckFlag}>{FLAG_LABEL[f] || f}</span>)}
            </div>
          )}
        </div>
        <div className={styles.headerActions}>
          <label className={styles.micToggle}>
            <input type="checkbox" checked={micOn} onChange={e => setMicOn(e.target.checked)} disabled={!stt.isSupported} />
            Measure my delivery (mic)
          </label>
          <button className={styles.primaryBtn} onClick={startRun} disabled={!deck.slides.length}>▶ Start rehearsal</button>
          <button className={styles.coachBtn} onClick={runCoach} disabled={coaching}>
            {coaching ? 'Coaching…' : '🧑‍🏫 Get coach feedback'}
          </button>
        </div>
      </header>
      {error && <div className={styles.inlineError}>{error}</div>}

      {coach && (
        <div className={styles.coachCard}>
          <div className={styles.coachSection}><h4>Overall</h4><p>{coach.overall_impression}</p></div>
          <div className={styles.coachSection}><h4>Structure</h4><p>{coach.structure_feedback}</p></div>
          <div className={styles.coachSection}><h4>Clarity</h4><p>{coach.clarity_feedback}</p></div>
          {coach.slide_suggestions?.length > 0 && (
            <div className={styles.coachSection}>
              <h4>Slide suggestions</h4>
              <ul>{coach.slide_suggestions.map((s, i) => <li key={i}><strong>Slide {s.slide_num}:</strong> {s.suggestion}</li>)}</ul>
            </div>
          )}
          {coach.strongest_slide && (
            <div className={styles.coachSection}><h4>Strongest slide</h4>
              <p><strong>Slide {coach.strongest_slide.slide_num}</strong> — {coach.strongest_slide.why}</p></div>
          )}
          {coach.likely_audience_questions?.length > 0 && (
            <div className={styles.coachSection}>
              <h4>Likely audience questions</h4>
              <ul>{coach.likely_audience_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
            </div>
          )}
        </div>
      )}

      <div className={styles.slideList}>
        {deck.slides.map((s) => (
          <div key={s.slide_num} className={styles.slideRow}>
            <span className={styles.slideNum}>{s.slide_num}</span>
            <div className={styles.slideInfo}>
              <div className={styles.slideRowTitle}>{s.title || '(untitled)'}</div>
              <div className={styles.slideMeta}>
                {s.body_words} words · {s.bullet_count} bullets · {s.notes_words > 0 ? `${s.notes_words} note words` : 'no notes'}
              </div>
            </div>
            <div className={styles.slideFlags}>
              {s.flags.map(f => <span key={f} className={styles.slideFlag}>{FLAG_LABEL[f] || f}</span>)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
