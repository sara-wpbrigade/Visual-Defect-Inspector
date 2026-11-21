/** Batch dashboard, batch detail, CSV export and inspection history. */

import { useEffect, useRef, useState } from 'react';

import {
  ACTION_LABELS,
  BATCH_DECISIONS,
  BATCH_DECISION_LABELS,
  SEVERITY_LABELS,
  VERDICT,
  VERDICT_LABELS,
} from '../constants';
import { formatPercent, relativeTime } from '../lib/format';
import {
  downloadPdfReport,
  exportDefectLogCsv,
  getBatch,
  getBatches,
  getInspections,
} from '../services/api';
import { Toast } from './Toast';

/** Pick whichever timestamp field the API returns, if any. */
function itemTimestamp(item) {
  return item?.createdAt ?? item?.created_at ?? item?.timestamp ?? null;
}

/** True when a timestamp falls on the current local calendar day. */
function isToday(value) {
  if (!value) {
    return false;
  }
  const date = new Date(value);
  return !Number.isNaN(date.getTime()) && date.toDateString() === new Date().toDateString();
}

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

/** One headline number on the quality dashboard. */
function KpiCard({ label, value, hint, tone = '' }) {
  return (
    <div className={`kpi-card ${tone}`}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {hint && <span className="kpi-hint">{hint}</span>}
    </div>
  );
}

