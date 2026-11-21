/** Photo picker, category selector, batch assignment, voice note recorder and validation. */

import { useEffect, useRef, useState } from 'react';

import {
  ALLOWED_AUDIO_TYPES,
  AUDIO_ACCEPT,
  BATCH_ID_REGEX,
  CAMERA_ACCEPT,
  MAX_AUDIO_BYTES,
  MAX_AUDIO_MEGABYTES,
  MAX_AUDIO_SECONDS,
  MAX_IMAGE_MEGABYTES,
  PHOTO_ACCEPT,
} from '../constants';
import { formatFileSize } from '../lib/format';
import { validateImage } from '../lib/validateImage';

/** Choose category, batch, preview photo and optional voice note, then trigger inspection. */
export function UploadPanel({
  onInspect,
  busy,
  categories = [],
  categoriesError = null,
  onRetryCategories,
  selectedCategory = '',
  onSelectCategory,
  onBatchIdChange,
}) {
  const photoInput = useRef(null);
  const cameraInput = useRef(null);
  const audioInput = useRef(null);
  const previewUrlRef = useRef(null);
  const audioUrlRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const recordingTimerRef = useRef(null);

  const [batchId, setBatchId] = useState('');
  const [batchIdError, setBatchIdError] = useState(null);

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [problem, setProblem] = useState(null);
  const [dragging, setDragging] = useState(false);

  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [audioName, setAudioName] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [audioProblem, setAudioProblem] = useState(null);
  const [showVoiceSection, setShowVoiceSection] = useState(false);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current);
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
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

  function releaseAudio() {
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setAudioBlob(null);
    setAudioUrl(null);
    setAudioName(null);
    setAudioProblem(null);
  }

  function choosePhoto(nextFile) {
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

  function handlePhotoInput(event) {
    choosePhoto(event.target.files?.[0] ?? null);
    event.target.value = '';
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    choosePhoto(event.dataTransfer.files?.[0] ?? null);
  }

  function handleDragOver(event) {
    event.preventDefault();
    setDragging(true);
  }

  function handleDragLeave() {
    setDragging(false);
  }

  function handleBatchIdChange(event) {
    const value = event.target.value;
    setBatchId(value);
    onBatchIdChange?.(value);
    if (value && !BATCH_ID_REGEX.test(value)) {
      setBatchIdError('Use up to 40 characters: letters, numbers, underscores, and hyphens.');
    } else {
      setBatchIdError(null);
    }
  }

  async function startRecording() {
    releaseAudio();
    setAudioProblem(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setAudioProblem('Audio recording is not supported in this browser.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const mimeType = recorder.mimeType || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        stream.getTracks().forEach((track) => track.stop());

        if (blob.size === 0) {
          setAudioProblem('Recording captured no audio.');
          return;
        }
        if (blob.size > MAX_AUDIO_BYTES) {
          setAudioProblem(`Recording is larger than ${MAX_AUDIO_MEGABYTES} MB.`);
          return;
        }

        const url = URL.createObjectURL(blob);
        audioUrlRef.current = url;
        setAudioBlob(blob);
        setAudioUrl(url);
        setAudioName('voice-note.webm');
      };

      recorder.start();
      setIsRecording(true);
      setRecordSeconds(0);

      recordingTimerRef.current = setInterval(() => {
        setRecordSeconds((sec) => {
          if (sec + 1 >= MAX_AUDIO_SECONDS) {
            stopRecording();
            return MAX_AUDIO_SECONDS;
          }
          return sec + 1;
        });
      }, 1000);
    } catch {
      setAudioProblem('Microphone permission was denied or microphone is unavailable.');
    }
  }

  function stopRecording() {
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }

  function handleAudioUpload(event) {
    const audioFile = event.target.files?.[0] ?? null;
    event.target.value = '';
    if (!audioFile) {
      return;
    }
    releaseAudio();

    if (audioFile.size === 0) {
      setAudioProblem('That audio file is empty.');
      return;
    }
    if (audioFile.size > MAX_AUDIO_BYTES) {
      setAudioProblem(`Audio file must be under ${MAX_AUDIO_MEGABYTES} MB.`);
      return;
    }
    const ext = audioFile.name.slice(audioFile.name.lastIndexOf('.')).toLowerCase();
    const isAllowedExt = ['.wav', '.mp3', '.ogg', '.webm', '.m4a', '.aac'].includes(ext);
    if (!ALLOWED_AUDIO_TYPES.includes(audioFile.type) && !isAllowedExt) {
      setAudioProblem('Use an audio file in WAV, MP3, OGG, WebM, or M4A format.');
      return;
    }

    const url = URL.createObjectURL(audioFile);
    audioUrlRef.current = url;
    setAudioBlob(audioFile);
    setAudioUrl(url);
    setAudioName(audioFile.name);
    setAudioProblem(null);
  }

  function handleSubmit() {
    if (!file || busy || batchIdError) {
      return;
    }

    const hasCustomCategory = selectedCategory && selectedCategory !== 'bottle';
    const hasBatchId = Boolean(batchId && batchId.trim());
    const hasVoiceNote = Boolean(audioBlob);

    if (hasCustomCategory || hasBatchId || hasVoiceNote) {
      onInspect(file, {
        category: selectedCategory,
        batchId: hasBatchId ? batchId.trim() : null,
        voiceNote: audioBlob,
      });
    } else {
      onInspect(file);
    }
  }

  const activeCategory = categories.find((cat) => cat.id === selectedCategory) ?? categories[0];
  const noCategories = categories.length === 0;

  return (
    <section className="card card--inspect" aria-labelledby="upload-title">
      <p className="step-label">Step 1</p>
      <h2 id="upload-title">New Inspection</h2>
      <p className="hint">
        Choose a target category, optional batch ID, and upload a JPEG or PNG photo up to{' '}
        {MAX_IMAGE_MEGABYTES} MB.
      </p>

      <div className="upload-grid">
        <div className="upload-main">
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
        </div>

        <div className="form-sidebar">
          <div className="form-field">
            <label htmlFor="category-select" className="field-label">
              Inspection Category
            </label>
            <select
              id="category-select"
              className="select-input"
              value={selectedCategory}
              onChange={(event) => onSelectCategory?.(event.target.value)}
              disabled={busy || noCategories}
            >
              {noCategories && <option value="">Loading categories…</option>}
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.displayName ?? cat.display_name ?? cat.id}
                </option>
              ))}
            </select>

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

            {activeCategory?.description && (
              <p className="field-hint">{activeCategory.description}</p>
            )}
            {activeCategory?.defectTypes && activeCategory.defectTypes.length > 0 && (
              <div className="defect-types-pills" aria-label="Known defect types for this category">
                <span className="defect-types-label">Defects:</span>
                {activeCategory.defectTypes.map((defect) => (
                  <span key={defect} className="defect-pill">
                    {defect}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="form-field">
            <label htmlFor="batch-id-input" className="field-label">
              Batch ID <span className="field-optional">(optional)</span>
            </label>
            <input
              id="batch-id-input"
              type="text"
              className={`text-input${batchIdError ? ' text-input-error' : ''}`}
              placeholder="e.g. batch-20261120-01"
              value={batchId}
              onChange={handleBatchIdChange}
              disabled={busy}
              maxLength={40}
            />
            {batchIdError ? (
              <p className="field-error" role="alert">
                {batchIdError}
              </p>
            ) : (
              <p className="field-hint">Leave blank to auto-generate a unique batch identifier.</p>
            )}
          </div>
        </div>
      </div>

      <div className="upload-footer">
        <div className="voice-note-section">
          <button
            type="button"
            className="voice-toggle-button"
            onClick={() => setShowVoiceSection((open) => !open)}
            aria-expanded={showVoiceSection}
          >
            <span>{showVoiceSection ? '▾' : '▸'} Optional Voice Note</span>
            {audioBlob && <span className="voice-attached-badge">Attached</span>}
          </button>

          {showVoiceSection && (
            <div className="voice-controls-panel">
              <p className="hint">
                Record or upload an operator note (up to {MAX_AUDIO_SECONDS}s or{' '}
                {MAX_AUDIO_MEGABYTES} MB).
              </p>

              <div className="voice-action-row">
                {!isRecording ? (
                  <button
                    type="button"
                    className="button secondary button-small"
                    onClick={startRecording}
                    disabled={busy}
                  >
                    Record voice note
                  </button>
                ) : (
                  <button
                    type="button"
                    className="button secondary button-small button-recording"
                    onClick={stopRecording}
                  >
                    Stop recording ({recordSeconds}s / {MAX_AUDIO_SECONDS}s)
                  </button>
                )}

                <input
                  ref={audioInput}
                  className="visually-hidden"
                  type="file"
                  accept={AUDIO_ACCEPT}
                  aria-label="Upload audio voice note"
                  tabIndex={-1}
                  onChange={handleAudioUpload}
                />

                <button
                  type="button"
                  className="button secondary button-small"
                  onClick={() => audioInput.current?.click()}
                  disabled={busy || isRecording}
                >
                  Upload audio
                </button>

                {audioBlob && (
                  <button
                    type="button"
                    className="button secondary button-small"
                    onClick={releaseAudio}
                    disabled={busy || isRecording}
                  >
                    Remove note
                  </button>
                )}
              </div>

              {audioUrl && (
                <div className="audio-preview-block">
                  <audio controls src={audioUrl} className="audio-player">
                    <track kind="captions" />
                  </audio>
                  {audioName && <span className="audio-name-label">{audioName}</span>}
                </div>
              )}

              {audioProblem && (
                <p className="field-error" role="alert">
                  {audioProblem}
                </p>
              )}
            </div>
          )}
        </div>

        <div className="upload-actions">
          <input
            ref={photoInput}
            className="visually-hidden"
            type="file"
            accept={PHOTO_ACCEPT}
            aria-label="Choose a photo"
            aria-hidden="true"
            tabIndex={-1}
            onChange={handlePhotoInput}
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
            onChange={handlePhotoInput}
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
          {audioBlob && (
            <span className="voice-attached-chip" aria-live="polite">
              <span aria-hidden="true">🎤</span>
              Voice note attached
            </span>
          )}
          <button
            type="button"
            className="button primary"
            onClick={handleSubmit}
            disabled={!file || busy || Boolean(batchIdError) || noCategories}
          >
            {busy ? 'Inspecting…' : 'Inspect photo'}
          </button>
        </div>
      </div>
    </section>
  );
}
