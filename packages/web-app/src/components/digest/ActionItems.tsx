/**
 * ActionItems — renders prioritized follow-up actions from a digest.
 * Items are displayed as an ordered list with P0/P1/P2 priority badges.
 */

import type { ActionItem } from '../../types/digest';
import { Badge } from '../common/Badge';
import { Card } from '../common/Card';
import { SectionHeader } from '../common/SectionHeader';

interface ActionItemsProps {
  actionItems: ActionItem[];
}

const PRIORITY_ORDER = { P0: 0, P1: 1, P2: 2 };

/**
 * Renders an ordered list of action items sorted by priority (P0 first).
 */
export function ActionItems({ actionItems }: ActionItemsProps) {
  if (actionItems.length === 0) {
    return (
      <section aria-labelledby="action-items-heading">
        <SectionHeader title="Action Items" count={0} />
        <p className="text-sm text-gray-500">No action items generated for this digest.</p>
      </section>
    );
  }

  const sorted = [...actionItems].sort(
    (a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
  );

  return (
    <section aria-labelledby="action-items-heading">
      <SectionHeader
        title="Action Items"
        count={actionItems.length}
        description="Prioritized next steps and follow-ups based on what was found"
      />
      <ol className="flex flex-col gap-3" aria-label="Action items list">
        {sorted.map((item, index) => (
          <li key={index}>
            <Card>
              <div className="flex items-start gap-3">
                {/* Step number */}
                <span
                  className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white"
                  aria-label={`Action ${index + 1}`}
                >
                  {index + 1}
                </span>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium leading-snug text-gray-900">
                      {item.action}
                    </p>
                    <Badge variant={item.priority} className="flex-shrink-0" />
                  </div>

                  {item.rationale && (
                    <p className="mt-2 text-xs leading-relaxed text-gray-500">
                      <span className="font-medium text-gray-600">Rationale: </span>
                      {item.rationale}
                    </p>
                  )}
                </div>
              </div>
            </Card>
          </li>
        ))}
      </ol>
    </section>
  );
}
