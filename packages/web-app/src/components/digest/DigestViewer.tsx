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
      <ErrorBoundary sectionName="Executive Summary">
        <ExecutiveSummary digest={digest} />
      </ErrorBoundary>

      <ErrorBoundary sectionName="Key Signals">
        <KeySignals signals={digest.key_signals} />
      </ErrorBoundary>

      <ErrorBoundary sectionName="Risks">
        <Risks risks={digest.risks} />
      </ErrorBoundary>

      <ErrorBoundary sectionName="Opportunities">
        <Opportunities opportunities={digest.opportunities} />
      </ErrorBoundary>

      <ErrorBoundary sectionName="Action Items">
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
