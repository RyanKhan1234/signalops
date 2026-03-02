/**
 * useReportHistory — custom hook for managing the history list view state.
 *
 * Handles:
 * - Fetching paginated report summaries from the Traceability Store
 * - Pagination state (page / pageSize)
 * - Digest-type filter state
 * - Loading and error states
 * - Loading a full digest detail by report_id
 */

import { useState, useEffect, useCallback } from 'react';
import type { ReportSummary, DigestResponse } from '../types/digest';
import { listReports, getReportById, DigestApiError } from '../services/api';

const DEFAULT_PAGE_SIZE = 20;

export interface UseReportHistoryReturn {
  reports: ReportSummary[];
  total: number;
  isLoading: boolean;
  error: string | null;
  page: number;
  pageSize: number;
  filter: string; // digest_type filter value, or '' for all
  setPage: (page: number) => void;
  setFilter: (filter: string) => void;
  refresh: () => void;
  loadReport: (reportId: string) => Promise<DigestResponse | null>;
}

/**
 * Manages state for the history list view, including pagination,
 * filtering, and fetching individual report details.
 */
export function useReportHistory(): UseReportHistoryReturn {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0); // 0-based page index
  const [filter, setFilter] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const pageSize = DEFAULT_PAGE_SIZE;

  const refresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const handleSetPage = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  const handleSetFilter = useCallback((newFilter: string) => {
    setFilter(newFilter);
    setPage(0); // Reset to first page on filter change
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function fetchReports() {
      setIsLoading(true);
      setError(null);

      try {
        const result = await listReports({
          limit: pageSize,
          offset: page * pageSize,
          digest_type: filter || undefined,
        });

        if (!cancelled) {
          setReports(result.items);
          setTotal(result.total);
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof DigestApiError
              ? err.message
              : 'Failed to load report history. Please try again.';
          setError(message);
          setReports([]);
          setTotal(0);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchReports();

    return () => {
      cancelled = true;
    };
  }, [page, pageSize, filter, refreshKey]);

  const loadReport = useCallback(async (reportId: string): Promise<DigestResponse | null> => {
    try {
      return await getReportById(reportId);
    } catch (err) {
      console.error('Failed to load report:', err);
      return null;
    }
  }, []);

  return {
    reports,
    total,
    isLoading,
    error,
    page,
    pageSize,
    filter,
    setPage: handleSetPage,
    setFilter: handleSetFilter,
    refresh,
    loadReport,
  };
}
