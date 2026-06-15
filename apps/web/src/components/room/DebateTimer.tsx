'use client';

import { useState, useEffect } from 'react';
import styles from './DebateTimer.module.css';

interface DebateTimerProps {
  debateId: string;
  timeboxMinutes?: number;
  debateStartedAt?: string; // ISO timestamp when debate started
  debateState: string;
}

export default function DebateTimer({ 
  debateId, 
  timeboxMinutes, 
  debateStartedAt,
  debateState 
}: DebateTimerProps) {
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);

  useEffect(() => {
    if (!timeboxMinutes || !debateStartedAt || debateState !== 'running') {
      setSecondsRemaining(null);
      return;
    }

    const calculateRemaining = () => {
      const started = new Date(debateStartedAt).getTime();
      const now = Date.now();
      const elapsed = Math.floor((now - started) / 1000); // seconds
      const total = timeboxMinutes * 60; // convert minutes to seconds
      const remaining = Math.max(0, total - elapsed);
      return remaining;
    };

    // Initial calculation
    setSecondsRemaining(calculateRemaining());

    // Update every second
    const interval = setInterval(() => {
      const remaining = calculateRemaining();
      setSecondsRemaining(remaining);

      // Auto-end debate when time runs out
      if (remaining === 0) {
        clearInterval(interval);
        // You could trigger an auto-end event here if needed
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [debateId, timeboxMinutes, debateStartedAt, debateState]);

  if (!timeboxMinutes || secondsRemaining === null) {
    return null;
  }

  const minutes = Math.floor(secondsRemaining / 60);
  const seconds = secondsRemaining % 60;
  const percentage = ((timeboxMinutes * 60 - secondsRemaining) / (timeboxMinutes * 60)) * 100;

  // Urgency levels
  let urgencyClass = styles.normal;
  let urgencyIcon = '⏱️';
  
  if (secondsRemaining === 0) {
    urgencyClass = styles.expired;
    urgencyIcon = '⏰';
  } else if (secondsRemaining < 60) {
    urgencyClass = styles.critical;
    urgencyIcon = '';
  } else if (secondsRemaining < 120) {
    urgencyClass = styles.warning;
    urgencyIcon = '';
  }

  return (
    <div className={`${styles.timer} ${urgencyClass}`}>
      <div className={styles.timerHeader}>
        <span className={styles.timerIcon}>{urgencyIcon}</span>
        <span className={styles.timerLabel}>TIME LIMIT</span>
      </div>
      <div className={styles.timerDisplay}>
        {minutes}:{seconds.toString().padStart(2, '0')}
      </div>
      <div className={styles.timerSubtext}>
        {secondsRemaining === 0 
          ? 'Time expired!' 
          : `${timeboxMinutes} minute${timeboxMinutes > 1 ? 's' : ''} total`
        }
      </div>
      <div className={styles.progressBar}>
        <div 
          className={styles.progressFill} 
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
