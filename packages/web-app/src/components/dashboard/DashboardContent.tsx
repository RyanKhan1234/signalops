/**
 * DashboardContent — scrollable right region of the dashboard layout.
 * Renders each digest section inside a PanelCard with anchor IDs,
 * wrapping each in an ErrorBoundary for resilience.
 */

import type { DigestResponse } from '../../types/digest';
import { ErrorBoundary } from '../common/ErrorBoundary';
import { ExecutiveSummary } from '../digest/ExecutiveSummary';
import { KeySignals } from '../digest/KeySignals';
import { Risks } from '../digest/Risks';
import { Opportunities } from '../digest/Opportunities';
import { ActionItems } from '../digest/ActionItems';
import { Sources } from '../digest/Sources';
import { ToolTrace } from '../debug/ToolTrace';
import { PanelCard } from './PanelCard';

interface DashboardContentProps {
  digest: DigestResponse;
}

/**
 * Main scrollable content area for the dashboard.
 * Each section is anchored by its panel ID for sidebar navigation.
 */
export function DashboardContent({ digest }: DashboardContentProps) {
  return (
    <div
      className="flex-1 overflow-y-auto bg-gray-50"
      id="dashboard-scroll-container"
    >
      <div className="max-w-4xl mx-auto px-6 py-8 flex flex-col gap-6">
        <PanelCard id="exec-summary-panel">
          <div className="p-6">
            <ErrorBoundary sectionName="Executive Summary">
              <ExecutiveSummary digest={digest} />
            </ErrorBoundary>
          </div>
        </PanelCard>

        <PanelCard id="key-signals-panel">
          <div className="p-6">
            <ErrorBoundary sectionName="Key Signals">
              <KeySignals signals={digest.key_signals} />
            </ErrorBoundary>
          </div>
        </PanelCard>

        <PanelCard id="risks-panel">
          <div className="p-6">
            <ErrorBoundary sectionName="Risks">
              <Risks risks={digest.risks} />
            </ErrorBoundary>
          </div>
        </PanelCard>

        <PanelCard id="opportunities-panel">
          <div className="p-6">
            <ErrorBoundary sectionName="Opportunities">
              <Opportunities opportunities={digest.opportunities} />
            </ErrorBoundary>
          </div>
        </PanelCard>

        <PanelCard id="action-items-panel">
          <div className="p-6">
            <ErrorBoundary sectionName="Action Items">
              <ActionItems actionItems={digest.action_items} />
            </ErrorBoundary>
          </div>
        </PanelCard>

        <PanelCard id="sources-panel">
          <div className="p-6">
            <ErrorBoundary sectionName="Sources">
              <Sources sources={digest.sources} />
            </ErrorBoundary>
          </div>
        </PanelCard>

        <PanelCard id="tool-trace-panel">
          <div className="p-6">
            <ErrorBoundary sectionName="Tool Trace">
              <ToolTrace
                toolTrace={digest.tool_trace}
                reportId={digest.report_id}
              />
            </ErrorBoundary>
          </div>
        </PanelCard>
      </div>
    </div>
  );
}
