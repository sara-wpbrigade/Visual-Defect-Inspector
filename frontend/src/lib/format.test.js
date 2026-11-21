import { afterEach, describe, expect, it, vi } from 'vitest';

import { formatFileSize, formatPercent, formatScore, relativeTime } from './format';

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

describe('relativeTime', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  function at(now, then) {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(now));
    return relativeTime(then);
  }

  it('returns an empty string for missing or unparseable values', () => {
    expect(relativeTime(null)).toBe('');
    expect(relativeTime(undefined)).toBe('');
    expect(relativeTime('not-a-date')).toBe('');
  });

  it('formats recent and older timestamps', () => {
    expect(at('2026-11-20T12:00:00Z', '2026-11-20T11:59:30Z')).toBe('just now');
    expect(at('2026-11-20T12:00:00Z', '2026-11-20T11:55:00Z')).toBe('5 min ago');
    expect(at('2026-11-20T12:00:00Z', '2026-11-20T10:00:00Z')).toBe('2 h ago');
    expect(at('2026-11-20T12:00:00Z', '2026-11-19T10:00:00Z')).toBe('yesterday');
    expect(at('2026-11-20T12:00:00Z', '2026-11-17T12:00:00Z')).toBe('3 days ago');
  });

  it('uses a calendar date for older timestamps', () => {
    const text = at('2026-11-20T12:00:00Z', '2026-11-01T12:00:00Z');

    expect(text).not.toBe('');
    expect(text).not.toContain('days ago');
  });
});
