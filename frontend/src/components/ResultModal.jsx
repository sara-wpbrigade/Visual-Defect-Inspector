/** Accessible modal that shows a historical inspection result in place. */

import { useCallback, useEffect, useRef } from 'react';

import { ResultCard } from './ResultCard';
import { LoadingCard } from './StatusPanels';

/** A modal wrapper for a historical inspection result. */
export function ResultModal({ result, loading, error, onClose, onReset }) {
  const closeButtonRef = useRef(null);
  const previouslyFocusedRef = useRef(null);

  useEffect(() => {
    previouslyFocusedRef.current = document.activeElement;
    document.body.style.overflow = 'hidden';
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = '';
      if (previouslyFocusedRef.current instanceof HTMLElement) {
        previouslyFocusedRef.current.focus();
      }
    };
  }, []);

  const handleBackdropClick = useCallback(
    (event) => {
      if (event.target === event.currentTarget) {
        onClose();
      }
    },
    [onClose],
  );

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={handleBackdropClick} role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-result-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          ref={closeButtonRef}
          type="button"
          className="modal-close"
          onClick={onClose}
          aria-label="Close result"
        >
          ×
        </button>

        {loading && (
          <div className="card">
            <LoadingCard />
          </div>
        )}

        {!loading && error && (
          <div className="card error-card" role="alert">
            <p className="step-label">Could not load result</p>
            <h2 id="modal-result-title">This result is not available</h2>
            <p className="error-message">{error}</p>
            <button type="button" className="button secondary" onClick={onClose}>
              Close
            </button>
          </div>
        )}

        {!loading && !error && result && (
          <ResultCard result={result} onReset={onReset ?? onClose} />
        )}
      </div>
    </div>
  );
}
