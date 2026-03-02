/**
 * SignalOps — App root component.
 *
 * Layout:
 * - Top navigation bar with branding and clear button
 * - Main content area: scrollable message thread
 * - Sticky bottom: chat input
 * - Fixed: debug panel toggle (bottom-right)
 */

import { useRef, useEffect } from 'react';
import { useDigest } from './hooks/useDigest';
import { ChatInput } from './components/chat/ChatInput';
import { ChatMessageList } from './components/chat/ChatMessageList';
import { DebugPanel } from './components/debug/DebugPanel';
import { ErrorBoundary } from './components/common/ErrorBoundary';

function App() {
  const { messages, isLoading, latestDigest, submitPrompt, clearMessages } =
    useDigest();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* Navigation bar */}
      <header className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-3 shadow-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Logo */}
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
              <svg
                className="h-5 w-5 text-white"
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
            <div>
              <h1 className="text-sm font-bold text-gray-900">SignalOps</h1>
              <p className="text-xs text-gray-400">Competitive Intelligence</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Mock API indicator */}
            {import.meta.env['VITE_USE_MOCK_API'] === 'true' && (
              <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                Mock API
              </span>
            )}

            {messages.length > 0 && (
              <button
                type="button"
                onClick={clearMessages}
                className="rounded-md px-3 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1 transition-colors"
                aria-label="Clear chat history"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main scrollable content */}
      <main
        className="flex-1 overflow-y-auto"
        id="main-content"
        aria-label="Chat conversation"
      >
        <div className="mx-auto max-w-4xl px-6 py-6">
          <ErrorBoundary sectionName="Chat messages">
            <ChatMessageList messages={messages} isLoading={isLoading} />
          </ErrorBoundary>
          {/* Scroll anchor */}
          <div ref={bottomRef} aria-hidden="true" />
        </div>
      </main>

      {/* Sticky chat input footer */}
      <footer className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-4 shadow-lg">
        <div className="mx-auto max-w-4xl">
          <ErrorBoundary sectionName="Chat input">
            <ChatInput onSubmit={submitPrompt} isLoading={isLoading} />
          </ErrorBoundary>
        </div>
      </footer>

      {/* Debug panel — only shown when there is a digest response */}
      <DebugPanel digest={latestDigest} />
    </div>
  );
}

export default App;
