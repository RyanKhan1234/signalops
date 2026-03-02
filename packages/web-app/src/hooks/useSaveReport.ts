/**
 * useSaveReport — custom hook for saving a digest to the Traceability Store.
 *
 * Handles:
 * - Save lifecycle state ('idle' | 'saving' | 'saved' | 'error')
 * - 409 responses are treated as already-saved (success)
 * - Auto-reset to 'idle' after 3 seconds on 'saved' or 'error'
 */

import { useState, useCallback, useRef } from 'react';
import type { DigestResponse } from '../types/digest';
import { saveReport, DigestApiError } from '../services/api';

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

interface UseSaveReportReturn {
  status: SaveStatus;
  save: (digest: DigestResponse, query: string) => Promise<void>;
}

/**
 * Provides a `save` function and a `status` state for saving digests to history.
 */
export function useSaveReport(): UseSaveReportReturn {
  const [status, setStatus] = useState<SaveStatus>('idle');
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleReset = useCallback(() => {
    if (resetTimerRef.current !== null) {
      clearTimeout(resetTimerRef.current);
    }
    resetTimerRef.current = setTimeout(() => {
      setStatus('idle');
      resetTimerRef.current = null;
    }, 3000);
  }, []);

  const save = useCallback(
    async (digest: DigestResponse, query: string): Promise<void> => {
      if (status === 'saving') return;

      // Cancel any pending reset timer before starting a new save
      if (resetTimerRef.current !== null) {
        clearTimeout(resetTimerRef.current);
        resetTimerRef.current = null;
      }

      setStatus('saving');

      try {
        await saveReport(digest, query);
        // 409 alreadySaved=true is still treated as success by saveReport
        setStatus('saved');
        scheduleReset();
      } catch (err) {
        // Network or unexpected server errors
        console.error('[useSaveReport] Failed to save report:', err instanceof DigestApiError ? err.message : err);
        setStatus('error');
        scheduleReset();
      }
    },
    [status, scheduleReset]
  );

  return { status, save };
}
