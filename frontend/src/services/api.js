/**
 * The only module that talks to the backend HTTP API.
 *
 * Transport concerns stay here: base URL, multipart upload, status-to-message
 * mapping and turning the snake_case API body into a small view model.
 */

import {
  CATEGORY_ERROR_CODES,
  GENERIC_ERROR_MESSAGE,
  NETWORK_ERROR_MESSAGE,
  NETWORK_ERROR_STATUS,
  STATUS_MESSAGES,
  UNEXPECTED_RESPONSE_MESSAGE,
} from '../constants';

const INSPECTIONS_PATH = '/inspections';
const BATCHES_PATH = '/batches';
const CATEGORIES_PATH = '/categories';
const DEFAULT_BASE_URL = '';
const BBOX_LENGTH = 4;
const REPORT_SOURCES = ['ai', 'template'];
const VOICE_NOTE_STATUSES = ['transcribed', 'no_speech'];
const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL).replace(/\/$/, '');

export class ApiError extends Error {
  /**
   * @param {string} message A message that is safe to show to the operator.
   * @param {{ status?: number, detail?: unknown, code?: string, supportedCategories?: Array<{ id: string, display_name: string }> }} [options]
   */
  constructor(
    message,
    { status = NETWORK_ERROR_STATUS, detail = null, code = null, supportedCategories = null } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.code = code;
    this.supportedCategories = supportedCategories;
  }
}

/**
 * Send one photo to POST /inspections and return the inspection facts.
 *
 * @param {File} file
 * @param {{ category?: string, batchId?: string | null, voiceNote?: Blob | File | null }} [options]
 * @returns {Promise<{ inspectionId: string, score: number, assessment: object, report: object }>}
 * @throws {ApiError} When the request fails or the response is malformed.
 */
export async function createInspection(file, options) {
  const response = await postPhoto(file, options);
  if (!response.ok) {
    throw await toApiError(response);
  }
  return normalizeInspection(await response.json(), response.status);
}

/** Send the photo and optional parameters, turning transport failure into an ApiError. */
async function postPhoto(file, options) {
  const form = new FormData();
  form.append('image', file);

  // Default category to 'bottle' if not specified
  const category = options?.category || 'bottle';
  form.append('category', category);

  if (options?.batchId && typeof options.batchId === 'string' && options.batchId.trim()) {
    form.append('batch_id', options.batchId.trim());
  }

  if (options?.voiceNote) {
    form.append('voice_note', options.voiceNote);
  }

  try {
    // No Content-Type header: the browser adds the multipart boundary itself.
    return await fetch(`${API_ORIGIN}${INSPECTIONS_PATH}`, { method: 'POST', body: form });
  } catch (cause) {
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: NETWORK_ERROR_STATUS, detail: cause });
  }
}

/**
 * Fetch available categories from GET /categories.
 *
 * @returns {Promise<Array<{ id: string, displayName: string, description: string, defectTypes: string[] }>>}
 */
export async function getCategories() {
  try {
    const response = await fetch(`${API_ORIGIN}${CATEGORIES_PATH}`);
    if (!response.ok) {
      throw await toApiError(response);
    }
    const data = await response.json();
    if (!Array.isArray(data)) {
      throw new ApiError(UNEXPECTED_RESPONSE_MESSAGE, { status: response.status, detail: data });
    }
    return data.map((item) => ({
      id: item.id,
      displayName: item.display_name ?? item.displayName ?? item.id,
      description: item.description ?? '',
      defectTypes: Array.isArray(item.defect_types) ? [...item.defect_types] : [],
    }));
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw cause;
    }
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: NETWORK_ERROR_STATUS, detail: cause });
  }
}

/**
 * Fetch batch summaries from GET /batches.
 *
 * @param {{ limit?: number, offset?: number }} [params]
 * @returns {Promise<Array<{ batchId: string, itemCount: number, decision: string, defectCount: number, passCount: number, reviewCount: number, categories: string[], lastInspectionAt: string | null }>>}
 */
