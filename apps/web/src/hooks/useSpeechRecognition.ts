/**
 * useSpeechRecognition — STT via Web Speech API (SpeechRecognition /
 * webkitSpeechRecognition).
 *
 * Features:
 *  - Continuous interim transcripts shown in real time.
 *  - Auto-stop after SILENCE_MS of no new speech.
 *  - Exposes `finalTranscript` (accumulated) + `interimTranscript` (live).
 *  - Gracefully degrades when not supported.
 */
'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

const SILENCE_MS = 2500; // auto-stop after 2.5 s of silence

type SpeechRecognitionType = any; // avoid browser-type conflicts

export interface UseSpeechRecognitionReturn {
  startListening:    () => void;
  stopListening:     () => void;
  resetTranscript:   () => void;
  finalTranscript:   string;
  interimTranscript: string;
  isListening:       boolean;
  isSupported:       boolean;
  confidence:        number;
  error:             string | null;
}

export interface UseSpeechRecognitionOptions {
  /** Long-form dictation mode (rehearsals): never auto-stop on silence, and
   *  restart recognition if the browser ends the session, preserving the
   *  accumulated transcript. Only stopListening() ends the capture. */
  keepAlive?: boolean;
}

export function useSpeechRecognition(options?: UseSpeechRecognitionOptions): UseSpeechRecognitionReturn {
  const [finalTranscript,   setFinalTranscript]   = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [isListening,       setIsListening]       = useState(false);
  const [isSupported,       setIsSupported]       = useState(false);
  const [confidence,        setConfidence]        = useState(0);
  const [error,             setError]             = useState<string | null>(null);

  const recognitionRef   = useRef<SpeechRecognitionType>(null);
  const silenceTimerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const accumulatedRef   = useRef('');
  const keepAliveRef     = useRef(!!options?.keepAlive);
  keepAliveRef.current   = !!options?.keepAlive;
  const manualStopRef    = useRef(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    setIsSupported(!!SR);
  }, []);

  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  const resetSilenceTimer = useCallback((stopFn: () => void) => {
    clearSilenceTimer();
    if (keepAliveRef.current) return; // keep-alive mode: only stopListening() ends capture
    silenceTimerRef.current = setTimeout(stopFn, SILENCE_MS);
  }, []);

  const stopListening = useCallback(() => {
    manualStopRef.current = true;
    clearSilenceTimer();
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
    }
    setIsListening(false);
    setInterimTranscript('');
  }, []);

  const startListening = useCallback(() => {
    if (typeof window === 'undefined') return;

    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;

    setError(null);
    manualStopRef.current = false;
    accumulatedRef.current = '';
    setFinalTranscript('');
    setInterimTranscript('');
    setConfidence(0);

    // Builds + starts a recognition instance. keepAlive mode re-invokes this
    // from onend (browsers cap continuous sessions), keeping accumulatedRef.
    const launch = () => {
      const recognition: SpeechRecognitionType = new SR();
      recognition.continuous    = true;
      recognition.interimResults = true;
      recognition.lang           = 'en-US';
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListening(true);
        resetSilenceTimer(stopListening);
      };

      recognition.onresult = (event: any) => {
        resetSilenceTimer(stopListening);

        let interim = '';
        let finalChunk = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            finalChunk += result[0].transcript;
            setConfidence(result[0].confidence ?? 0);
          } else {
            interim += result[0].transcript;
          }
        }

        if (finalChunk) {
          accumulatedRef.current += (accumulatedRef.current ? ' ' : '') + finalChunk.trim();
          setFinalTranscript(accumulatedRef.current);
        }
        setInterimTranscript(interim);
      };

      recognition.onspeechend = () => {
        resetSilenceTimer(stopListening);
      };

      recognition.onerror = (event: any) => {
        if (event.error === 'no-speech') {
          // Benign — just restart silence timer
          resetSilenceTimer(stopListening);
          return;
        }
        if (event.error === 'aborted') return; // manual stop

        const messages: Record<string, string> = {
          'not-allowed':        'Microphone permission denied. Please allow mic access.',
          'service-not-allowed': 'Speech service not allowed. Try Chrome or Edge.',
          'network':            'Network error. Check your internet connection.',
          'audio-capture':      'No microphone found. Please connect a mic.',
        };
        setError(messages[event.error] ?? `Speech error: ${event.error}`);
        manualStopRef.current = true; // terminal — don't keep-alive restart
        setIsListening(false);
        clearSilenceTimer();
      };

      recognition.onend = () => {
        clearSilenceTimer();
        if (keepAliveRef.current && !manualStopRef.current) {
          try { launch(); return; } catch {}
        }
        setIsListening(false);
        setInterimTranscript('');
      };

      recognitionRef.current = recognition;
      recognition.start();
    };

    launch();
  }, [stopListening, resetSilenceTimer]);

  const resetTranscript = useCallback(() => {
    accumulatedRef.current = '';
    setFinalTranscript('');
    setInterimTranscript('');
    setConfidence(0);
    setError(null);
  }, []);

  return {
    startListening,
    stopListening,
    resetTranscript,
    finalTranscript,
    interimTranscript,
    isListening,
    isSupported,
    confidence,
    error,
  };
}
