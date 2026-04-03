/**
 * KeySignals — renders the list of key findings extracted from source articles.
 */

import type { KeySignal } from '../../types/digest';
import { Badge } from '../common/Badge';
import { Card } from '../common/Card';
import { SectionHeader } from '../common/SectionHeader';
import { formatDate } from '../../utils/formatDate';

interface KeySignalsProps {
  signals: KeySignal[];
}

export function KeySignals({ signals }: KeySignalsProps) {
  if (signals.length === 0) {
    return (
      <section aria-labelledby="signals-heading">
        <SectionHeader title="Key Findings" count={0} />
        <p className="text-sm text-gray-500">Nothing notable turned up for this query.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="signals-heading">
      <SectionHeader
        title="Key Findings"
        count={signals.length}
        description="The most interesting things that came up in the research"
      />
      <ol className="flex flex-col gap-3" aria-label="Key signals list">
        {signals.map((signal, index) => (
          <li key={`${signal.source_url}-${index}`}>
            <Card>
              <div className="flex items-start gap-3">
                {/* Rank indicator */}
                <span
                  className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-500"
                  aria-label={`Signal ${index + 1}`}
                >
                  {index + 1}
                </span>

                <div className="flex-1 min-w-0">
                  <p className="text-sm leading-relaxed text-gray-800">
                    {signal.signal}
                  </p>

                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge variant={signal.relevance} />

                    <a
                      href={signal.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 hover:underline focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 rounded"
                      aria-label={`Source: ${signal.source_title} (opens in new tab)`}
                    >
                      <svg
                        className="h-3 w-3 flex-shrink-0"
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
                      <span className="truncate max-w-xs">{signal.source_title}</span>
                    </a>

                    <span className="text-xs text-gray-400">
                      {formatDate(signal.published_date)}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          </li>
        ))}
      </ol>
    </section>
  );
}
