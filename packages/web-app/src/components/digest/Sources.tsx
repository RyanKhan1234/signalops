/**
 * Sources — compact list of all source articles referenced in the digest.
 * Traceability requirement: every source must have a clickable external link.
 */

import type { Source } from '../../types/digest';
import { SectionHeader } from '../common/SectionHeader';
import { formatDate } from '../../utils/formatDate';

interface SourcesProps {
  sources: Source[];
}

/**
 * Renders a compact, numbered list of source articles with external links.
 * Supports the traceability invariant: all claims must link to a source.
 */
export function Sources({ sources }: SourcesProps) {
  if (sources.length === 0) {
    return (
      <section aria-labelledby="sources-heading">
        <SectionHeader title="Sources" count={0} />
        <p className="text-sm text-gray-500">No sources referenced in this digest.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="sources-heading">
      <SectionHeader
        title="Sources"
        count={sources.length}
        description="All source articles referenced in this digest. Every claim is traceable to a source."
      />
      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        <ol className="divide-y divide-gray-100" aria-label="Source articles list">
          {sources.map((source, index) => (
            <li key={index} className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 transition-colors">
              {/* Source number */}
              <span
                className="mt-0.5 flex-shrink-0 font-mono text-xs font-medium text-gray-400 w-6 text-right"
                aria-label={`Source ${index + 1}`}
              >
                [{index + 1}]
              </span>

              <div className="flex-1 min-w-0">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-brand-700 hover:text-brand-900 hover:underline focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 rounded line-clamp-1"
                  aria-label={`${source.title} (opens in new tab)`}
                >
                  {source.title}
                </a>
                <p className="mt-0.5 text-xs text-gray-400">
                  {formatDate(source.published_date)}
                </p>
                {source.snippet && (
                  <p className="mt-1 text-xs leading-relaxed text-gray-500 line-clamp-2">
                    {source.snippet}
                  </p>
                )}
              </div>

              {/* External link icon */}
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                tabIndex={-1}
                aria-hidden="true"
                className="mt-0.5 flex-shrink-0 text-gray-300 hover:text-brand-500"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                  />
                </svg>
              </a>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
