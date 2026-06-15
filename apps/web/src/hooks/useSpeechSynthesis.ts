/**
 * useSpeechSynthesis — TTS via Web Speech API
 *
 * Each persona maps to a distinct voice pitch/rate so the student
 * can immediately recognise which panel member is speaking.
 */
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

export type PersonaVoiceId =
  | 'advisor'
  | 'methodology'
  | 'domain'
  | 'skeptical'
  | 'friendly'
  | 'examiner'
  | 'default';

interface VoiceConfig {
  pitch: number;
  rate:  number;
  /** Prefer voices whose name includes this token (case-insensitive). */
  preferName?: string;
}

const PERSONA_VOICES: Record<PersonaVoiceId, VoiceConfig> = {
  advisor:      { pitch: 0.90, rate: 0.85, preferName: 'daniel'   },
  methodology:  { pitch: 1.00, rate: 0.95, preferName: 'karen'    },
  domain:       { pitch: 1.05, rate: 1.05, preferName: 'alex'     },
  skeptical:    { pitch: 0.80, rate: 0.88, preferName: 'fred'     },
  friendly:     { pitch: 1.10, rate: 0.92, preferName: 'samantha' },
  examiner:     { pitch: 0.75, rate: 0.82, preferName: 'tom'      },
  default:      { pitch: 1.00, rate: 1.00 },
};

/** Map a raw persona role string to one of our persona voice IDs. */
export function roleToVoiceId(role: string): PersonaVoiceId {
  const r = role.toLowerCase();
  if (r.includes('advisor'))       return 'advisor';
  if (r.includes('method'))        return 'methodology';
  if (r.includes('domain') || r.includes('expert')) return 'domain';
  if (r.includes('skeptic'))       return 'skeptical';
  if (r.includes('friendly'))      return 'friendly';
  if (r.includes('examiner') || r.includes('external') || r.includes('independent')) return 'examiner';
  return 'default';
}

export interface UseSpeechSynthesisReturn {
  speak:       (text: string, personaId?: PersonaVoiceId) => void;
  cancel:      () => void;
  isSpeaking:  boolean;
  isSupported: boolean;
}

export function useSpeechSynthesis(): UseSpeechSynthesisReturn {
  const [isSpeaking,  setIsSpeaking]  = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    setIsSupported(true);

    const load = () => { voicesRef.current = window.speechSynthesis.getVoices(); };
    load();
    window.speechSynthesis.addEventListener('voiceschanged', load);
    return () => window.speechSynthesis.removeEventListener('voiceschanged', load);
  }, []);

  const pickVoice = useCallback((personaId: PersonaVoiceId): SpeechSynthesisVoice | null => {
    const voices = voicesRef.current;
    if (!voices.length) return null;

    const config = PERSONA_VOICES[personaId] ?? PERSONA_VOICES.default;

    // 1. preferred name (exact substring match)
    if (config.preferName) {
      const preferred = voices.find(v =>
        v.name.toLowerCase().includes(config.preferName!.toLowerCase())
      );
      if (preferred) return preferred;
    }

    // 2. English voices
    const english = voices.filter(v => v.lang.startsWith('en'));
    if (english.length) return english[0];

    return voices[0];
  }, []);

  const speak = useCallback((text: string, personaId: PersonaVoiceId = 'default') => {
    if (!isSupported) return;

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const config    = PERSONA_VOICES[personaId] ?? PERSONA_VOICES.default;

    utterance.pitch  = config.pitch;
    utterance.rate   = config.rate;
    utterance.volume = 1;

    const voice = pickVoice(personaId);
    if (voice) utterance.voice = voice;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend   = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }, [isSupported, pickVoice]);

  const cancel = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, [isSupported]);

  return { speak, cancel, isSpeaking, isSupported };
}