/** Batch dashboard, inline batch detail, and the full inspection history. */
export function BatchesHistoryView({ onSelectInspection, initialBatchFilter = '' }) {
  const [batches, setBatches] = useState([]);
  const [loadingBatches, setLoadingBatches] = useState(true);
  const [batchError, setBatchError] = useState(null);
  const [inspectionsToday, setInspectionsToday] = useState(null);

  const [inspections, setInspections] = useState([]);
  const [totalInspections, setTotalInspections] = useState(0);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [historyError, setHistoryError] = useState(null);

  const [selectedBatchId, setSelectedBatchId] = useState(initialBatchFilter);
  const [batchDetail, setBatchDetail] = useState(null);
  const detailRef = useRef(null);

  const [batchFilter, setBatchFilter] = useState(initialBatchFilter);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [onlyDefects, setOnlyDefects] = useState(true);
  const [offset, setOffset] = useState(0);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const limit = 20;

  const [exportingBatchId, setExportingBatchId] = useState(null);
  const [exportingAll, setExportingAll] = useState(false);
  const [downloadingPdfId, setDownloadingPdfId] = useState(null);
  const [toast, setToast] = useState(null);

  const effectiveBatchId = selectedBatchId || batches[0]?.batchId || '';
  const detail = batchDetail?.batchId === effectiveBatchId ? batchDetail : null;

  function showToast(text, tone = 'info') {
    setToast({ text, tone });
  }

  function triggerRefresh() {
    setLoadingBatches(true);
    setLoadingHistory(true);
    setRefreshTrigger((prev) => prev + 1);
  }

  useEffect(() => {
    let ignore = false;

    async function loadBatches() {
      try {
        const data = await getBatches({ limit: 50, offset: 0 });
        if (!ignore) {
          setBatches(data);
          setBatchError(null);
        }
      } catch (err) {
        if (!ignore) {
          setBatchError(err?.message || 'Could not load batches.');
        }
      } finally {
        if (!ignore) {
          setLoadingBatches(false);
        }
      }
    }

    loadBatches();
    return () => {
      ignore = true;
    };
  }, [refreshTrigger]);

  useEffect(() => {
    let ignore = false;

    async function loadToday() {
      try {
        const data = await getInspections({ limit: 100, offset: 0 });
        if (!ignore) {
          setInspectionsToday(data.items.filter((item) => isToday(itemTimestamp(item))).length);
        }
      } catch {
        if (!ignore) {
          setInspectionsToday(null);
        }
      }
    }

    loadToday();
    return () => {
      ignore = true;
    };
  }, [refreshTrigger]);

  useEffect(() => {
    if (!effectiveBatchId) {
      return undefined;
    }
    let ignore = false;

    async function loadDetail() {
      try {
        const data = await getBatch(effectiveBatchId);
        if (!ignore) {
          setBatchDetail({ batchId: effectiveBatchId, data });
        }
      } catch (err) {
        if (!ignore) {
          setBatchDetail({
            batchId: effectiveBatchId,
            error: err?.message || 'Could not load this batch.',
          });
        }
      }
    }

    loadDetail();
    return () => {
      ignore = true;
    };
  }, [effectiveBatchId, refreshTrigger]);

  useEffect(() => {
    let ignore = false;

    async function loadHistory() {
      try {
        const data = await getInspections({
          limit,
          offset,
          batchId: batchFilter.trim() || null,
          category: categoryFilter.trim() || null,
        });
        if (!ignore) {
          setInspections(data.items);
          setTotalInspections(data.total);
          setHistoryError(null);
        }
      } catch (err) {
        if (!ignore) {
          setHistoryError(err?.message || 'Could not load inspection history.');
        }
      } finally {
        if (!ignore) {
          setLoadingHistory(false);
        }
      }
    }

    loadHistory();
    return () => {
      ignore = true;
    };
  }, [batchFilter, categoryFilter, offset, limit, refreshTrigger]);

  async function handleExportBatch(batchId) {
    setExportingBatchId(batchId);
    try {
      await exportDefectLogCsv({ batchId, onlyDefects });
      showToast(`Exported CSV for ${batchId}.`, 'success');
    } catch (err) {
      showToast(`Export failed: ${err?.message}`, 'error');
    } finally {
      setExportingBatchId(null);
    }
  }

  async function handleExportAll() {
    setExportingAll(true);
    try {
      await exportDefectLogCsv({
        batchId: batchFilter.trim() || null,
        category: categoryFilter.trim() || null,
        onlyDefects,
      });
      showToast('Exported defect log CSV.', 'success');
    } catch (err) {
      showToast(`Export failed: ${err?.message}`, 'error');
    } finally {
      setExportingAll(false);
    }
  }

  async function handleDownloadPdf(inspectionId) {
    setDownloadingPdfId(inspectionId);
    try {
      await downloadPdfReport(inspectionId);
      showToast('PDF report downloaded.', 'success');
    } catch (err) {
      showToast(`PDF download failed: ${err?.message}`, 'error');
    } finally {
      setDownloadingPdfId(null);
    }
  }

  function handleFilterBatch(batchId) {
    setBatchFilter(batchId);
    setOffset(0);
  }

  function selectBatch(batchId) {
    setSelectedBatchId(batchId);
    const narrow =
      typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 1080px)').matches;
    if (narrow) {
      window.requestAnimationFrame(() => {
        detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  }

  const totals = batches.reduce(
    (acc, batch) => ({
      items: acc.items + (batch.itemCount ?? 0),
      defects: acc.defects + (batch.defectCount ?? 0),
      passes: acc.passes + (batch.passCount ?? 0),
      reviews: acc.reviews + (batch.reviewCount ?? 0),
    }),
    { items: 0, defects: 0, passes: 0, reviews: 0 },
  );
  const passRate = totals.items > 0 ? totals.passes / totals.items : null;
  const hasTimestamp = inspections.some((item) => Boolean(itemTimestamp(item)));

  return (
    <div className="batches-history-container">
      <section className="kpi-grid" aria-label="Quality dashboard">
        <KpiCard
          label="Batches"
          value={batches.length}
          hint={`${totals.items} ${totals.items === 1 ? 'inspection' : 'inspections'} tracked`}
        />
        <KpiCard label="Inspections" value={totals.items} hint="In the current batch window" />
        <KpiCard
          label="Pass rate"
          value={passRate === null ? '—' : formatPercent(passRate)}
          hint="Passed / inspected"
          tone="kpi-pass"
        />
        <KpiCard
          label="Defects"
          value={totals.defects}
          hint="Items to rework or reject"
          tone="kpi-defect"
        />
        <KpiCard
          label="Needs review"
          value={totals.reviews}
          hint="Waiting on an operator"
          tone="kpi-review"
        />
        <KpiCard
          label="Today"
          value={inspectionsToday === null ? '—' : inspectionsToday}
          hint="Inspections so far"
        />
      </section>

      <div className="batch-workspace">
        <section className="card card--batches batch-list-card" aria-labelledby="batches-title">
          <div className="section-header">
            <div>
              <p className="step-label">Batch management</p>
              <h2 id="batches-title">Batches &amp; quality decisions</h2>
            </div>
            <button
              type="button"
              className="button secondary button-small"
              onClick={triggerRefresh}
              disabled={loadingBatches}
            >
              {loadingBatches ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>

          {batchError && (
            <p className="field-error" role="alert">
              {batchError}
            </p>
          )}

          {loadingBatches && batches.length === 0 ? (
            <div className="history-skeleton" aria-hidden="true">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="history-skeleton-row batch-skeleton-row">
                  <div className="skeleton-line" style={{ width: '35%', height: 12 }} />
                  <div className="skeleton-box" style={{ width: 64, height: 22 }} />
                  <div className="skeleton-line" style={{ width: '20%', height: 12 }} />
                </div>
              ))}
            </div>
          ) : batches.length === 0 ? (
            <p className="empty-history-state">No batches yet. Run an inspection to start one.</p>
          ) : (
            <div className="table-responsive">
              <table className="history-table batch-table">
                <thead>
                  <tr>
                    <th>Batch</th>
                    <th>Decision</th>
                    <th>Items</th>
                    <th>Defects</th>
                    <th>Passed</th>
                    <th>Review</th>
                    <th>Last activity</th>
                    <th>
                      <span className="visually-hidden">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((batch) => {
                    const tone = decisionTone(batch.decision);
                    const label = BATCH_DECISION_LABELS[batch.decision] ?? batch.decision;
                    const isActive = effectiveBatchId === batch.batchId;
                    return (
                      <tr
                        key={batch.batchId}
                        className={isActive ? 'batch-row-active' : ''}
                        onClick={() => selectBatch(batch.batchId)}
                      >
                        <td data-label="Batch">
                          <button
                            type="button"
                            className="batch-link mono"
                            onClick={(event) => {
                              event.stopPropagation();
                              selectBatch(batch.batchId);
                            }}
                          >
                            {batch.batchId}
                          </button>
                        </td>
                        <td data-label="Decision">
                          <span className={`verdict ${tone}`}>{label}</span>
                        </td>
                        <td data-label="Items">{batch.itemCount}</td>
                        <td data-label="Defects" className="batch-count-defect">
                          {batch.defectCount}
                        </td>
                        <td data-label="Passed" className="batch-count-pass">
                          {batch.passCount}
                        </td>
                        <td data-label="Review" className="batch-count-review">
                          {batch.reviewCount}
                        </td>
                        <td data-label="Last activity">
                          {relativeTime(batch.lastInspectionAt) || '—'}
                        </td>
                        <td data-label="Export" className="batch-row-action">
                          <button
                            type="button"
                            className="button secondary button-small"
                            aria-label={`Export batch ${batch.batchId} CSV`}
                            onClick={(event) => {
                              event.stopPropagation();
                              handleExportBatch(batch.batchId);
                            }}
                            disabled={exportingBatchId === batch.batchId}
                          >
                            {exportingBatchId === batch.batchId ? '…' : 'CSV'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside
          className="card card--batches batch-detail-card"
          aria-labelledby="batch-detail-title"
        >
          <div className="section-header batch-detail-header">
            <div>
              <p className="step-label">Batch detail</p>
              <h2 id="batch-detail-title" className="mono batch-detail-title">
                {effectiveBatchId || 'No batch selected'}
              </h2>
            </div>
            {detail?.data && (
              <span className={`verdict ${decisionTone(detail.data.summary.decision)}`}>
                {BATCH_DECISION_LABELS[detail.data.summary.decision] ??
                  detail.data.summary.decision}
              </span>
            )}
          </div>

          {!effectiveBatchId && (
            <p className="hint">Select a batch to see its inspections and decision.</p>
          )}

          {effectiveBatchId && !detail && <p className="hint">Loading batch…</p>}

          {detail?.error && (
            <p className="field-error" role="alert">
              {detail.error}
            </p>
          )}

          {detail?.data && (
            <>
              <p className="batch-detail-summary">
                {detail.data.summary.itemCount}{' '}
                {detail.data.summary.itemCount === 1 ? 'inspection' : 'inspections'} ·{' '}
                {detail.data.summary.defectCount}{' '}
                {detail.data.summary.defectCount === 1 ? 'defect' : 'defects'} ·{' '}
                {detail.data.summary.reviewCount}{' '}
                {detail.data.summary.reviewCount === 1 ? 'needs review' : 'need review'}
              </p>

              <div className="batch-detail-actions">
                <button
                  type="button"
                  className="button secondary button-small"
                  onClick={() => handleFilterBatch(detail.data.summary.batchId)}
                >
                  Filter history
                </button>
                <button
                  type="button"
                  className="button secondary button-small"
                  onClick={() => handleExportBatch(detail.data.summary.batchId)}
                  disabled={exportingBatchId === detail.data.summary.batchId}
                >
                  {exportingBatchId === detail.data.summary.batchId ? 'Exporting…' : 'Export CSV'}
                </button>
              </div>

              {detail.data.items.length === 0 ? (
                <p className="empty-history-state">No inspections in this batch.</p>
              ) : (
                <div className="batch-detail-list">
                  {detail.data.items.map((item) => {
                    const tone = item.verdict === VERDICT.DEFECT ? 'defect' : 'pass';
                    return (
                      <div key={item.id} className="batch-detail-item">
                        {item.thumbnailUrl ? (
                          <button
                            type="button"
                            className="history-thumb-btn"
                            aria-label={`Open inspection ${item.id}`}
                            onClick={() => onSelectInspection?.(item.id)}
                          >
                            <img
                              className="history-thumb"
                              src={item.thumbnailUrl}
                              alt={`Thumbnail for inspection ${item.id}`}
                              loading="lazy"
                            />
                          </button>
                        ) : (
                          <span className="thumb-placeholder" aria-hidden="true" />
                        )}

                        <div className="batch-detail-item-main">
                          <span className={`verdict verdict-${tone}`}>
                            {VERDICT_LABELS[item.verdict] ?? item.verdict}
                          </span>
                          <span className="batch-detail-meta">
                            {SEVERITY_LABELS[item.severity] ?? item.severity} ·{' '}
                            {ACTION_LABELS[item.action] ?? item.action}
                          </span>
                          <span className="batch-detail-meta">
                            {relativeTime(item.createdAt) || '—'}
                          </span>
                        </div>

                        <div className="batch-detail-item-actions">
                          <button
                            type="button"
                            className="button secondary button-small"
                            aria-label={`Download PDF for ${item.id}`}
                            onClick={() => handleDownloadPdf(item.id)}
                            disabled={!item.reportPdfAvailable || downloadingPdfId === item.id}
                          >
                            {downloadingPdfId === item.id ? '…' : 'PDF'}
                          </button>
                          {onSelectInspection && (
                            <button
                              type="button"
                              className="button secondary button-small"
                              aria-label={`View inspection ${item.id}`}
                              onClick={() => onSelectInspection(item.id)}
                            >
                              View
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </aside>
      </div>

      <section className="card card--batches" aria-labelledby="history-title">
        <div className="section-header">
          <div>
            <p className="step-label">Audit log</p>
            <h2 id="history-title">Inspection history</h2>
          </div>
          <div className="export-controls">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={onlyDefects}
                onChange={(event) => setOnlyDefects(event.target.checked)}
              />
              Only defects
            </label>
            <button
              type="button"
              className="button primary button-small"
              onClick={handleExportAll}
              disabled={exportingAll}
            >
              {exportingAll ? 'Exporting…' : 'Export CSV'}
            </button>
          </div>
        </div>

        <div className="history-filter-bar">
          <div className="filter-item">
            <label htmlFor="history-batch-filter" className="filter-label">
              Batch:
            </label>
            <input
              id="history-batch-filter"
              type="text"
              placeholder="Filter by batch ID…"
              className="text-input text-input-small"
              value={batchFilter}
              onChange={(event) => {
                setBatchFilter(event.target.value);
                setOffset(0);
              }}
            />
            {batchFilter && (
              <button
                type="button"
                className="button-clear"
                onClick={() => {
                  setBatchFilter('');
                  setOffset(0);
                }}
                aria-label="Clear batch filter"
              >
                ×
              </button>
            )}
          </div>

          <div className="filter-item">
            <label htmlFor="history-cat-filter" className="filter-label">
              Category:
            </label>
            <select
              id="history-cat-filter"
              className="select-input select-input-small"
              value={categoryFilter}
              onChange={(event) => {
                setCategoryFilter(event.target.value);
                setOffset(0);
              }}
            >
              <option value="">All Categories</option>
              <option value="bottle">Bottle</option>
              <option value="metal_nut">Metal Nut</option>
              <option value="screw">Screw</option>
            </select>
          </div>

          <span className="history-count">
            {totalInspections} {totalInspections === 1 ? 'inspection' : 'inspections'}
          </span>
        </div>

        {historyError && (
          <p className="field-error" role="alert">
            {historyError}
          </p>
        )}

        {loadingHistory && inspections.length === 0 ? (
          <div className="history-skeleton" aria-hidden="true">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="history-skeleton-row">
                <div className="skeleton-box" style={{ width: 40, height: 40 }} />
                <div className="skeleton-line" style={{ width: '20%', height: 12 }} />
                <div className="skeleton-line" style={{ width: '15%', height: 12 }} />
                <div className="skeleton-line" style={{ width: '25%', height: 12 }} />
              </div>
            ))}
          </div>
        ) : inspections.length === 0 ? (
          <div className="empty-history-state">
            <p>No inspections match your filters.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Photo</th>
                  <th>ID</th>
                  <th>Category</th>
                  <th>Batch</th>
                  <th>Verdict</th>
                  <th>Severity</th>
                  <th>Action</th>
                  <th>Confidence</th>
                  {hasTimestamp && <th>When</th>}
                  <th>PDF</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {inspections.map((item) => {
                  const tone = item.verdict === VERDICT.DEFECT ? 'defect' : 'pass';
                  const verdictText = VERDICT_LABELS[item.verdict] ?? item.verdict;
                  const severityText = SEVERITY_LABELS[item.severity] ?? item.severity;
                  const actionText = ACTION_LABELS[item.action] ?? item.action;
                  const isPdfDownloading = downloadingPdfId === item.id;
                  const timestamp = itemTimestamp(item);

                  return (
                    <tr key={item.id}>
                      <td className="thumbnail-cell" data-label="Photo">
                        {item.thumbnailUrl ? (
                          onSelectInspection ? (
                            <button
                              type="button"
                              className="history-thumb-btn"
                              onClick={() => onSelectInspection(item.id)}
                              aria-label={`Open inspection ${item.id}`}
                            >
                              <img
                                src={item.thumbnailUrl}
                                alt={`Thumbnail for inspection ${item.id}`}
                                className="history-thumb"
                                loading="lazy"
                              />
                            </button>
                          ) : (
                            <img
                              src={item.thumbnailUrl}
                              alt={`Thumbnail for inspection ${item.id}`}
                              className="history-thumb"
                              loading="lazy"
                            />
                          )
                        ) : (
                          <div className="thumb-placeholder" aria-hidden="true" />
                        )}
                      </td>
                      <td className="mono mono-cell" title={item.id} data-label="ID">
                        {item.id.slice(0, 8)}…
                      </td>
                      <td data-label="Category">
                        <span className="cat-chip">{item.category}</span>
                      </td>
                      <td className="mono mono-cell" data-label="Batch">
                        {item.batchId ?? '—'}
                      </td>
                      <td data-label="Verdict">
                        <span className={`verdict verdict-${tone}`}>{verdictText}</span>
                      </td>
                      <td data-label="Severity">{severityText}</td>
                      <td data-label="Action">
                        <span className="action-tag">{actionText}</span>
                      </td>
                      <td data-label="Confidence">{formatPercent(item.confidence)}</td>
                      {hasTimestamp && (
                        <td data-label="When" title={timestamp ? String(timestamp) : ''}>
                          {relativeTime(timestamp) || '—'}
                        </td>
                      )}
                      <td data-label="PDF">
                        <button
                          type="button"
                          className="button secondary button-small"
                          onClick={() => handleDownloadPdf(item.id)}
                          disabled={!item.reportPdfAvailable || isPdfDownloading}
                          title={
                            item.reportPdfAvailable
                              ? 'Download PDF Report'
                              : 'PDF Report not generated'
                          }
                        >
                          {isPdfDownloading ? '…' : 'PDF'}
                        </button>
                      </td>
                      <td data-label="Actions">
                        {onSelectInspection && (
                          <button
                            type="button"
                            className="button secondary button-small"
                            onClick={() => onSelectInspection(item.id)}
                          >
                            View
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {totalInspections > limit && (
          <div className="pagination-bar">
            <button
              type="button"
              className="button secondary button-small"
              disabled={offset === 0 || loadingHistory}
              onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
            >
              Previous
            </button>
            <span className="pagination-info">
              {offset + 1}–{Math.min(offset + limit, totalInspections)} of {totalInspections}
            </span>
            <button
              type="button"
              className="button secondary button-small"
              disabled={offset + limit >= totalInspections || loadingHistory}
              onClick={() => setOffset((prev) => prev + limit)}
            >
              Next
            </button>
          </div>
        )}
      </section>

      {toast && <Toast message={toast.text} tone={toast.tone} onClose={() => setToast(null)} />}
    </div>
  );
}