export async function getBatches({ limit = 50, offset = 0 } = {}) {
  try {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    const response = await fetch(`${API_ORIGIN}${BATCHES_PATH}?${params.toString()}`);
    if (!response.ok) {
      throw await toApiError(response);
    }
    const data = await response.json();
    if (!Array.isArray(data)) {
      throw new ApiError(UNEXPECTED_RESPONSE_MESSAGE, { status: response.status, detail: data });
    }
    return data.map((item) => ({
      batchId: item.batch_id,
      itemCount: item.item_count,
      decision: item.decision,
      defectCount: item.defect_count,
      passCount: item.pass_count,
      reviewCount: item.review_count,
      categories: Array.isArray(item.categories) ? [...item.categories] : [],
      lastInspectionAt: item.last_inspection_at,
    }));
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw cause;
    }
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: NETWORK_ERROR_STATUS, detail: cause });
  }
}

/**
 * Fetch one batch summary and its items from GET /batches/{batch_id}.
 *
 * @param {string} batchId
 * @returns {Promise<{ summary: object, items: object[] }>}
 */
export async function getBatch(batchId) {
  try {
    const response = await fetch(`${API_ORIGIN}${BATCHES_PATH}/${encodeURIComponent(batchId)}`);
    if (!response.ok) {
      throw await toApiError(response);
    }
    const data = await response.json();
    return {
      summary: {
        batchId: data.summary?.batch_id,
        itemCount: data.summary?.item_count,
        decision: data.summary?.decision,
        defectCount: data.summary?.defect_count,
        passCount: data.summary?.pass_count,
        reviewCount: data.summary?.review_count,
        categories: Array.isArray(data.summary?.categories) ? [...data.summary.categories] : [],
        lastInspectionAt: data.summary?.last_inspection_at,
      },
      items: Array.isArray(data.items)
        ? data.items.map((item) => normalizeInspectionSummary(item))
        : [],
    };
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw cause;
    }
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: NETWORK_ERROR_STATUS, detail: cause });
  }
}

/**
 * Fetch stored inspection history from GET /inspections.
 *
 * @param {{ limit?: number, offset?: number, batchId?: string | null, category?: string | null }} [params]
 * @returns {Promise<{ items: Array<object>, total: number }>}
 */
export async function getInspections({
  limit = 20,
  offset = 0,
  batchId = null,
  category = null,
} = {}) {
  try {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (batchId) {
      params.append('batch_id', batchId);
    }
    if (category) {
      params.append('category', category);
    }
    const response = await fetch(`${API_ORIGIN}${INSPECTIONS_PATH}?${params.toString()}`);
    if (!response.ok) {
      throw await toApiError(response);
    }
    const data = await response.json();
    const items = Array.isArray(data?.items)
      ? data.items.map((item) => normalizeInspectionSummary(item))
      : [];
    return {
      items,
      total: typeof data?.total === 'number' ? data.total : items.length,
    };
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw cause;
    }
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: NETWORK_ERROR_STATUS, detail: cause });
  }
}

/**
 * Fetch one inspection detail by ID from GET /inspections/{id}.
 *
 * @param {string} inspectionId
 * @returns {Promise<object>}
 */
export async function getInspection(inspectionId) {
  try {
    const response = await fetch(
      `${API_ORIGIN}${INSPECTIONS_PATH}/${encodeURIComponent(inspectionId)}`,
    );
    if (!response.ok) {
      throw await toApiError(response);
    }
    const body = await response.json();
    return normalizeInspection(body, response.status);
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw cause;
    }
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: NETWORK_ERROR_STATUS, detail: cause });
  }
}

/**
 * Trigger download of the PDF report for an inspection from GET /inspections/{id}/report.pdf.
 *
 * @param {string} inspectionId
 * @returns {Promise<void>}
 */
export async function downloadPdfReport(inspectionId) {
  try {
    const response = await fetch(
      `${API_ORIGIN}${INSPECTIONS_PATH}/${encodeURIComponent(inspectionId)}/report.pdf`,
    );
    if (!response.ok) {
      throw await toApiError(response);
    }
    const blob = await response.blob();
    triggerFileDownload(blob, `inspection-${inspectionId}.pdf`);
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw cause;
    }
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: NETWORK_ERROR_STATUS, detail: cause });
  }
}

/**
 * Export defect log or full batch history as CSV from GET /inspections/export.csv.
 *
 * @param {{ batchId?: string | null, category?: string | null, onlyDefects?: boolean }} [options]
 * @returns {Promise<void>}
 */
