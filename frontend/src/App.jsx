/** One-page upload, result flow, and batch history for the factory QC operator. */

import { useCallback, useEffect, useRef, useState } from 'react';

import { BatchContextStrip } from './components/BatchContextStrip';
import { BatchesHistoryView } from './components/BatchesHistoryView';
import { RecentInspections } from './components/RecentInspections';
import { ResultCard } from './components/ResultCard';
import { ResultModal } from './components/ResultModal';
import { ShortcutsModal } from './components/ShortcutsModal';
import { EmptyState, ErrorBanner, LoadingCard } from './components/StatusPanels';
import { UploadPanel } from './components/UploadPanel';
import { ACTION_LABELS, STATUS, VERDICT_LABELS, VIEW_TABS } from './constants';
import { useBackendHealth } from './hooks/useBackendHealth';
import { useInspection } from './hooks/useInspection';
import { getCategories, getInspection } from './services/api';

const THEME_KEY = 'vdi-theme';
const APP_VERSION = '0.1.0';

/** Read the current theme from <html data-theme>. */
function readTheme() {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

/** Build the screen-reader announcement for a finished inspection. */
function describeResult(result) {
  const verdict = VERDICT_LABELS[result.assessment.verdict] ?? result.assessment.verdict;
  const action = ACTION_LABELS[result.assessment.action] ?? result.assessment.action;
  return `Inspection finished: ${verdict}. Recommended action: ${action}.`;
}

/** Small inspection icon used by the navigation tab. */
function InspectionIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h2l1.2-2h4.6l1.2 2h2A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5v-8Z" />
      <circle cx="12" cy="12.5" r="3.2" />
    </svg>
  );
}

/** Small history icon used by the navigation tab. */
function HistoryIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11Z" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </svg>
  );
}

/** True when the current platform uses Cmd rather than Ctrl. */
function isMacPlatform() {
  if (typeof navigator === 'undefined') {
    return false;
  }
  return /Mac|iPhone|iPad/i.test(navigator.platform);
}

