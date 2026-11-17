import { describe, expect, it } from 'vitest';

import { formatFileSize, formatPercent, formatScore } from './format';

describe('formatPercent', () => {
  it('formats a ratio with one decimal', () => {
    expect(formatPercent(0.8234)).toBe('82.3%');
    expect(formatPercent(0)).toBe('0.0%');
    expect(formatPercent(1)).toBe('100.0%');
  });
});

describe('formatScore', () => {
  it('formats the anomaly score with three decimals', () => {
    expect(formatScore(0.2179394)).toBe('0.218');
    expect(formatScore(1)).toBe('1.000');
  });
});

describe('formatFileSize', () => {
  it('uses kilobytes below one megabyte', () => {
    expect(formatFileSize(2048)).toBe('2 KB');
  });

  it('uses one decimal of megabytes at or above one megabyte', () => {
    expect(formatFileSize(10 * 1024 * 1024)).toBe('10.0 MB');
  });
});
