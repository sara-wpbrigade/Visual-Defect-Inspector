/** User-facing vocabulary and upload limits shared across the UI. */

export const MAX_IMAGE_MEGABYTES = 10;
export const MAX_IMAGE_BYTES = MAX_IMAGE_MEGABYTES * 1024 * 1024;

export const ALLOWED_IMAGE_TYPES = Object.freeze(['image/jpeg', 'image/png']);
export const ALLOWED_IMAGE_EXTENSIONS = Object.freeze(['.jpg', '.jpeg', '.png']);
export const PHOTO_ACCEPT = ALLOWED_IMAGE_TYPES.join(',');
export const CAMERA_ACCEPT = 'image/*';

export const STATUS = Object.freeze({
  IDLE: 'idle',
  LOADING: 'loading',
  SUCCESS: 'success',
  ERROR: 'error',
});

export const VERDICT = Object.freeze({
  PASS: 'pass',
  DEFECT: 'defect',
});

export const VERDICT_LABELS = Object.freeze({
  [VERDICT.PASS]: 'Pass',
  [VERDICT.DEFECT]: 'Defect',
});

export const SEVERITY_LABELS = Object.freeze({
  none: 'None',
  low: 'Low',
  medium: 'Medium',
  high: 'High',
});

export const ACTION_LABELS = Object.freeze({
  accept: 'Accept',
  rework: 'Rework',
  reject: 'Reject',
  re_inspect: 'Re-inspect',
});

export const ACTION_HINTS = Object.freeze({
  accept: 'Release the item. No further action is needed.',
  rework: 'Send the item for rework before it leaves the line.',
  reject: 'Reject the item and keep it out of the batch.',
  re_inspect: 'Inspect the item again or ask a second operator to review it.',
});

export const REPORT_SECTION_TITLE = 'Report';
export const REPORT_SOURCE_LABELS = Object.freeze({
  ai: 'AI-written',
  template: 'Template (offline)',
});
export const REPORT_FINDINGS_TITLE = 'Findings';
export const REPORT_RECOMMENDATIONS_TITLE = 'Recommendations';
export const DEFECT_TYPE_LABEL = 'Defect type';
export const DEFECT_TYPE_ESTIMATE_LABEL = 'estimated by AI';
export const DEFECT_TYPE_NOT_DETERMINED = 'not determined';
export const FLAGGED_AREA_LABEL = 'Flagged area';
export const MANUAL_REVIEW_TITLE = 'Manual review required';
export const VOICE_CONFLICT_LABEL = 'Voice note conflict';

export const HTTP_BAD_REQUEST = 400;
export const HTTP_PAYLOAD_TOO_LARGE = 413;
export const HTTP_UNPROCESSABLE = 422;
export const HTTP_UNAVAILABLE = 503;
export const NETWORK_ERROR_STATUS = 0;

export const STATUS_MESSAGES = Object.freeze({
  [HTTP_BAD_REQUEST]: 'The server could not read this image. Use a JPEG or PNG photo.',
  [HTTP_PAYLOAD_TOO_LARGE]: `That photo is too large. Use one under ${MAX_IMAGE_MEGABYTES} MB.`,
  [HTTP_UNPROCESSABLE]: 'The photo was not sent correctly. Choose the file again.',
  [HTTP_UNAVAILABLE]: 'The inspection model is unavailable right now. Try again in a moment.',
});

export const NETWORK_ERROR_MESSAGE =
  'Could not reach the server. Check that the backend is running and try again.';
export const UNEXPECTED_RESPONSE_MESSAGE =
  'The server returned an unexpected response. Try again in a moment.';
export const GENERIC_ERROR_MESSAGE = 'The inspection failed. Try again in a moment.';
