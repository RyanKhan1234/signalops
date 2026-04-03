/**
 * DigestViewer — top-level composer for all digest sections.
 * Renders each section in order with error boundaries wrapping each one.
 */

import type { DigestResponse } from '../../types/digest';
import { ErrorBoundary } from '../common/ErrorBoundary';
import { ExecutiveSummary } from './ExecutiveSummary';
import { KeySignals } from './KeySignals';
import { Risks } from './Risks';
import { Opportunities } from './Opportunities';
import { ActionItems } from './ActionItems';
import { Sources } from './Sources';
import { ToolTrace } from '../debug/ToolTrace';

interface DigestViewerProps {
  digest: DigestResponse;
}

/**
 * Composes all digest sections in the correct display order.
 * Each section is wrapped in an ErrorBoundary for resilience.
 */
export function DigestViewer({ digest }: DigestViewerProps) {
  return (
    <article
      className="flex flex-col gap-8"
      aria-label={`Digest: ${digest.query}`}
    >
      <ErrorBoundary sectionName="Overview">
        <ExecutiveSummary digest={digest} />
      </ErrorBoundary>

      {digest.research_summary && (
        <ErrorBoundary sectionName="Research Notes">
          <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-5">
            <h3 className="mb-2 text-sm font-semibold text-indigo-900">Research Notes</h3>
            <p className="text-sm leading-relaxed text-indigo-800 whitespace-pre-line">
              {digest.research_summary}
            </p>
            {digest.reasoning_steps && digest.reasoning_steps.length > 0 && (
              <details className="mt-3">
                <summary className="cursor-pointer text-xs font-medium text-indigo-600 hover:text-indigo-800">
                  Show reasoning ({digest.reasoning_steps.length} steps)
                </summary>
                <ol className="mt-2 space-y-1.5 pl-4 text-xs text-indigo-700">
                  {digest.reasoning_steps.map((step, i) => (
                    <li key={i} className="list-decimal leading-relaxed">
                      {step.length > 300 ? step.slice(0, 300) + '...' : step}
                    </li>
                  ))}
                </ol>
              </details>
            )}
          </div>
        </ErrorBoundary>
      )}

      <ErrorBoundary sectionName="Key Findings">
        <KeySignals signals={digest.key_signals} />
      </ErrorBoundary>

      <ErrorBoundary sectionName="Heads Up">
        <Risks risks={digest.risks} />
      </ErrorBoundary>

      <ErrorBoundary sectionName="Worth Exploring">
        <Opportunities opportunities={digest.opportunities} />
      </ErrorBoundary>

      <ErrorBoundary sectionName="Next Steps">
        <ActionItems actionItems={digest.action_items} />
      </ErrorBoundary>

      <ErrorBoundary sectionName="Sources">
        <Sources sources={digest.sources} />
      </ErrorBoundary>

      <ErrorBoundary sectionName="Tool Trace">
        <ToolTrace toolTrace={digest.tool_trace} reportId={digest.report_id} />
      </ErrorBoundary>
    </article>
  );
}