export async function exportDefectLogCsv({
  batchId = null,
  category = null,
  onlyDefects = true,
} = {}) {
  try {
    const params = new URLSearchParams();
    if (batchId) {
      params.append('batch_id', batchId);
    }
    if (category) {
      params.append('category', category);
    }
    params.append('only_defects', String(onlyDefects));

    const response = await fetch(
      `${API_ORIGIN}${INSPECTIONS_PATH}/export.csv?${params.toString()}`,
    );
    if (!response.ok) {
      throw await toApiError(response);
    }
    const blob = await response.blob();
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const filename = batchId ? `defect-log-${batchId}-${today}.csv` : `defect-log-${today}.csv`;
    triggerFileDownload(blob, filename);
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw cause;
    }
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: NETWORK_ERROR_STATUS, detail: cause });
  }
}

/** Helper to trigger a browser file download using a blob. */
function triggerFileDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

/** Build the user-facing error for a non-2xx response. */
async function toApiError(response) {
  const body = await readBody(response);
  const detail = body?.detail ?? null;
  const code = body?.code ?? null;
  const supportedCategories = body?.supported_categories ?? null;

  // Check for category errors or an unusable voice note; keep their own detail.
  const isVoiceNoteError =
    response.status === 400 && typeof detail === 'string' && /audio|voice note/i.test(detail);
  if (
    code === CATEGORY_ERROR_CODES.CATEGORY_MISMATCH ||
    code === CATEGORY_ERROR_CODES.UNKNOWN_CATEGORY ||
    isVoiceNoteError ||
    (response.status === 422 && typeof detail === 'string')
  ) {
    return new ApiError(detail, {
      status: response.status,
      detail,
      code,
      supportedCategories,
    });
  }

  const message =
    STATUS_MESSAGES[response.status] ?? detailMessage(detail) ?? GENERIC_ERROR_MESSAGE;
  return new ApiError(message, { status: response.status, detail, code, supportedCategories });
}

/** Read a FastAPI error body without letting a broken body mask the status code. */
async function readBody(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/** Flatten FastAPI's validation detail into one sentence. */
function detailMessage(detail) {
  if (typeof detail === 'string' && detail.length > 0) {
    return detail;
  }
  if (!Array.isArray(detail)) {
    return null;
  }
  const messages = detail.map((item) => item?.msg).filter((message) => typeof message === 'string');
  return messages.length > 0 ? messages.join(' ') : null;
}

/** True for a plain JSON object. */
function isObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** True for the API's optional text fields: a string or null. */
function isNullableString(value) {
  return value === null || typeof value === 'string';
}

/** True for a non-empty list of strings, the report's findings and recommendations. */
function isNonEmptyStringList(value) {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((item) => typeof item === 'string' && item.length > 0)
  );
}

/** True for a normalized [x_min, y_min, x_max, y_max] box inside the photo. */
function isBbox(value) {
  return (
    Array.isArray(value) &&
    value.length === BBOX_LENGTH &&
    value.every(
      (coordinate) => typeof coordinate === 'number' && coordinate >= 0 && coordinate <= 1,
    )
  );
}

/** True for the defect location: a region name and a normalized box, or null. */
function isLocation(value) {
  if (value === null) {
    return true;
  }
  return (
    isObject(value) &&
    typeof value.region === 'string' &&
    value.region.length > 0 &&
    isBbox(value.bbox)
  );
}

/** True for the report block: identity, source and the validated content. */
function isReport(value) {
  if (!isObject(value)) {
    return false;
  }
  const content = value.content;
  return (
    typeof value.report_id === 'string' &&
    typeof value.generated_at === 'string' &&
    typeof value.persona === 'string' &&
    REPORT_SOURCES.includes(value.source) &&
    isNullableString(value.manual_review_notice) &&
    isObject(content) &&
    typeof content.summary === 'string' &&
    content.summary.length > 0 &&
    isNonEmptyStringList(content.findings) &&
    isNonEmptyStringList(content.recommendations) &&
    isNullableString(content.defect_type) &&
    isNullableString(content.voice_note_conflict)
  );
}

