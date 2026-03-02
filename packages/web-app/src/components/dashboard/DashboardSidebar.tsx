/**
 * DashboardSidebar — left navigation panel for the dashboard layout.
 *
 * Shows anchor links to each digest section with counts, and displays
 * digest metadata at the bottom (report ID, generated_at, digest_type).
 * Active section is tracked via simple useState; clicking a nav item
 * sets the active panel.
 */

import { useState } from 'react';
import type { DigestResponse, DigestType } from '../../types/digest';

interface DashboardSidebarProps {
  digest: DigestResponse;
}

interface NavItem {
  id: string;
  label: string;
  href: string;
  count?: number;
  icon: React.ReactNode;
}

const DIGEST_TYPE_LABELS: Record<DigestType, string> = {
  daily_digest: 'Daily Digest',
  weekly_report: 'Weekly Report',
  risk_alert: 'Risk Alert',
  competitor_monitor: 'Competitor Monitor',
};

const DIGEST_TYPE_COLORS: Record<DigestType, string> = {
  daily_digest: 'bg-blue-50 border-blue-200 text-blue-800',
  weekly_report: 'bg-purple-50 border-purple-200 text-purple-800',
  risk_alert: 'bg-red-50 border-red-200 text-red-800',
  competitor_monitor: 'bg-amber-50 border-amber-200 text-amber-800',
};

/** Lightning bolt icon for Executive Summary */
function LightningIcon() {
  return (
    <svg
      className="h-4 w-4 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13 10V3L4 14h7v7l9-11h-7z"
      />
    </svg>
  );
}

/** Signal / wifi-like icon for Key Signals */
function SignalIcon() {
  return (
    <svg
      className="h-4 w-4 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.143 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0"
      />
    </svg>
  );
}

/** Warning / shield icon for Risks */
function RiskIcon() {
  return (
    <svg
      className="h-4 w-4 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  );
}

/** Sparkles / star icon for Opportunities */
function OpportunityIcon() {
  return (
    <svg
      className="h-4 w-4 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
      />
    </svg>
  );
}

/** Checkmark / clipboard icon for Action Items */
function ActionIcon() {
  return (
    <svg
      className="h-4 w-4 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
      />
    </svg>
  );
}

/** Link icon for Sources */
function SourcesIcon() {
  return (
    <svg
      className="h-4 w-4 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
      />
    </svg>
  );
}

/** Terminal / code icon for Tool Trace */
function ToolTraceIcon() {
  return (
    <svg
      className="h-4 w-4 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
      />
    </svg>
  );
}

/**
 * Left sidebar navigation for the dashboard layout.
 * Renders anchor links to each digest section with counts.
 */
export function DashboardSidebar({ digest }: DashboardSidebarProps) {
  const [activePanel, setActivePanel] = useState<string>('exec-summary-panel');

  const navItems: NavItem[] = [
    {
      id: 'exec-summary-panel',
      label: 'Executive Summary',
      href: '#exec-summary-panel',
      icon: <LightningIcon />,
    },
    {
      id: 'key-signals-panel',
      label: 'Key Signals',
      href: '#key-signals-panel',
      count: digest.key_signals.length,
      icon: <SignalIcon />,
    },
    {
      id: 'risks-panel',
      label: 'Risks',
      href: '#risks-panel',
      count: digest.risks.length,
      icon: <RiskIcon />,
    },
    {
      id: 'opportunities-panel',
      label: 'Opportunities',
      href: '#opportunities-panel',
      count: digest.opportunities.length,
      icon: <OpportunityIcon />,
    },
    {
      id: 'action-items-panel',
      label: 'Action Items',
      href: '#action-items-panel',
      count: digest.action_items.length,
      icon: <ActionIcon />,
    },
    {
      id: 'sources-panel',
      label: 'Sources',
      href: '#sources-panel',
      count: digest.sources.length,
      icon: <SourcesIcon />,
    },
    {
      id: 'tool-trace-panel',
      label: 'Tool Trace',
      href: '#tool-trace-panel',
      count: digest.tool_trace.length,
      icon: <ToolTraceIcon />,
    },
  ];

  const generatedAt = new Date(digest.generated_at).toLocaleString([], {
    dateStyle: 'short',
    timeStyle: 'short',
  });

  const truncatedReportId = digest.report_id.length > 20
    ? `${digest.report_id.slice(0, 20)}…`
    : digest.report_id;

  const typeLabel = DIGEST_TYPE_LABELS[digest.digest_type];
  const typeColor = DIGEST_TYPE_COLORS[digest.digest_type];

  return (
    <aside
      className="w-64 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col h-full overflow-hidden"
      aria-label="Dashboard navigation"
    >
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-gray-100">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 flex-shrink-0">
          <svg
            className="h-4 w-4 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
        </div>
        <span className="text-sm font-semibold text-gray-900">SignalOps</span>
      </div>

      {/* Nav links */}
      <nav className="flex-1 overflow-y-auto py-3" aria-label="Digest sections">
        <ul className="flex flex-col gap-0.5 px-2">
          {navItems.map((item) => {
            const isActive = activePanel === item.id;
            return (
              <li key={item.id}>
                <a
                  href={item.href}
                  onClick={() => setActivePanel(item.id)}
                  className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                    isActive
                      ? 'bg-brand-50 text-brand-700 border-l-2 border-brand-600 font-medium rounded-l-none pl-[10px]'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  }`}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <span className={isActive ? 'text-brand-600' : 'text-gray-400'}>
                    {item.icon}
                  </span>
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.count !== undefined && (
                    <span
                      className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-xs font-medium ${
                        isActive
                          ? 'bg-brand-100 text-brand-700'
                          : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {item.count}
                    </span>
                  )}
                </a>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Digest metadata footer */}
      <div className="border-t border-gray-100 px-4 py-4 space-y-2">
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
            Report
          </p>
          <p
            className="font-mono text-xs text-gray-600 truncate"
            title={digest.report_id}
          >
            {truncatedReportId}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
            Generated
          </p>
          <p className="text-xs text-gray-600">{generatedAt}</p>
        </div>
        <div>
          <span
            className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${typeColor}`}
          >
            {typeLabel}
          </span>
        </div>
      </div>
    </aside>
  );
}
