/**
 * ExecutiveSummary — displays the top-level digest summary with metadata.
 */

import type { DigestResponse } from '../../types/digest';
import { SectionHeader } from '../common/SectionHeader';

const DIGEST_TYPE_LABELS: Record<DigestResponse['digest_type'], string> = {
  latest_news: 'Latest News',
  deep_dive: 'Deep Dive',
  risk_scan: 'Risk Scan',
  trend_watch: 'Trend Watch',
};

const DIGEST_TYPE_COLORS: Record<DigestResponse['digest_type'], string> = {
  latest_news: 'bg-blue-50 border-blue-200 text-blue-800',
  deep_dive: 'bg-purple-50 border-purple-200 text-purple-800',
  risk_scan: 'bg-red-50 border-red-200 text-red-800',
  trend_watch: 'bg-amber-50 border-amber-200 text-amber-800',
};

interface ExecutiveSummaryProps {
  digest: DigestResponse;
}

/**
 * Prominent executive summary block shown at the top of every digest.
 * Includes digest type, report ID, generation timestamp, and summary text.
 */
export function ExecutiveSummary({ digest }: ExecutiveSummaryProps) {
  const typeLabel = DIGEST_TYPE_LABELS[digest.digest_type];
  const typeColor = DIGEST_TYPE_COLORS[digest.digest_type];

  const generatedAt = new Date(digest.generated_at).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  });

  return (
    <section aria-labelledby="exec-summary-heading">
      <SectionHeader
        title="Executive Summary"
        description={`Query: "${digest.query}"`}
      />

      {/* Metadata row */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-medium ${typeColor}`}
        >
          {typeLabel}
        </span>
        <span className="text-xs text-gray-400">
          Generated {generatedAt}
        </span>
        <span className="text-xs text-gray-300">|</span>
        <span className="font-mono text-xs text-gray-400">
          {digest.report_id}
        </span>
      </div>

      {/* Summary text */}
      <div className="rounded-xl border border-brand-100 bg-brand-50 p-5">
        <p
          id="exec-summary-heading"
          className="text-base leading-relaxed text-gray-800"
        >
          {digest.executive_summary}
        </p>
      </div>
    </section>
  );
}
