/**
 * HistoryList — full-page history view for past digests.
 *
 * Layout:
 * - Left panel (~1/3 width): scrollable list of past report summaries with
 *   pagination and a digest-type filter dropdown.
 * - Right panel (~2/3 width): detail view showing the full DashboardContent
 *   for the selected report, or a placeholder when nothing is selected.
 */

import { useState } from 'react';
import type { DigestResponse, DigestType, ReportSummary } from '../../types/digest';
import { useReportHistory } from '../../hooks/useReportHistory';
import { DashboardContent } from '../dashboard/DashboardContent';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { formatDate } from '../../utils/formatDate';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DIGEST_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'daily_digest', label: 'Daily Digest' },
  { value: 'weekly_report', label: 'Weekly Report' },
  { value: 'risk_alert', label: 'Risk Alert' },
  { value: 'competitor_monitor', label: 'Competitor Monitor' },
];

const DIGEST_TYPE_LABELS: Record<DigestType, string> = {
  daily_digest: 'Daily',
  weekly_report: 'Weekly',
  risk_alert: 'Risk Alert',
  competitor_monitor: 'Competitor',
};

const DIGEST_TYPE_BADGE_CLASSES: Record<DigestType, string> = {
  daily_digest: 'bg-blue-100 text-blue-800 ring-1 ring-blue-200',
  weekly_report: 'bg-purple-100 text-purple-800 ring-1 ring-purple-200',
  risk_alert: 'bg-red-100 text-red-800 ring-1 ring-red-200',
  competitor_monitor: 'bg-green-100 text-green-800 ring-1 ring-green-200',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface DigestTypeBadgeProps {
  digestType: DigestType;
}

function DigestTypeBadge({ digestType }: DigestTypeBadgeProps) {
  const classes =
    DIGEST_TYPE_BADGE_CLASSES[digestType] ?? 'bg-gray-100 text-gray-800 ring-1 ring-gray-200';
  const label = DIGEST_TYPE_LABELS[digestType] ?? digestType;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium flex-shrink-0 ${classes}`}
    >
      {label}
    </span>
  );
}

interface ReportRowProps {
  report: ReportSummary;
  isSelected: boolean;
  isLoadingDetail: boolean;
  onClick: () => void;
}

function ReportRow({ report, isSelected, isLoadingDetail, onClick }: ReportRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left px-3 py-3 rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-1 ${
        isSelected
          ? 'bg-brand-50 border-brand-200'
          : 'bg-white border-gray-100 hover:bg-gray-50 hover:border-gray-200'
      }`}
      aria-pressed={isSelected}
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <DigestTypeBadge digestType={report.digest_type} />
            <span className="text-xs text-gray-400 flex-shrink-0">
              {formatDate(report.generated_at)}
            </span>
          </div>
          <p className="text-sm text-gray-700 truncate leading-snug" title={report.query}>
            {report.query}
          </p>
          <p className="text-xs text-gray-400 font-mono mt-0.5 truncate">
            {report.report_id}
          </p>
        </div>
        {isLoadingDetail && (
          <div className="flex-shrink-0 mt-1">
            <LoadingSpinner size="sm" />
          </div>
        )}
      </div>
    </button>
  );
}

interface DetailHeaderProps {
  digest: DigestResponse;
}

function DetailHeader({ digest }: DetailHeaderProps) {
  return (
    <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-3">
      <div className="flex items-center gap-3 flex-wrap">
        <DigestTypeBadge digestType={digest.digest_type} />
        <span className="text-xs text-gray-400 font-mono">{digest.report_id}</span>
        <span className="text-xs text-gray-400">{formatDate(digest.generated_at, false)}</span>
      </div>
      <p className="mt-1 text-sm text-gray-700 line-clamp-2">{digest.query}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * Full-page history view showing a list of past digests on the left
 * and the selected digest's full DashboardContent on the right.
 */
export function HistoryList() {
  const {
    reports,
    total,
    isLoading,
    error,
    page,
    pageSize,
    filter,
    setPage,
    setFilter,
    refresh,
    loadReport,
  } = useReportHistory();

  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [loadingRowId, setLoadingRowId] = useState<string | null>(null);
  const [selectedDigest, setSelectedDigest] = useState<DigestResponse | null>(null);

  const totalPages = Math.ceil(total / pageSize);
  const hasPrev = page > 0;
  const hasNext = page < totalPages - 1;

  async function handleRowClick(report: ReportSummary) {
    // Clicking the already-selected row deselects it
    if (selectedReportId === report.report_id) {
      setSelectedReportId(null);
      setSelectedDigest(null);
      return;
    }

    setSelectedReportId(report.report_id);
    setLoadingRowId(report.report_id);
    setSelectedDigest(null);

    const digest = await loadReport(report.report_id);
    setLoadingRowId(null);

    if (digest) {
      setSelectedDigest(digest);
    }
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Left panel — report list */}
      <aside className="w-80 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col h-full overflow-hidden">
        {/* Left panel header */}
        <div className="flex-shrink-0 px-4 py-3 border-b border-gray-100">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-gray-900">Past Digests</h2>
            <button
              type="button"
              onClick={refresh}
              className="text-xs text-gray-500 hover:text-gray-900 hover:bg-gray-50 rounded px-2 py-1 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400"
              aria-label="Refresh history"
              title="Refresh"
            >
              Refresh
            </button>
          </div>
          {/* Filter dropdown */}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-brand-400"
            aria-label="Filter by digest type"
          >
            {DIGEST_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Report list */}
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner size="md" label="Loading history..." />
            </div>
          )}

          {!isLoading && error && (
            <div className="px-4 py-6 text-center">
              <p className="text-sm text-red-600">{error}</p>
              <button
                type="button"
                onClick={refresh}
                className="mt-2 text-xs text-brand-600 hover:underline focus:outline-none"
              >
                Try again
              </button>
            </div>
          )}

          {!isLoading && !error && reports.length === 0 && (
            <div className="px-4 py-12 text-center">
              <p className="text-sm text-gray-500">
                No past digests yet. Generate your first digest to see it here.
              </p>
            </div>
          )}

          {!isLoading && !error && reports.length > 0 && (
            <ul className="flex flex-col gap-1.5 p-3">
              {reports.map((report) => (
                <li key={report.id}>
                  <ReportRow
                    report={report}
                    isSelected={selectedReportId === report.report_id}
                    isLoadingDetail={loadingRowId === report.report_id}
                    onClick={() => void handleRowClick(report)}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex-shrink-0 border-t border-gray-100 px-3 py-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setPage(page - 1)}
              disabled={!hasPrev}
              className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-brand-400"
            >
              Previous
            </button>
            <span className="text-xs text-gray-500">
              {page + 1} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage(page + 1)}
              disabled={!hasNext}
              className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-brand-400"
            >
              Next
            </button>
          </div>
        )}
      </aside>

      {/* Right panel — digest detail */}
      <div className="flex-1 overflow-hidden flex flex-col bg-gray-50">
        {loadingRowId && !selectedDigest && (
          <div className="flex-1 flex items-center justify-center">
            <LoadingSpinner size="lg" label="Loading digest..." />
          </div>
        )}

        {!loadingRowId && !selectedDigest && (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-sm text-gray-400">Select a digest to preview</p>
          </div>
        )}

        {selectedDigest && (
          <>
            <DetailHeader digest={selectedDigest} />
            <DashboardContent digest={selectedDigest} />
          </>
        )}
      </div>
    </div>
  );
}
