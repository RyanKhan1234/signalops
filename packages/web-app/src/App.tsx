/**
 * SignalOps — App root component.
 *
 * Layout:
 * - Top header bar with branding, view-switching nav, mock API badge, and clear button
 * - Body: varies by currentView
 *   - 'digest': optional left sidebar + main content area (empty state / spinner / dashboard)
 *   - 'history': full-width HistoryList component
 * - Query bar at the bottom (digest view only, when digest is loaded)
 * - Fixed: debug panel toggle (bottom-right)
 */

import { useState } from 'react';
import { useDigest } from './hooks/useDigest';
import { useSaveReport } from './hooks/useSaveReport';
import { DebugPanel } from './components/debug/DebugPanel';
import { LoadingSpinner } from './components/common/LoadingSpinner';
import {
  EmptyState,
  DashboardSidebar,
  DashboardContent,
  QueryBar,
} from './components/dashboard';
import { HistoryList } from './components/history';

type CurrentView = 'digest' | 'history';

function App() {
  const { isLoading, latestDigest, submitPrompt, clearMessages } =
    useDigest();
  const { status: saveStatus, save: saveDigest } = useSaveReport();
  const [currentView, setCurrentView] = useState<CurrentView>('digest');

  return (
    <div className="flex h-screen flex-col bg-gray-50 overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 h-14 border-b border-gray-200 bg-white px-6 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600">
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
            <span className="font-semibold text-gray-900">SignalOps</span>
            <span className="text-xs text-gray-500 hidden sm:block">
              Competitive Intelligence
            </span>
          </div>

          {/* View navigation tabs */}
          <nav className="flex items-center gap-1 ml-4" aria-label="Main navigation">
            <button
              type="button"
              onClick={() => setCurrentView('digest')}
              className={
                currentView === 'digest'
                  ? 'bg-brand-50 text-brand-700 rounded-lg px-3 py-1.5 text-sm font-medium'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-lg px-3 py-1.5 text-sm'
              }
              aria-current={currentView === 'digest' ? 'page' : undefined}
            >
              Dashboard
            </button>
            <button
              type="button"
              onClick={() => setCurrentView('history')}
              className={
                currentView === 'history'
                  ? 'bg-brand-50 text-brand-700 rounded-lg px-3 py-1.5 text-sm font-medium'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-lg px-3 py-1.5 text-sm'
              }
              aria-current={currentView === 'history' ? 'page' : undefined}
            >
              History
            </button>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          {/* Mock API indicator */}
          {import.meta.env['VITE_USE_MOCK_API'] === 'true' && (
            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
              Mock API
            </span>
          )}

          {currentView === 'digest' && latestDigest && (
            <>
              <button
                type="button"
                onClick={() => saveDigest(latestDigest, latestDigest.query)}
                disabled={saveStatus === 'saving' || saveStatus === 'saved'}
                className={
                  saveStatus === 'saved'
                    ? 'text-sm border rounded-lg px-3 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 bg-green-50 border-green-300 text-green-700 cursor-default focus:ring-green-400'
                    : saveStatus === 'error'
                    ? 'text-sm border rounded-lg px-3 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 bg-red-50 border-red-300 text-red-700 hover:bg-red-100 focus:ring-red-400'
                    : saveStatus === 'saving'
                    ? 'text-sm border rounded-lg px-3 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 border-gray-200 text-gray-400 cursor-not-allowed focus:ring-gray-400'
                    : 'text-sm text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1'
                }
                aria-label="Save digest to history"
              >
                {saveStatus === 'saving' && (
                  <span className="flex items-center gap-1.5">
                    <svg
                      className="h-3.5 w-3.5 animate-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                      aria-hidden="true"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z"
                      />
                    </svg>
                    Saving&hellip;
                  </span>
                )}
                {saveStatus === 'saved' && (
                  <span className="flex items-center gap-1.5">
                    <svg
                      className="h-3.5 w-3.5"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2.5}
                      aria-hidden="true"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    Saved
                  </span>
                )}
                {saveStatus === 'error' && 'Save failed'}
                {saveStatus === 'idle' && (
                  <span className="flex items-center gap-1.5">
                    <svg
                      className="h-3.5 w-3.5"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
                      />
                    </svg>
                    Save to History
                  </span>
                )}
              </button>
              <button
                type="button"
                onClick={clearMessages}
                className="text-sm text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1"
                aria-label="Clear digest and start over"
              >
                New Digest
              </button>
            </>
          )}
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {currentView === 'history' ? (
          /* History view — full width */
          <HistoryList />
        ) : (
          /* Digest view — sidebar + main content */
          <>
            {/* Sidebar — only shown when digest is loaded */}
            {latestDigest && !isLoading && (
              <DashboardSidebar digest={latestDigest} />
            )}

            {/* Main content area */}
            <div className="flex-1 overflow-hidden flex flex-col">
              {!latestDigest && !isLoading && (
                <EmptyState onSubmit={submitPrompt} isLoading={isLoading} />
              )}

              {isLoading && (
                <div className="flex-1 flex items-center justify-center">
                  <LoadingSpinner size="lg" label="Generating digest..." />
                </div>
              )}

              {latestDigest && !isLoading && (
                <DashboardContent digest={latestDigest} />
              )}
            </div>
          </>
        )}
      </div>

      {/* Query bar — shown in digest view when digest is loaded */}
      {currentView === 'digest' && latestDigest && (
        <QueryBar onClear={clearMessages} isLoading={isLoading} />
      )}

      {/* Debug panel — only shown when there is a digest response */}
      <DebugPanel digest={latestDigest} />
    </div>
  );
}

export default App;
