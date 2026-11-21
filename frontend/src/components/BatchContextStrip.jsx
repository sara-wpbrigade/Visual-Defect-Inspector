/** Live context for the batch currently being inspected. */

import { useEffect, useState } from 'react';

import { BATCH_DECISIONS, BATCH_DECISION_LABELS, BATCH_ID_REGEX } from '../constants';
import { getBatch } from '../services/api';

const LOOKUP_DELAY_MS = 400;

/** Pick the colour tone for a batch decision. */
function decisionTone(decision) {
  if (decision === BATCH_DECISIONS.REJECTED) {
    return 'verdict-defect';
  }
  if (decision === BATCH_DECISIONS.NEEDS_REVIEW) {
    return 'verdict-review';
  }
  return 'verdict-pass';
}

/** Show what already exists for the batch id the operator is working on. */
export function BatchContextStrip({ batchId, onViewBatch }) {
  const [context, setContext] = useState(null);
  const id = (batchId ?? '').trim();
  const valid = Boolean(id) && BATCH_ID_REGEX.test(id);

  useEffect(() => {
    if (!valid) {
      return undefined;
    }
    let ignore = false;
    const timer = setTimeout(async () => {
      try {
        const detail = await getBatch(id);
        if (!ignore) {
          setContext({ batchId: id, status: 'found', summary: detail.summary });
        }
      } catch (err) {
        if (!ignore) {
          setContext({
            batchId: id,
            status: err?.status === 404 ? 'new' : 'error',
            message: err?.message ?? null,
          });
        }
      }
    }, LOOKUP_DELAY_MS);
    return () => {
      ignore = true;
      clearTimeout(timer);
    };
  }, [id, valid]);

  if (!valid) {
    return null;
  }

  const current = context?.batchId === id ? context : null;

  return (
    <div className="batch-context-strip" aria-live="polite">
      <span className="batch-context-label">Current batch</span>
      <span className="batch-context-id mono">{id}</span>

      {!current && <span className="batch-context-note">Checking batch…</span>}

      {current?.status === 'found' && (
        <>
          <span className={`verdict ${decisionTone(current.summary.decision)}`}>
            {BATCH_DECISION_LABELS[current.summary.decision] ?? current.summary.decision}
          </span>
          <span className="batch-context-note">
            {current.summary.itemCount}{' '}
            {current.summary.itemCount === 1 ? 'inspection' : 'inspections'} ·{' '}
            {current.summary.defectCount} {current.summary.defectCount === 1 ? 'defect' : 'defects'}{' '}
            · {current.summary.reviewCount}{' '}
            {current.summary.reviewCount === 1 ? 'review' : 'reviews'}
          </span>
        </>
      )}

      {current?.status === 'new' && (
        <span className="batch-context-note">New batch · no inspections yet</span>
      )}

      {current?.status === 'error' && (
        <span className="batch-context-note is-error">Could not load this batch</span>
      )}

      {onViewBatch && current?.status === 'found' && (
        <button
          type="button"
          className="button secondary button-small batch-context-action"
          onClick={() => onViewBatch(id)}
        >
          View batch
        </button>
      )}
    </div>
  );
}
