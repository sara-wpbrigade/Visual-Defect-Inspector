/** Photo picker, camera shortcut, drag-and-drop and client-side validation. */

import { useEffect, useRef, useState } from 'react';

import { CAMERA_ACCEPT, MAX_IMAGE_MEGABYTES, PHOTO_ACCEPT } from '../constants';
import { formatFileSize } from '../lib/format';
import { validateImage } from '../lib/validateImage';

/** Choose and preview one photo, then hand it to the inspection hook. */
export function UploadPanel({ onInspect, busy }) {
  const photoInput = useRef(null);
  const cameraInput = useRef(null);
  const previewUrlRef = useRef(null);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [problem, setProblem] = useState(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  function releasePreview() {
    if (!previewUrlRef.current) {
      return;
    }
    URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = null;
  }

  function choose(nextFile) {
    const message = validateImage(nextFile);
    releasePreview();
    setPreviewUrl(null);
    if (message) {
      setFile(null);
      setProblem(message);
      return;
    }
    const url = URL.createObjectURL(nextFile);
    previewUrlRef.current = url;
    setPreviewUrl(url);
    setFile(nextFile);
    setProblem(null);
  }

  function handleInput(event) {
    choose(event.target.files?.[0] ?? null);
    event.target.value = '';
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files?.[0] ?? null);
  }

  function handleDragOver(event) {
    event.preventDefault();
    setDragging(true);
  }

  function handleDragLeave() {
    setDragging(false);
  }

  return (
    <section className="card" aria-labelledby="upload-title">
      <p className="step-label">Step 1</p>
      <h2 id="upload-title">Add a bottle photo</h2>
      <p className="hint">
        JPEG or PNG, up to {MAX_IMAGE_MEGABYTES} MB. The photo is checked by the bottle anomaly
        model.
      </p>

      <div
        className={`dropzone${dragging ? ' dropzone-active' : ''}`}
        data-testid="dropzone"
        role="group"
        aria-label="Photo drop area"
        onDragEnter={handleDragOver}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {previewUrl ? (
          <img className="preview" src={previewUrl} alt="Selected bottle photo" />
        ) : (
          <div className="dropzone-empty">
            <span className="dropzone-icon" aria-hidden="true">
              +
            </span>
            <p>Drag a photo here</p>
            <p className="hint">or choose one below</p>
          </div>
        )}
      </div>

      {file && (
        <p className="file-chip" data-testid="file-chip">
          {file.name} · {formatFileSize(file.size)}
        </p>
      )}
      {problem && (
        <p className="field-error" role="alert">
          {problem}
        </p>
      )}

      <div className="upload-actions">
        <input
          ref={photoInput}
          className="visually-hidden"
          type="file"
          accept={PHOTO_ACCEPT}
          aria-label="Choose a photo"
          aria-hidden="true"
          tabIndex={-1}
          onChange={handleInput}
        />
        <input
          ref={cameraInput}
          className="visually-hidden"
          type="file"
          accept={CAMERA_ACCEPT}
          capture="environment"
          aria-label="Take a photo"
          aria-hidden="true"
          tabIndex={-1}
          onChange={handleInput}
        />
        <button
          type="button"
          className="button secondary"
          onClick={() => photoInput.current?.click()}
          disabled={busy}
        >
          Choose photo
        </button>
        <button
          type="button"
          className="button secondary"
          onClick={() => cameraInput.current?.click()}
          disabled={busy}
        >
          Take photo
        </button>
        <button
          type="button"
          className="button primary"
          onClick={() => onInspect(file)}
          disabled={!file || busy}
        >
          {busy ? 'Inspecting…' : 'Inspect photo'}
        </button>
      </div>
    </section>
  );
}
