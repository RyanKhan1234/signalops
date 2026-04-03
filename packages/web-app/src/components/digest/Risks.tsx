/**
 * Risks — renders things to watch out for, with impact indicators and source links.
 */

import type { Risk } from '../../types/digest';
import { Badge } from '../common/Badge';
import { Card } from '../common/Card';
import { SectionHeader } from '../common/SectionHeader';

interface RisksProps {
  risks: Risk[];
}

const SEVERITY_BORDER: Record<Risk['severity'], string> = {
  high: 'border-l-4 border-l-red-400',
  medium: 'border-l-4 border-l-yellow-400',
  low: 'border-l-4 border-l-green-400',
};

export function Risks({ risks }: RisksProps) {
  if (risks.length === 0) {
    return (
      <section aria-labelledby="risks-heading">
        <SectionHeader title="Heads Up" count={0} />
        <p className="text-sm text-gray-500">Nothing concerning came up this time.</p>
      </section>
    );
  }

  const ORDER = { high: 0, medium: 1, low: 2 };
  const sorted = [...risks].sort(
    (a, b) => ORDER[a.severity] - ORDER[b.severity]
  );

  return (
    <section aria-labelledby="risks-heading">
      <SectionHeader
        title="Heads Up"
        count={risks.length}
        description="Things worth keeping an eye on — potential concerns or shifts"
      />
      <ul className="flex flex-col gap-3" aria-label="Risk list">
        {sorted.map((risk, index) => (
          <li key={index}>
            <Card className={SEVERITY_BORDER[risk.severity]}>
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm leading-relaxed text-gray-800">
                  {risk.description}
                </p>
                <Badge variant={risk.severity} className="flex-shrink-0" />
              </div>

              {risk.source_urls.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {risk.source_urls.map((url, urlIndex) => (
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
