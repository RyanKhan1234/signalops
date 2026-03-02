/**
 * Generates a unique ID for chat messages.
 * Uses crypto.randomUUID() where available, falls back to a timestamp + random string.
 */
export function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
