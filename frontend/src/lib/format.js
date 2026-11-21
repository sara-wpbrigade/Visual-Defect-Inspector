/** Display formatting helpers. */

const PERCENT = 100;
const PERCENT_DIGITS = 1;
const SCORE_DIGITS = 3;
const BYTES_PER_KILOBYTE = 1024;
const BYTES_PER_MEGABYTE = 1024 * 1024;
const KILOBYTE_DIGITS = 0;
const MEGABYTE_DIGITS = 1;

/** Format a 0..1 ratio as a percentage, for example 0.8234 -> "82.3%". */
export function formatPercent(ratio) {
  return `${(ratio * PERCENT).toFixed(PERCENT_DIGITS)}%`;
}

/** Format the raw anomaly score with three decimals. */
export function formatScore(score) {
  return score.toFixed(SCORE_DIGITS);
}

/** Format a byte count for a file chip, for example 2048 -> "2 KB". */
export function formatFileSize(bytes) {
  if (bytes < BYTES_PER_MEGABYTE) {
    return `${(bytes / BYTES_PER_KILOBYTE).toFixed(KILOBYTE_DIGITS)} KB`;
  }
  return `${(bytes / BYTES_PER_MEGABYTE).toFixed(MEGABYTE_DIGITS)} MB`;
}
/**
 * Format a timestamp as a short relative string ("2 min ago", "3 h ago", "yesterday").
 * Returns an empty string when the input is missing or unparseable.
 *
 * @param {string | number | Date | null | undefined} value
 * @returns {string}
 */
export function relativeTime(value) {
  if (value === null || value === undefined) {
    return '';
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.round(diffMs / 1000);
  if (diffSec < 45) {
    return 'just now';
  }
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) {
    return `${diffMin} min ago`;
  }
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) {
    return `${diffHr} h ago`;
  }
  const diffDay = Math.round(diffHr / 24);
  if (diffDay === 1) {
    return 'yesterday';
  }
  if (diffDay < 7) {
    return `${diffDay} days ago`;
  }
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
