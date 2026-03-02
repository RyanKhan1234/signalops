/**
 * ToolTrace — collapsible accordion showing each MCP tool call
 * with its input parameters, output summary, and latency.
 * Rendered inline in the DigestViewer as the final section.
 */

import { useState } from 'react';
import type { ToolTraceEntry } from '../../types/digest';
import { SectionHeader } from '../common/SectionHeader';
import { formatDate } from '../../utils/formatDate';

interface ToolTraceProps {
  toolTrace: ToolTraceEntry[];
  reportId: string;
}

interface TraceEntryProps {
  entry: ToolTraceEntry;
  index: number;
}

/**
 * A single collapsible tool trace entry in the accordion.
 */
function TraceEntry({ entry, index }: TraceEntryProps) {
  const [isOpen, setIsOpen] = useState(false);

  const latencyColor =
    entry.latency_ms > 3000
      ? 'text-red-600'
      : entry.latency_ms > 1500
      ? 'text-yellow-600'
      : 'text-green-600';

  return (
    <div className="border-b border-gray-100 last:border-b-0">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-controls={`trace-body-${index}`}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-500 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded bg-gray-100 font-mono text-xs font-medium text-gray-600">
            {index + 1}
          </span>
          <code className="font-mono text-xs font-semibold text-gray-800 truncate">
            {entry.tool_name}
          </code>
          <span className="text-xs text-gray-400 hidden sm:inline">
            {formatDate(entry.timestamp)}
          </span>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <span className={`font-mono text-xs font-medium ${latencyColor}`}>
            {entry.latency_ms.toLocaleString()}ms
          </span>
          <svg
            className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>

      {isOpen && (
        <div
          id={`trace-body-${index}`}
          className="px-4 pb-4 pt-1"
          role="region"
          aria-label={`Tool trace for ${entry.tool_name}`}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            {/* Input params */}
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">
                Input
              </p>
              <pre className="overflow-auto rounded-md bg-gray-900 p-3 text-xs leading-relaxed text-green-300 max-h-40">
                {JSON.stringify(entry.input, null, 2)}
              </pre>
            </div>

            {/* Output summary */}
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">
                Output Summary
              </p>
              <div className="rounded-md bg-gray-50 p-3 text-xs leading-relaxed text-gray-700 max-h-40 overflow-auto">
                {entry.output_summary}
              </div>
            </div>
          </div>

          <div className="mt-2 flex items-center gap-4 text-xs text-gray-400">
            <span>
              Latency:{' '}
              <span className={`font-medium ${latencyColor}`}>
                {entry.latency_ms.toLocaleString()}ms
              </span>
            </span>
            <span>
              Timestamp:{' '}
              <time dateTime={entry.timestamp} className="font-mono">
                {entry.timestamp}
              </time>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Collapsible accordion of all tool calls in the digest pipeline.
 * Shows report ID prominently for traceability.
 */
export function ToolTrace({ toolTrace, reportId }: ToolTraceProps) {
  const totalLatency = toolTrace.reduce((sum, e) => sum + e.latency_ms, 0);

  if (toolTrace.length === 0) {
    return (
      <section aria-labelledby="tool-trace-heading">
        <SectionHeader title="Tool Trace" count={0} />
        <p className="text-sm text-gray-500">No tool calls recorded for this digest.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="tool-trace-heading">
      <SectionHeader
        title="Tool Trace"
        count={toolTrace.length}
        description="MCP tool calls made during digest generation — expand each to see inputs, outputs, and latency"
      />

      {/* Report metadata */}
      <div className="mb-3 flex flex-wrap items-center gap-4 rounded-lg bg-gray-50 px-4 py-2.5 text-xs">
        <span className="text-gray-500">
          Report ID:{' '}
          <code className="font-mono font-medium text-gray-800">{reportId}</code>
        </span>
        <span className="text-gray-500">
          Total API latency:{' '}
          <span className="font-medium text-gray-800">
            {totalLatency.toLocaleString()}ms
          </span>
        </span>
        <span className="text-gray-500">
          Tool calls:{' '}
          <span className="font-medium text-gray-800">{toolTrace.length}</span>
        </span>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        {toolTrace.map((entry, index) => (
          <TraceEntry key={index} entry={entry} index={index} />
        ))}
      </div>
    </section>
  );
}
