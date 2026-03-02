/**
 * Opportunities — renders identified strategic opportunities with confidence indicators.
 */

import type { Opportunity } from '../../types/digest';
import { Badge } from '../common/Badge';
import { Card } from '../common/Card';
import { SectionHeader } from '../common/SectionHeader';

interface OpportunitiesProps {
  opportunities: Opportunity[];
}

const CONFIDENCE_ICON: Record<Opportunity['confidence'], string> = {
  high: '↑',
  medium: '→',
  low: '↓',
};

/**
 * Renders a list of opportunities with confidence levels and source references.
 */
export function Opportunities({ opportunities }: OpportunitiesProps) {
  if (opportunities.length === 0) {
    return (
      <section aria-labelledby="opportunities-heading">
        <SectionHeader title="Opportunities" count={0} />
        <p className="text-sm text-gray-500">No opportunities identified for this query.</p>
      </section>
    );
  }

  const ORDER = { high: 0, medium: 1, low: 2 };
  const sorted = [...opportunities].sort(
    (a, b) => ORDER[a.confidence] - ORDER[b.confidence]
  );

  return (
    <section aria-labelledby="opportunities-heading">
      <SectionHeader
        title="Opportunities"
        count={opportunities.length}
        description="Strategic openings and potential advantages identified from source articles"
      />
      <ul className="flex flex-col gap-3" aria-label="Opportunities list">
        {sorted.map((opportunity, index) => (
          <li key={index}>
            <Card className="border-l-4 border-l-emerald-400">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2 flex-1">
                  <span
                    className="mt-0.5 text-lg leading-none text-emerald-500 font-bold"
                    aria-hidden="true"
                  >
                    {CONFIDENCE_ICON[opportunity.confidence]}
                  </span>
                  <p className="text-sm leading-relaxed text-gray-800">
                    {opportunity.description}
                  </p>
                </div>
                <Badge variant={opportunity.confidence} prefix="Confidence" className="flex-shrink-0" />
              </div>

              {opportunity.source_urls.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {opportunity.source_urls.map((url, urlIndex) => (
                    <a
                      key={urlIndex}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded bg-gray-50 px-2 py-0.5 text-xs text-brand-600 hover:bg-gray-100 hover:text-brand-800 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1"
                      aria-label={`Source ${urlIndex + 1} (opens in new tab)`}
                    >
                      <svg
                        className="h-3 w-3"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                        />
                      </svg>
                      Source {urlIndex + 1}
                    </a>
                  ))}
                </div>
              )}
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}
