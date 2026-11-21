/** The verdict, confidence, severity, next action, batch decision and PDF report for one inspection. */

import { useState } from 'react';

import {
  ACTION_HINTS,
  ACTION_LABELS,
  BATCH_DECISIONS,
  BATCH_DECISION_LABELS,
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
import { downloadPdfReport } from '../services/api';

/** True when the report has a defect type to show, or the verdict needs one. */
function showDefectType(assessment, content) {
  return content.defectType !== null || assessment.verdict === VERDICT.DEFECT;
}

/** The AI-written summary, findings and recommendations for this inspection. */
/** The AI-written summary, findings and recommendations for this inspection. */
function ReportSection({ assessment, report }) {
  const { content } = report;
  const region = assessment.location?.region ?? null;
  const hasConflict = Boolean(content.voiceNoteConflict);
  const needsReview = Boolean(report.manualReviewNotice);

  return (
    <details
      className="report"
      open={hasConflict || needsReview || assessment.verdict === VERDICT.DEFECT}
    >
      <summary className="report-summary-toggle">
        <span className="report-summary-title">{REPORT_SECTION_TITLE}</span>
        <span className={`report-badge report-badge-${report.source}`}>
          {REPORT_SOURCE_LABELS[report.source]}
        </span>
      </summary>

      {needsReview && (
        <p className="notice report-review" role="alert">
          <strong>{MANUAL_REVIEW_TITLE}.</strong> {report.manualReviewNotice}
        </p>
      )}

      {hasConflict && (
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
    </details>
  );
}

/** Display the transcribed operator voice note if present. */
function VoiceNoteCard({ voiceNote }) {
  if (!voiceNote || !voiceNote.text) {
    return null;
  }

  return (
    <div className="voice-result-box" aria-label="Transcribed voice note">
      <div className="voice-result-heading">
        <span className="voice-icon" aria-hidden="true">
          🎤
        </span>
        <span className="voice-title">Voice Note</span>
        {voiceNote.language && <span className="voice-lang-tag">Lang: {voiceNote.language}</span>}
        <span className="voice-status-tag">{voiceNote.status || 'Transcribed'}</span>
      </div>
      <blockquote className="voice-transcript">&ldquo;{voiceNote.text}&rdquo;</blockquote>
      {voiceNote.durationSeconds && (
        <span className="voice-duration">Duration: {Math.round(voiceNote.durationSeconds)}s</span>
      )}
    </div>
  );
}

/** Show the facts returned by the API in the order an operator needs them. */
export function ResultCard({ result, onReset }) {
  const { assessment, report } = result;
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(null);
  const [activeImageKind, setActiveImageKind] = useState('overlay');

  const tone = assessment.verdict === VERDICT.DEFECT ? 'defect' : 'pass';
  const verdict = VERDICT_LABELS[assessment.verdict] ?? assessment.verdict;
  const severity = SEVERITY_LABELS[assessment.severity] ?? assessment.severity;
  const action = ACTION_LABELS[assessment.action] ?? assessment.action;

  const pdfAvailable = result.reportPdfAvailable ?? Boolean(result.reportPdfUrl);
  const batchDecision = result.batchDecision
    ? (BATCH_DECISION_LABELS[result.batchDecision] ?? result.batchDecision)
    : null;
  const batchTone =
    result.batchDecision === BATCH_DECISIONS.REJECTED
      ? 'verdict-defect'
      : result.batchDecision === BATCH_DECISIONS.NEEDS_REVIEW
        ? 'verdict-review'
        : 'verdict-pass';

  async function handleDownloadPdf() {
    if (!pdfAvailable || downloading) {
      return;
    }
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadPdfReport(result.inspectionId);
    } catch (err) {
      setDownloadError(err?.message || 'Could not download PDF report.');
    } finally {
      setDownloading(false);
    }
  }

  const hasOverlay = Boolean(result.images?.overlay);
  const currentImageUrl =
    activeImageKind === 'overlay' && hasOverlay
      ? result.images.overlay
      : (result.images?.photo ?? null);

  return (
    <section
      className={`card result-card card--result--${tone} tone-${tone}`}
      aria-labelledby="result-title"
    >
      <div className="result-hero">
        <div className="result-hero-main">
          <div className="result-heading">
            <p className="step-label">Step 2</p>
            <h2 id="result-title">Inspection result</h2>
          </div>
          <span className="verdict-hero-label">
            {batchDecision ? `Batch decision: ${batchDecision}` : 'Inspection verdict'}
          </span>
          <span className="verdict-hero-value">{verdict}</span>
          <span className="verdict-hero-action">
            Recommended action: <strong>{action}</strong>
          </span>
        </div>

        <div className="result-hero-meta">
          <div className="badges-group">
            {batchDecision && (
              <span className={`verdict ${batchTone}`} title="Batch decision based on policy">
                Batch: {batchDecision}
              </span>
            )}
            <span className={`verdict verdict-${tone}`}>{verdict}</span>
          </div>
          <p className="result-id mono">{result.inspectionId}</p>
        </div>
      </div>

      {assessment.needsReview && (
        <p className="notice" role="status">
          <strong>Needs manual review.</strong> The anomaly score is close to the decision cutoff,
          so treat this result as provisional.
        </p>
      )}

      <div className="result-split">
        <div className="result-evidence">
          {currentImageUrl ? (
            <div className="result-image-panel">
              <div className="image-tabs">
                {hasOverlay && (
                  <button
                    type="button"
                    className={`tab-btn ${activeImageKind === 'overlay' ? 'active' : ''}`}
                    onClick={() => setActiveImageKind('overlay')}
                  >
                    Anomaly Overlay
                  </button>
                )}
                <button
                  type="button"
                  className={`tab-btn ${activeImageKind === 'photo' || !hasOverlay ? 'active' : ''}`}
                  onClick={() => setActiveImageKind('photo')}
                >
                  Original Photo
                </button>
              </div>
              <div className="result-image-wrapper">
                <img
                  src={currentImageUrl}
                  alt={
                    activeImageKind === 'overlay'
                      ? 'Anomaly overlay mask'
                      : 'Original inspected photo'
                  }
                  className="result-image"
                />
              </div>
            </div>
          ) : (
            <div className="result-image-empty">
              <span className="result-image-empty-mark" aria-hidden="true">
                ◫
              </span>
              <p>No stored image is available for this inspection.</p>
            </div>
          )}

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
            {result.category && (
              <div>
                <dt>Category</dt>
                <dd>{result.category}</dd>
              </div>
            )}
            {result.batchId && (
              <div>
                <dt>Batch ID</dt>
                <dd className="mono">{result.batchId}</dd>
              </div>
            )}
          </dl>

          {result.voiceNote && <VoiceNoteCard voiceNote={result.voiceNote} />}
        </div>

        <aside className="result-decision-panel">
          <div className="action-panel">
            <p className="action-panel-label">Recommended action</p>
            <p className="action-value">{action}</p>
            <p className="action-hint">
              {ACTION_HINTS[assessment.action] ?? "Follow your line's standard procedure."}
            </p>
          </div>

          <ReportSection assessment={assessment} report={report} />

          {downloadError && (
            <p className="field-error" role="alert">
              {downloadError}
            </p>
          )}

          <div className="result-actions">
            <button
              type="button"
              className="button secondary download-pdf-btn"
              onClick={handleDownloadPdf}
              disabled={!pdfAvailable || downloading}
              title={pdfAvailable ? 'Download PDF Report' : 'PDF Report is not available yet'}
            >
              {downloading ? 'Downloading PDF…' : 'Download PDF Report'}
            </button>
            <button type="button" className="button secondary" onClick={onReset}>
              Inspect another photo
            </button>
          </div>
        </aside>
      </div>
    </section>
  );
}
