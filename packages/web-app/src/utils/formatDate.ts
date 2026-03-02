/**
 * Date formatting utilities used across digest components.
 */

/**
 * Formats an ISO 8601 date string into a human-readable relative or absolute date.
 * Examples: "Feb 28, 2026" or "3 days ago"
 *
 * @param isoString - ISO 8601 date string
 * @param relative - If true and within the last 7 days, return a relative string
 * @returns Formatted date string
 */
export function formatDate(isoString: string, relative = true): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {
      return isoString;
    }

    if (relative) {
      const diffMs = Date.now() - date.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

      if (diffDays === 0) return 'Today';
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays} days ago`;
    }

    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return isoString;
  }
}

/**
 * Formats a latency value in milliseconds to a human-readable string.
 *
 * @param ms - Latency in milliseconds
 * @returns Formatted latency string (e.g. "1.2s" or "987ms")
 */
export function formatLatency(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${ms}ms`;
}
