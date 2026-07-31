'use client';

/**
 * A dialog a keyboard user can actually use.
 *
 * The dialogs this replaces closed on overlay click only, which meant someone
 * navigating by keyboard could open one and have no way out. They also let
 * focus wander behind the overlay to content they could not see.
 */
import { useCallback, useEffect, useRef } from 'react';
import styles from './Modal.module.css';

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), ' +
  'select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  /** Hide the heading visually while keeping it for screen readers. */
  hideTitle?: boolean;
}

export default function Modal({
  open,
  onClose,
  title,
  children,
  hideTitle = false,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusTo = useRef<HTMLElement | null>(null);

  const focusables = useCallback(
    () => Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []),
    []
  );

  useEffect(() => {
    if (!open) return;

    restoreFocusTo.current = document.activeElement as HTMLElement | null;
    // Move focus in, so the next Tab stays inside the dialog.
    (focusables()[0] ?? panelRef.current)?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;

      const items = focusables();
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;

      // Wrap, rather than letting focus escape to the page behind.
      if (e.shiftKey && (active === first || !panelRef.current?.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.body.style.overflow = previousOverflow;
      restoreFocusTo.current?.focus?.();
    };
  }, [open, onClose, focusables]);

  if (!open) return null;

  return (
    // Clicking the backdrop is a mouse convenience; Escape is the keyboard
    // equivalent and is handled above, so a key listener here would be a
    // second path to the same action rather than an accessibility gain.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions, jsx-a11y/click-events-have-key-events
    <div
      className={styles.overlay}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={panelRef}
        tabIndex={-1}
      >
        <div className={styles.head}>
          <h2 className={hideTitle ? styles.srOnly : styles.title}>{title}</h2>
          <button className={styles.close} onClick={onClose} aria-label={`Close ${title}`}>
            <span aria-hidden="true">&#10005;</span>
          </button>
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>
  );
}