/** True for the optional voice-note result: status, text, language and duration. */
function isVoiceNote(value) {
  if (value === null || value === undefined) {
    return true;
  }
  return (
    isObject(value) &&
    VOICE_NOTE_STATUSES.includes(value.status) &&
    typeof value.text === 'string' &&
    isNullableString(value.language) &&
    typeof value.duration_seconds === 'number' &&
    value.duration_seconds >= 0 &&
    typeof value.truncated === 'boolean'
  );
}

/** Convert the API body into the camelCase model the components use. */
function normalizeInspection(body, status) {
  const assessment = body?.assessment;
  const valid =
    (typeof body?.inspection_id === 'string' || typeof body?.id === 'string') &&
    typeof body.score === 'number' &&
    typeof assessment?.verdict === 'string' &&
    typeof assessment.confidence === 'number' &&
    typeof assessment.needs_review === 'boolean' &&
    typeof assessment.severity === 'string' &&
    typeof assessment.area_ratio === 'number' &&
    typeof assessment.action === 'string' &&
    isLocation(assessment.location) &&
    isReport(body.report) &&
    isVoiceNote(body.voice_note);
  if (!valid) {
    throw new ApiError(UNEXPECTED_RESPONSE_MESSAGE, { status, detail: body });
  }

  const model = {
    inspectionId: body.inspection_id || body.id,
    score: body.score,
    assessment: {
      verdict: assessment.verdict,
      confidence: assessment.confidence,
      needsReview: assessment.needs_review,
      severity: assessment.severity,
      areaRatio: assessment.area_ratio,
      action: assessment.action,
      location: normalizeLocation(assessment.location),
    },
    report: normalizeReport(body.report),
  };

  // Attach optional additional backend fields when present
  if (body.category !== undefined) {
    model.category = body.category;
  }
  if (body.created_at !== undefined) {
    model.createdAt = body.created_at;
  }
  if (body.batch_id !== undefined) {
    model.batchId = body.batch_id;
  }
  if (body.batch_decision !== undefined) {
    model.batchDecision = body.batch_decision;
  }
  if (body.report_pdf_available !== undefined) {
    model.reportPdfAvailable = Boolean(body.report_pdf_available);
  }
  if (body.report_pdf_url !== undefined) {
    model.reportPdfUrl = body.report_pdf_url;
  }
  if (body.images !== undefined) {
    model.images = {
      photo: body.images.photo,
      overlay: body.images.overlay,
      thumbnail: body.images.thumbnail,
    };
  }
  if (body.voice_note !== undefined && body.voice_note !== null) {
    model.voiceNote = {
      status: body.voice_note.status,
      text: body.voice_note.text,
      language: body.voice_note.language,
      durationSeconds: body.voice_note.duration_seconds,
      truncated: body.voice_note.truncated,
    };
  }

  return model;
}

/** Convert a history summary item from GET /inspections or batch item to camelCase. */
function normalizeInspectionSummary(item) {
  const id = item.id ?? item.inspection_id;
  return {
    id,
    createdAt: item.created_at,
    category: item.category,
    batchId: item.batch_id ?? null,
    verdict: item.verdict ?? item.assessment?.verdict,
    severity: item.severity ?? item.assessment?.severity,
    action: item.action ?? item.assessment?.action,
    confidence: item.confidence ?? item.assessment?.confidence,
    needsReview: item.needs_review ?? item.assessment?.needs_review ?? false,
    thumbnailUrl: item.thumbnail_url ?? (id ? `/inspections/${id}/thumbnail` : null),
    batchDecision: item.batch_decision ?? null,
    reportPdfAvailable: Boolean(item.report_pdf_available),
    reportPdfUrl: item.report_pdf_url ?? null,
  };
}

/** Convert the defect location to camelCase, keeping the box as a plain array. */
function normalizeLocation(location) {
  if (location === null) {
    return null;
  }
  return { region: location.region, bbox: [...location.bbox] };
}

/** Convert the report block to camelCase for the result card. */
function normalizeReport(report) {
  return {
    reportId: report.report_id,
    generatedAt: report.generated_at,
    persona: report.persona,
    source: report.source,
    manualReviewNotice: report.manual_review_notice,
    content: {
      summary: report.content.summary,
      findings: [...report.content.findings],
      recommendations: [...report.content.recommendations],
      defectType: report.content.defect_type,
      voiceNoteConflict: report.content.voice_note_conflict,
    },
  };
}
