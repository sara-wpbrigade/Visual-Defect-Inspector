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
