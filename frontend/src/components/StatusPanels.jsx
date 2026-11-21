/** Loading, empty, error and skeleton panels for the interface. */

import { CATEGORY_ERROR_CODES } from '../constants';

/** Small inline illustration used on the empty state. */
function BottleGlyph() {
  return (
    <svg
      width="72"
      height="72"
      viewBox="0 0 72 72"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M28 8h16v10l4 8v32a6 6 0 0 1-6 6H30a6 6 0 0 1-6-6V26l4-8V8Z" />
      <path d="M24 30h24" />
      <circle cx="36" cy="46" r="5" strokeDasharray="2 3" />
    </svg>
  );
}

/** Shown before the first inspection. */
export function EmptyState({ categoriesError = null, onRetryCategories }) {
  return (
    <section className="card empty-card" aria-labelledby="empty-title">
      <div className="empty-illustration">
        <BottleGlyph />
      </div>
      <p className="step-label">Step 2</p>
      <h1 id="empty-title" className="empty-title">
        No inspection yet
      </h1>
      <p className="hint">Upload a photo to get a verdict and a recommended action.</p>
      <ul className="tips">
        <li>Straight-on, well-lit photos of one item.</li>
        <li>Supported: Bottle, Metal Nut, Screw.</li>
        <li>Low-confidence results are flagged for review.</li>
      </ul>
      {categoriesError && (
        <>
          <p className="field-error" role="alert">
            {categoriesError}
          </p>
          {onRetryCategories && (
            <button
              type="button"
              className="button secondary button-small"
              onClick={onRetryCategories}
            >
              Retry
            </button>
          )}
        </>
      )}
    </section>
  );
}

/** Shown while the photo is uploading and the model is running. */
export function LoadingCard() {
  return (
    <section className="card loading-card" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div>
        <h2>Inspecting…</h2>
        <p className="hint">First run loads the model, then it's fast.</p>
      </div>
    </section>
  );
}

/** Shown when the API, the network or the model fails. */
export function ErrorBanner({ error, onReset, onSelectCategory }) {
  const isCategoryMismatch =
    error?.code === CATEGORY_ERROR_CODES.CATEGORY_MISMATCH ||
    error?.code === CATEGORY_ERROR_CODES.UNKNOWN_CATEGORY;
  const supported = error?.supportedCategories ?? [];

  return (
    <section className="card error-card" role="alert">
      <p className="step-label">
        {isCategoryMismatch ? 'Category Verification' : 'Something went wrong'}
      </p>
      <h2>
        {isCategoryMismatch ? 'Category Verification Mismatch' : 'The inspection did not finish'}
      </h2>
      <p className="error-message">{error?.message ?? 'Unknown error.'}</p>

      {isCategoryMismatch && (
        <div className="category-error-advice">
          <p className="hint">Pick a category that matches the photo:</p>
          {supported.length > 0 && (
            <div className="supported-cats-list">
              {supported.map((cat) => {
                const id = cat.id;
                const label = cat.displayName ?? cat.display_name ?? id;
                return (
                  <button
                    key={id}
                    type="button"
                    className="button secondary button-small"
                    onClick={() => onSelectCategory?.(id)}
                  >
                    Switch to {label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      <button type="button" className="button secondary" onClick={onReset}>
        Try another photo
      </button>
    </section>
  );
}

/** Skeleton loading card for smooth transitions during data fetches. */
export function SkeletonCard() {
  return (
    <div className="card skeleton-card" aria-hidden="true">
      <div className="skeleton-line skeleton-title" />
      <div className="skeleton-line skeleton-subtitle" />
      <div className="skeleton-grid">
        <div className="skeleton-box" />
        <div className="skeleton-box" />
        <div className="skeleton-box" />
        <div className="skeleton-box" />
      </div>
    </div>
  );
}
