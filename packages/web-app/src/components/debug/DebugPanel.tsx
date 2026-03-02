/**
 * DebugPanel — toggle-able side panel showing the full raw digest JSON
 * and per-tool-call breakdown.
 */

import { useState } from 'react';
import type { DigestResponse } from '../../types/digest';

interface DebugPanelProps {
  digest: DigestResponse | null;
}

/**
 * Sliding debug panel that shows raw JSON of the full digest response.
 * Toggled via a floating button in the bottom-right corner.
 */
export function DebugPanel({ digest }: DebugPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'raw' | 'trace'>('raw');

  if (!digest) return null;

  return (
    <>
      {/* Toggle button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={isOpen ? 'Close debug panel' : 'Open debug panel'}
        aria-expanded={isOpen}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full bg-gray-900 px-4 py-2.5 text-xs font-medium text-white shadow-lg hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
      >
        <svg
          className="h-3.5 w-3.5"
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
        Debug
        {isOpen && (
          <span className="ml-1 text-gray-400">✕</span>
        )}
      </button>

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <aside
        className={`fixed bottom-0 right-0 z-50 flex h-[70vh] w-full flex-col border-l border-t border-gray-200 bg-white shadow-2xl transition-transform duration-300 sm:w-[520px] rounded-tl-xl ${
          isOpen ? 'translate-y-0' : 'translate-y-full'
        }`}
        role="complementary"
        aria-label="Debug panel"
        aria-hidden={!isOpen}
      >
        {/* Panel header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Debug Panel</h2>
            <p className="text-xs text-gray-500">
              Report:{' '}
              <code className="font-mono">{digest.report_id}</code>
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            aria-label="Close debug panel"
            className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          {(['raw', 'trace'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              role="tab"
              aria-selected={activeTab === tab}
              className={`px-5 py-2.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-500 ${
                activeTab === tab
                  ? 'border-b-2 border-brand-600 text-brand-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab === 'raw' ? 'Raw JSON' : `Tool Calls (${digest.tool_trace.length})`}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-auto">
          {activeTab === 'raw' && (
            <pre className="p-4 font-mono text-xs leading-relaxed text-green-300 bg-gray-900 min-h-full">
              {JSON.stringify(digest, null, 2)}
            </pre>
          )}

          {activeTab === 'trace' && (
            <div className="divide-y divide-gray-100 p-4 flex flex-col gap-4">
              {digest.tool_trace.map((entry, index) => {
                const latencyColor =
                  entry.latency_ms > 3000
                    ? 'text-red-600'
                    : entry.latency_ms > 1500
                    ? 'text-yellow-600'
                    : 'text-green-600';

                return (
                  <div key={index} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <code className="text-xs font-bold text-gray-800">
                        {index + 1}. {entry.tool_name}
                      </code>
                      <span className={`font-mono text-xs font-medium ${latencyColor}`}>
                        {entry.latency_ms.toLocaleString()}ms
                      </span>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2 text-xs">
                      <div>
                        <p className="mb-1 font-semibold text-gray-500 uppercase tracking-wider text-[10px]">Input</p>
                        <pre className="rounded bg-gray-900 p-2 text-green-300 text-[10px] leading-relaxed overflow-auto max-h-24">
                          {JSON.stringify(entry.input, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <p className="mb-1 font-semibold text-gray-500 uppercase tracking-wider text-[10px]">Output</p>
                        <p className="text-[11px] text-gray-600 leading-relaxed">{entry.output_summary}</p>
                      </div>
                    </div>
                    <p className="mt-2 text-[10px] text-gray-400 font-mono">{entry.timestamp}</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
