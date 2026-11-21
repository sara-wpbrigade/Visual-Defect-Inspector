/** Modal listing keyboard shortcuts. */

import { useEffect, useRef } from 'react';

const SHORTCUTS = [
  { keys: ['⌘', 'K'], label: 'Focus inspection tab' },
  { keys: ['⌘', 'H'], label: 'Open batches & history' },
  { keys: ['⌘', 'N'], label: 'Start a new inspection' },
  { keys: ['?'], label: 'Show this panel' },
  { keys: ['Esc'], label: 'Close any dialog' },
];

/** Read `navigator.platform` for the modifier label. */
function modifierLabel() {
  if (typeof navigator === 'undefined') {
    return 'Ctrl';
  }
  return /Mac|iPhone|iPad/i.test(navigator.platform) ? '⌘' : 'Ctrl';
}

/** Show the keyboard-shortcut reference. */
export function ShortcutsModal({ open, onClose }) {
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    closeRef.current?.focus();
    document.body.style.overflow = 'hidden';

    function handleKey(event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    }
    document.addEventListener('keydown', handleKey);
    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleKey);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const mod = modifierLabel();

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className="modal modal-shortcuts"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          ref={closeRef}
          type="button"
          className="modal-close"
          onClick={onClose}
          aria-label="Close shortcuts"
        >
          ×
        </button>

        <p className="step-label">Reference</p>
        <h2 id="shortcuts-title">Keyboard shortcuts</h2>

        <ul className="shortcut-list">
          {SHORTCUTS.map((shortcut) => (
            <li key={shortcut.label} className="shortcut-row">
              <span className="shortcut-keys">
                {shortcut.keys.map((key) => (
                  <kbd key={key}>{key === '⌘' && mod !== '⌘' ? mod : key}</kbd>
                ))}
              </span>
              <span className="shortcut-label">{shortcut.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
