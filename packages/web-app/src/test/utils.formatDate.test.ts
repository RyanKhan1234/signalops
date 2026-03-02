/**
 * Tests for formatDate and formatLatency utilities.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { formatDate, formatLatency } from '../utils/formatDate';

describe('formatDate', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns the original string for invalid dates', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });

  it('returns "Today" for dates within the past 24 hours when relative=true', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-01T12:00:00Z'));
    expect(formatDate('2026-03-01T08:00:00Z', true)).toBe('Today');
  });

  it('returns "Yesterday" for dates from the previous day', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-02T12:00:00Z'));
    expect(formatDate('2026-03-01T12:00:00Z', true)).toBe('Yesterday');
  });

  it('returns "N days ago" for dates within the last 7 days', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-06T12:00:00Z'));
    expect(formatDate('2026-03-01T12:00:00Z', true)).toBe('5 days ago');
  });

  it('returns an absolute date string for dates older than 7 days', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-15T12:00:00Z'));
    const result = formatDate('2026-03-01T12:00:00Z', true);
    expect(result).toContain('Mar');
    expect(result).toContain('2026');
  });

  it('returns an absolute date string when relative=false', () => {
    const result = formatDate('2026-03-01T12:00:00Z', false);
    expect(result).toContain('2026');
  });
});

describe('formatLatency', () => {
  it('formats sub-second latency as milliseconds', () => {
    expect(formatLatency(987)).toBe('987ms');
  });

  it('formats exactly 1000ms as 1.0s', () => {
    expect(formatLatency(1000)).toBe('1.0s');
  });

  it('formats 1500ms as 1.5s', () => {
    expect(formatLatency(1500)).toBe('1.5s');
  });

  it('formats 2345ms as 2.3s', () => {
    expect(formatLatency(2345)).toBe('2.3s');
  });

  it('formats 0ms as 0ms', () => {
    expect(formatLatency(0)).toBe('0ms');
  });
});
