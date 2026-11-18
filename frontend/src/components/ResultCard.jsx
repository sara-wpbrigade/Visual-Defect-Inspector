/** The verdict, confidence, severity and next action for one inspection. */

import {
  ACTION_HINTS,
  ACTION_LABELS,
  DEFECT_TYPE_ESTIMATE_LABEL,
  DEFECT_TYPE_LABEL,
  DEFECT_TYPE_NOT_DETERMINED,
  FLAGGED_AREA_LABEL,
  MANUAL_REVIEW_TITLE,
  REPORT_FINDINGS_TITLE,
  REPORT_RECOMMENDATIONS_TITLE,
  REPORT_SECTION_TITLE,
  REPORT_SOURCE_LABELS,
  SEVERITY_LABELS,
  VERDICT,
  VERDICT_LABELS,
  VOICE_CONFLICT_LABEL,
} from '../constants';
import { formatPercent, formatScore } from '../lib/format';

/** True when the report has a defect type to show, or the verdict needs one. */
function showDefectType(assessment, content) {
  return content.defectType !== null || assessment.verdict === VERDICT.DEFECT;
}

/** The AI-written summary, findings and recommendations for this inspection. */
function ReportSection({ assessment, report }) {
  const { content } = report;
  const region = assessment.location?.region ?? null;

  return (
    <section className="report" aria-labelledby="report-title">
      <div className="report-heading">
        <h3 id="report-title">{REPORT_SECTION_TITLE}</h3>
        <span className={`report-badge report-badge-${report.source}`}>
          {REPORT_SOURCE_LABELS[report.source]}
        </span>
      </div>

      {report.manualReviewNotice && (
        <p className="notice report-review" role="alert">
          <strong>{MANUAL_REVIEW_TITLE}.</strong> {report.manualReviewNotice}
        </p>
      )}

      {content.voiceNoteConflict && (
        <p className="notice report-conflict" role="status">
          <strong>{VOICE_CONFLICT_LABEL}.</strong> {content.voiceNoteConflict}
        </p>
      )}

      <p className="report-summary">{content.summary}</p>

      <div className="report-meta">
        {showDefectType(assessment, content) && (
          <p className="defect-chip">
            <span className="defect-chip-text">
              {DEFECT_TYPE_LABEL}: {content.defectType ?? DEFECT_TYPE_NOT_DETERMINED}
            </span>
            {content.defectType !== null && (
              <span className="defect-chip-note">{DEFECT_TYPE_ESTIMATE_LABEL}</span>
            )}
          </p>
        )}
        {region && (
          <p className="report-location">
            {FLAGGED_AREA_LABEL}: {region}
          </p>
        )}
      </div>

      <h4>{REPORT_FINDINGS_TITLE}</h4>
      <ul className="report-list">
        {content.findings.map((finding, index) => (
          <li key={index}>{finding}</li>
        ))}
      </ul>

      <h4>{REPORT_RECOMMENDATIONS_TITLE}</h4>
      <ul className="report-list">
        {content.recommendations.map((recommendation, index) => (
          <li key={index}>{recommendation}</li>
        ))}
      </ul>
    </section>
  );
}

/** Show the facts returned by the API in the order an operator needs them. */
export function ResultCard({ result, onReset }) {
  const { assessment, report } = result;
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

      <ReportSection assessment={assessment} report={report} />

      <div className="result-actions">
        <button type="button" className="button secondary" onClick={onReset}>
          Inspect another photo
        </button>
      </div>
    </section>
  );
}
