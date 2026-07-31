'use client';

/**
 * In-app messages.
 *
 * Replaces alert(), which blocked the page, could not be styled, could not
 * carry an action, and read as a browser failure rather than as the app
 * telling you something.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from 'react';
import styles from './Toaster.module.css';

export type ToastTone = 'info' | 'success' | 'error';

interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
  /** An optional way to recover, shown as a button. */
  action?: { label: string; onClick: () => void };
}

interface ToastApi {
  notify: (message: string, tone?: ToastTone, action?: Toast['action']) => void;
  /** Errors persist until dismissed — a failure the user missed is a failure they will hit again. */
  error: (message: string, action?: Toast['action']) => void;
  success: (message: string) => void;
}

const ToastContext = createContext<ToastApi>({
  notify: () => {},
  error: () => {},
  success: () => {},
});

const AUTO_DISMISS_MS = 6000;

export function Toaster({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback(
    (message: string, tone: ToastTone = 'info', action?: Toast['action']) => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, tone, message, action }]);
      // Errors stay until dismissed; anything else clears itself.
      if (tone !== 'error') {
        setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
      }
    },
    [dismiss]
  );

  const api = useMemo<ToastApi>(
    () => ({
      notify,
      error: (message, action) => notify(message, 'error', action),
      success: (message) => notify(message, 'success'),
    }),
    [notify]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className={styles.stack} role="region" aria-label="Notifications">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`${styles.toast} ${styles[t.tone]}`}
            // Errors interrupt; the rest wait for a pause in speech.
            role={t.tone === 'error' ? 'alert' : 'status'}
            aria-live={t.tone === 'error' ? 'assertive' : 'polite'}
          >
            <span className={styles.message}>{t.message}</span>
            {t.action && (
              <button
                className={styles.action}
                onClick={() => {
                  t.action!.onClick();
                  dismiss(t.id);
                }}
              >
                {t.action.label}
              </button>
            )}
            <button
              className={styles.close}
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
            >
              <span aria-hidden="true">&#10005;</span>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  return useContext(ToastContext);
}