/** Render the upload panel, batch history, and current inspection state. */
export default function App() {
  const { status, result, error, inspect, reset } = useInspection();
  const backendHealth = useBackendHealth();
  const [formKey, setFormKey] = useState(0);
  const [viewTab, setViewTab] = useState(VIEW_TABS.INSPECT);
  const [theme, setTheme] = useState(readTheme);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [categoriesError, setCategoriesError] = useState(null);
  const [categoriesVersion, setCategoriesVersion] = useState(0);
  const [activeBatchId, setActiveBatchId] = useState('');
  const [batchViewFilter, setBatchViewFilter] = useState('');
  const [recentRefreshKey, setRecentRefreshKey] = useState(0);

  const [historyModal, setHistoryModal] = useState({
    open: false,
    loading: false,
    error: null,
    result: null,
  });

  const uploadRef = useRef(null);

  const retryCategories = useCallback(() => {
    setCategoriesError(null);
    setCategoriesVersion((value) => value + 1);
  }, []);

  useEffect(() => {
    let ignore = false;

    async function loadCategories() {
      try {
        const list = await getCategories();
        if (ignore) {
          return;
        }
        if (Array.isArray(list) && list.length > 0) {
          setCategories(list);
          setSelectedCategory((current) => current || list[0].id);
          setCategoriesError(null);
        } else {
          setCategoriesError('No inspection categories are available.');
        }
      } catch (err) {
        if (!ignore) {
          setCategoriesError(err?.message || 'Could not load inspection categories.');
        }
      }
    }

    loadCategories();
    return () => {
      ignore = true;
    };
  }, [categoriesVersion]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Ignore storage failures.
    }
  }, [theme]);

  const handleToggleTheme = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'));
  }, []);

  const handleReset = useCallback(() => {
    reset();
    setActiveBatchId('');
    setFormKey((value) => value + 1);
  }, [reset]);

  const handleInspect = useCallback(
    async (file, options) => {
      const inspection =
        options && Object.keys(options).length > 0
          ? await inspect(file, options)
          : await inspect(file);
      if (inspection?.batchId) {
        setActiveBatchId(inspection.batchId);
      }
      if (inspection) {
        setRecentRefreshKey((value) => value + 1);
      }
      return inspection;
    },
    [inspect],
  );

  const handleSelectCategory = useCallback((categoryId) => {
    setSelectedCategory(categoryId);
  }, []);

  const handleBatchIdChange = useCallback((batchId) => {
    setActiveBatchId(batchId ?? '');
  }, []);

  const handleViewBatch = useCallback((batchId) => {
    setBatchViewFilter(batchId);
    setViewTab(VIEW_TABS.BATCHES);
  }, []);

  const handleViewAllBatches = useCallback(() => {
    setBatchViewFilter('');
    setViewTab(VIEW_TABS.BATCHES);
  }, []);

  const handleOpenHistoricalInspection = useCallback(async (inspectionId) => {
    setHistoryModal({ open: true, loading: true, error: null, result: null });
    try {
      const detail = await getInspection(inspectionId);
      setHistoryModal({ open: true, loading: false, error: null, result: detail });
    } catch (err) {
      setHistoryModal({
        open: true,
        loading: false,
        error: err?.message || 'Could not load this inspection.',
        result: null,
      });
    }
  }, []);

  const handleCloseHistoryModal = useCallback(() => {
    setHistoryModal({ open: false, loading: false, error: null, result: null });
  }, []);

  const focusUploadPanel = useCallback(() => {
    setViewTab(VIEW_TABS.INSPECT);
    handleReset();
    // Wait a tick so the panel is mounted if we just switched tabs or cleared a result.
    window.requestAnimationFrame(() => {
      uploadRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      const input = document.querySelector('input[aria-label="Choose a photo"]');
      if (input instanceof HTMLInputElement) {
        input.click();
      }
    });
  }, [handleReset]);

  // Global keyboard shortcuts.
  useEffect(() => {
    function handleKey(event) {
      const mod = isMacPlatform() ? event.metaKey : event.ctrlKey;
      const target = event.target;
      const isTyping =
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable);

      if (mod && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setViewTab(VIEW_TABS.INSPECT);
      } else if (mod && event.key.toLowerCase() === 'h') {
        event.preventDefault();
        setViewTab(VIEW_TABS.BATCHES);
      } else if (mod && event.key.toLowerCase() === 'n') {
        event.preventDefault();
        focusUploadPanel();
      } else if (event.key === '?' && !isTyping) {
        event.preventDefault();
        setShortcutsOpen(true);
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [focusUploadPanel]);

  const announcement = status === STATUS.SUCCESS && result ? describeResult(result) : '';

  const healthLabel =
    backendHealth === 'ok'
      ? 'Backend connected'
      : backendHealth === 'down'
        ? 'Backend offline'
        : 'Checking backend';

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <p className="brand">
            <span className="brand-mark" aria-hidden="true">
              V
            </span>
            <span className="brand-text">Visual Defect Inspector</span>
            <span className="brand-text-short">Defect Inspector</span>
          </p>

          <nav className="nav-tabs" aria-label="Main Navigation">
            <button
              type="button"
              className={`nav-tab ${viewTab === VIEW_TABS.INSPECT ? 'active' : ''}`}
              onClick={() => setViewTab(VIEW_TABS.INSPECT)}
              aria-current={viewTab === VIEW_TABS.INSPECT ? 'page' : undefined}
            >
              <span className="nav-tab-icon">
                <InspectionIcon />
              </span>
              Inspection
            </button>
            <button
              type="button"
              className={`nav-tab ${viewTab === VIEW_TABS.BATCHES ? 'active' : ''}`}
              onClick={handleViewAllBatches}
              aria-current={viewTab === VIEW_TABS.BATCHES ? 'page' : undefined}
            >
              <span className="nav-tab-icon">
                <HistoryIcon />
              </span>
              Batches &amp; History
            </button>
          </nav>

          <div className="header-actions">
            <span
              className={`health-pill health-${backendHealth}`}
              title={healthLabel}
              aria-label={healthLabel}
            >
              <span className="health-dot" aria-hidden="true" />
              <span className="health-text">
                {backendHealth === 'ok'
                  ? 'Connected'
                  : backendHealth === 'down'
                    ? 'Offline'
                    : 'Checking'}
              </span>
            </span>

            <button
              type="button"
              className="icon-button"
              onClick={() => setShortcutsOpen(true)}
              aria-label="Keyboard shortcuts"
              title="Keyboard shortcuts (?)"
            >
              ?
            </button>

            <button
              type="button"
              className="theme-toggle"
              onClick={handleToggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            >
              <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>
            </button>

            <button
              type="button"
              className="button primary button-small header-cta"
              onClick={focusUploadPanel}
            >
              + New inspection
            </button>
          </div>
        </div>
      </header>

      {viewTab === VIEW_TABS.INSPECT ? (
        <>
          <div className="page-intro">
            <div className="page-intro-copy">
              <p className="step-label">Line inspection</p>
              <h1>Inspection</h1>
              <p className="page-subtitle">
                Photograph one item, choose its category, and get a decision with the evidence and
                the next action in one place.
              </p>
            </div>
            <BatchContextStrip batchId={activeBatchId} onViewBatch={handleViewBatch} />
          </div>

          <main className="inspection-view">
            <p className="visually-hidden" role="status">
              {announcement}
            </p>

            {status === STATUS.SUCCESS && result ? (
              <ResultCard result={result} onReset={handleReset} />
            ) : (
              <div className="layout">
                <div ref={uploadRef} className="upload-column">
                  <UploadPanel
                    key={formKey}
                    onInspect={handleInspect}
                    onBatchIdChange={handleBatchIdChange}
                    busy={status === STATUS.LOADING}
                    categories={categories}
                    categoriesError={categoriesError}
                    onRetryCategories={retryCategories}
                    selectedCategory={selectedCategory}
                    onSelectCategory={handleSelectCategory}
                  />
                </div>

                <div className="result-column">
                  {status === STATUS.IDLE && !result && (
                    <EmptyState
                      categoriesError={categoriesError}
                      onRetryCategories={retryCategories}
                    />
                  )}
                  {status === STATUS.LOADING && <LoadingCard />}
                  {status === STATUS.ERROR && (
                    <ErrorBanner
                      error={error}
                      onReset={handleReset}
                      onSelectCategory={handleSelectCategory}
                    />
                  )}
                </div>
              </div>
            )}

            <RecentInspections
              refreshKey={recentRefreshKey}
              onSelectInspection={handleOpenHistoricalInspection}
              onViewAll={handleViewAllBatches}
            />
          </main>
        </>
      ) : (
        <>
          <div className="page-intro">
            <div className="page-intro-copy">
              <p className="step-label">Quality overview</p>
              <h1>Batches &amp; history</h1>
              <p className="page-subtitle">
                Track batch decisions, review the items that need attention, and export the defect
                log.
              </p>
            </div>
          </div>
          <main className="layout-full">
            <BatchesHistoryView
              onSelectInspection={handleOpenHistoricalInspection}
              initialBatchFilter={batchViewFilter}
            />
          </main>
        </>
      )}

      {historyModal.open && (
        <ResultModal
          result={historyModal.result}
          loading={historyModal.loading}
          error={historyModal.error}
          onClose={handleCloseHistoryModal}
          onReset={handleCloseHistoryModal}
        />
      )}

      <ShortcutsModal open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />

      <footer className="app-footer">
        <span>MVTec AD · Bottle, Metal Nut, Screw · PatchCore</span>
        <span className="app-version">v{APP_VERSION}</span>
      </footer>
    </div>
  );
}
