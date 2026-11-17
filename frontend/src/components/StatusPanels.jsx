/** Loading, empty and error panels for the result column. */

/** Shown before the first inspection. */
export function EmptyState() {
  return (
    <section className="card empty-card" aria-labelledby="empty-title">
      <p className="step-label">Step 2</p>
      <h2 id="empty-title">Your result will appear here</h2>
      <p className="hint">
        Add a photo and run an inspection to get a pass or defect verdict, a confidence score, the
        defect severity and the recommended action.
      </p>
      <ul className="tips">
        <li>Use straight-on, well-lit photos of one bottle.</li>
        <li>The model was trained on MVTec AD bottle images.</li>
        <li>Results close to the cutoff are marked for manual review.</li>
      </ul>
    </section>
  );
}

/** Shown while the photo is uploading and the model is running. */
export function LoadingCard() {
  return (
    <section className="card loading-card" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div>
        <h2>Inspecting photo…</h2>
        <p className="hint">This can take a few seconds the first time while the model loads.</p>
      </div>
    </section>
  );
}

/** Shown when the API, the network or the model fails. */
export function ErrorBanner({ error, onReset }) {
  return (
    <section className="card error-card" role="alert">
      <p className="step-label">Something went wrong</p>
      <h2>The inspection did not finish</h2>
      <p className="error-message">{error?.message ?? 'Unknown error.'}</p>
      <button type="button" className="button secondary" onClick={onReset}>
        Try another photo
      </button>
    </section>
  );
}
