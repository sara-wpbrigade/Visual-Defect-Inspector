/** One-page upload and result flow for the factory QC operator. */

import { useCallback, useState } from 'react';

import { ResultCard } from './components/ResultCard';
import { EmptyState, ErrorBanner, LoadingCard } from './components/StatusPanels';
import { UploadPanel } from './components/UploadPanel';
import { ACTION_LABELS, STATUS, VERDICT_LABELS } from './constants';
import { useInspection } from './hooks/useInspection';

/** Build the screen-reader announcement for a finished inspection. */
function describeResult(result) {
  const verdict = VERDICT_LABELS[result.assessment.verdict] ?? result.assessment.verdict;
  const action = ACTION_LABELS[result.assessment.action] ?? result.assessment.action;
  return `Inspection finished: ${verdict}. Recommended action: ${action}.`;
}

/** Render the upload panel and the current inspection state. */
export default function App() {
  const { status, result, error, inspect, reset } = useInspection();
  const [formKey, setFormKey] = useState(0);

  const handleReset = useCallback(() => {
    reset();
    setFormKey((value) => value + 1);
  }, [reset]);

  const announcement = status === STATUS.SUCCESS && result ? describeResult(result) : '';

  return (
    <div className="app">
      <header className="app-header">
        <p className="brand">
          <span className="brand-dot" aria-hidden="true" />
          Visual Defect Inspector
        </p>
        <h1>Bottle QC in one photo</h1>
        <p className="subtitle">
          PatchCore scores the bottle for anomalies and the factory QC rules turn that score into a
          pass or reject decision.
        </p>
      </header>

      <main className="layout">
        <p className="visually-hidden" role="status">
          {announcement}
        </p>
        <UploadPanel key={formKey} onInspect={inspect} busy={status === STATUS.LOADING} />

        <div className="result-column">
          {status === STATUS.IDLE && <EmptyState />}
          {status === STATUS.LOADING && <LoadingCard />}
          {status === STATUS.ERROR && <ErrorBanner error={error} onReset={handleReset} />}
          {status === STATUS.SUCCESS && result && (
            <ResultCard result={result} onReset={handleReset} />
          )}
        </div>
      </main>

      <footer className="app-footer">
        <span>MVTec AD · bottle · PatchCore</span>
        <span>Facts come from the model and the persona rules.</span>
      </footer>
    </div>
  );
}
