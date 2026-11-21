/** Lightweight toast notification. Auto-dismisses after `duration` ms. */

import { useEffect, useRef } from 'react';

const DEFAULT_DURATION = 4000;

/** @param {{ message: string, tone?: 'info'|'success'|'error', onClose: () => void, duration?: number }} props */
export function Toast({ message, tone = 'info', onClose, duration = DEFAULT_DURATION }) {
  const timerRef = useRef(null);

  useEffect(() => {
    timerRef.current = setTimeout(onClose, duration);
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [onClose, duration]);

  return (
    <div className={`toast toast-${tone}`} role="status" aria-live="polite">
      <span className="toast-message">{message}</span>
      <button type="button" className="toast-dismiss" onClick={onClose} aria-label="Dismiss">
        ×
      </button>
    </div>
  );
}
