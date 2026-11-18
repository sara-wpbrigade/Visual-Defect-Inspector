/**
 * The only module that talks to the backend HTTP API.
 *
 * Transport concerns stay here: base URL, multipart upload, status-to-message
 * mapping and turning the snake_case API body into a small view model.
 */

import {
  GENERIC_ERROR_MESSAGE,
  NETWORK_ERROR_MESSAGE,
  NETWORK_ERROR_STATUS,
  STATUS_MESSAGES,
  UNEXPECTED_RESPONSE_MESSAGE,
} from '../constants';

const INSPECTIONS_PATH = '/inspections';
const DEFAULT_BASE_URL = '';
const BBOX_LENGTH = 4;
const REPORT_SOURCES = ['ai', 'template'];
const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL).replace(/\/$/, '');

export class ApiError extends Error {
  /**
   * @param {string} message A message that is safe to show to the operator.
   * @param {{ status?: number, detail?: unknown }} [options]
   */
  constructor(message, { status = NETWORK_ERROR_STATUS, detail = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Send one photo to POST /inspections and return the inspection facts.
 *
 * @param {File} file
 * @returns {Promise<{ inspectionId: string, score: number, assessment: object, report: object }>}
 * @throws {ApiError} When the request fails or the response is malformed.
 */
export async function createInspection(file) {
  const response = await postPhoto(file);
  if (!response.ok) {
    throw await toApiError(response);
  }
  return normalizeInspection(await response.json(), response.status);
}

/** Send the photo and turn a transport failure into an ApiError. */
async function postPhoto(file) {
  const form = new FormData();
  form.append('image', file);
  try {
    // No Content-Type header: the browser adds the multipart boundary itself.
    return await fetch(`${API_ORIGIN}${INSPECTIONS_PATH}`, { method: 'POST', body: form });
  } catch (cause) {
    throw new ApiError(NETWORK_ERROR_MESSAGE, { status: NETWORK_ERROR_STATUS, detail: cause });
  }
}

/** Build the user-facing error for a non-2xx response. */
async function toApiError(response) {
  const detail = await readDetail(response);
  const message =
    STATUS_MESSAGES[response.status] ?? detailMessage(detail) ?? GENERIC_ERROR_MESSAGE;
  return new ApiError(message, { status: response.status, detail });
}

/** Read a FastAPI error body without letting a broken body mask the status code. */
async function readDetail(response) {
  try {
    const body = await response.json();
    return body?.detail ?? null;
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

/** Convert the API body into the camelCase model the components use. */
function normalizeInspection(body, status) {
  const assessment = body?.assessment;
  const valid =
    typeof body?.inspection_id === 'string' &&
    typeof body.score === 'number' &&
    typeof assessment?.verdict === 'string' &&
    typeof assessment.confidence === 'number' &&
    typeof assessment.needs_review === 'boolean' &&
    typeof assessment.severity === 'string' &&
    typeof assessment.area_ratio === 'number' &&
    typeof assessment.action === 'string' &&
    isLocation(assessment.location) &&
    isReport(body.report);
  if (!valid) {
    throw new ApiError(UNEXPECTED_RESPONSE_MESSAGE, { status, detail: body });
  }
  return {
    inspectionId: body.inspection_id,
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
