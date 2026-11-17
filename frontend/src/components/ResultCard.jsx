/** The verdict, confidence, severity and next action for one inspection. */

import {
  ACTION_HINTS,
  ACTION_LABELS,
  SEVERITY_LABELS,
  VERDICT,
  VERDICT_LABELS,
} from '../constants';
import { formatPercent, formatScore } from '../lib/format';

/** Show the facts returned by the API in the order an operator needs them. */
export function ResultCard({ result, onReset }) {
  const { assessment } = result;
  const tone = assessment.verdict === VERDICT.DEFECT ? 'defect' : 'pass';
  const verdict = VERDICT_LABELS[assessment.verdict] ?? assessment.verdict;
  const severity = SEVERITY_LABELS[assessment.severity] ?? assessment.severity;
  const action = ACTION_LABELS[assessment.action] ?? assessment.action;

  return (
    <section className={`card result-card tone-${tone}`} aria-labelledby="result-title">
      <div className="result-heading">
        <div>
          <p className="step-label">Step 2</p>
          <h2 id="result-title">Inspection result</h2>
        </div>
        <span className={`verdict verdict-${tone}`}>{verdict}</span>
      </div>

      {assessment.needsReview && (
        <p className="notice" role="status">
          <strong>Needs manual review.</strong> The anomaly score is close to the decision cutoff,
          so treat this result as provisional.
        </p>
      )}

      <p className="verdict-line">
        <span className="action-value">{action}</span>
        <span className="action-hint">
          {ACTION_HINTS[assessment.action] ?? "Follow your line's standard procedure."}
        </span>
      </p>

      <div className="confidence-block">
        <div className="confidence-label">
          <span>Confidence</span>
          <strong>{formatPercent(assessment.confidence)}</strong>
        </div>
        <div className="meter" aria-hidden="true">
          <span style={{ width: formatPercent(assessment.confidence) }} />
        </div>
      </div>

      <dl className="facts">
        <div>
          <dt>Severity</dt>
          <dd>{severity}</dd>
        </div>
        <div>
          <dt>Flagged area</dt>
          <dd>{formatPercent(assessment.areaRatio)}</dd>
        </div>
        <div>
          <dt>Anomaly score</dt>
          <dd>{formatScore(result.score)}</dd>
        </div>
        <div>
          <dt>Inspection ID</dt>
          <dd className="mono">{result.inspectionId}</dd>
        </div>
      </dl>

      <div className="result-actions">
        <button type="button" className="button secondary" onClick={onReset}>
          Inspect another photo
        </button>
      </div>
    </section>
  );
}
