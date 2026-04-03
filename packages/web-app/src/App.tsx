/**
 * SignalOps — App root component.
 *
 * Layout:
 * - Header: logo + "Save to History" button (shown when latestDigest exists)
 * - Body: ChatSidebar (w-64) + ChatThread (flex-1, scrollable)
 * - Footer: persistent ChatInput (always visible)
 *
 * Session management (in-memory only):
 * - Current session: messages tracked by useDigest
 * - Past sessions: stored in `sessions` state, newest first
 * - "New Chat": saves current session, clears messages
 * - Session switching: renders that session's messages read-only
 */

import { useState, useCallback } from 'react';
import { useDigest } from './hooks/useDigest';
import { useSaveReport } from './hooks/useSaveReport';
import { DebugPanel } from './components/debug/DebugPanel';
import { ChatInput } from './components/chat/ChatInput';
import { ChatThread } from './components/chat/ChatThread';
import { ChatSidebar } from './components/chat/ChatSidebar';
import type { Session } from './components/chat/ChatSidebar';
import type { ChatMessage } from './types/digest';
import { generateId } from './utils/generateId';

function App() {
  const { messages, isLoading, latestDigest, submitPrompt, clearMessages } =
    useDigest();
  const { status: saveStatus, save: saveDigest } = useSaveReport();

  // Past sessions stored in memory, newest first
  const [sessions, setSessions] = useState<Session[]>([]);
  // When non-null, we are viewing a past session (read-only)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  // Messages to display — either current session or a selected past session
  const [viewMessages, setViewMessages] = useState<ChatMessage[] | null>(null);

  /**
   * Displayed messages: viewMessages when browsing a past session,
   * otherwise the live messages from useDigest.
   */
  const displayMessages: ChatMessage[] = viewMessages ?? messages;

  /**
   * New Chat: save current session (if non-empty), then clear.
   */
  const handleNewChat = useCallback(() => {
    if (messages.length === 0) return;

    // Derive session title from first user message, truncated to 40 chars
    const firstUserMsg = messages.find((m) => m.type === 'user');
    const rawTitle = firstUserMsg
      ? (firstUserMsg.content as string)
      : 'Untitled session';
    const title =
      rawTitle.length > 40 ? `${rawTitle.slice(0, 40)}…` : rawTitle;

    const newSession: Session = {
      id: generateId(),
      title,
      messages: [...messages],
      createdAt: new Date().toISOString(),
    };

    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(null);
    setViewMessages(null);
    clearMessages();
  }, [messages, clearMessages]);

  /**
   * Select a past session for read-only display.
   */
  const handleSelectSession = useCallback(
    (id: string) => {
      const session = sessions.find((s) => s.id === id);
      if (!session) return;
      setActiveSessionId(id);
      setViewMessages(session.messages);
    },
    [sessions]
  );

  /**
   * Submit a new prompt.
   * If currently viewing a past session, switch back to the live session first.
   */
  const handleSubmit = useCallback(
    (prompt: string) => {
      if (activeSessionId !== null) {
        // Switch back to the live current session
        setActiveSessionId(null);
        setViewMessages(null);
      }
      void submitPrompt(prompt);
    },
    [activeSessionId, submitPrompt]
  );

  const isCurrentSessionEmpty = messages.length === 0;

  return (
    <div className="flex h-screen flex-col bg-gray-50 overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 h-14 border-b border-gray-200 bg-white px-6 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          {/* Logo — visible in header for context; sidebar also shows it */}
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
              Personal Research Tool
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Mock API indicator */}
          {import.meta.env['VITE_USE_MOCK_API'] === 'true' && (
            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
              Mock API
            </span>
          )}

          {/* Save to History button — shown when latest digest is available */}
          {latestDigest && (
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
          )}
        </div>
      </header>

      {/* Body: sidebar + thread */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar: session list + New Chat */}
        <ChatSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          isCurrentSessionEmpty={isCurrentSessionEmpty}
          onNewChat={handleNewChat}
          onSelectSession={handleSelectSession}
        />

        {/* Main area: chat thread (scrollable) */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <ChatThread
            messages={displayMessages}
            isLoading={isLoading && activeSessionId === null}
          />
        </div>
      </div>

      {/* Persistent bottom input — always visible */}
      <div className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-4 z-10">
        <div className="max-w-4xl mx-auto">
          <ChatInput onSubmit={handleSubmit} isLoading={isLoading} />
        </div>
      </div>

      {/* Debug panel — only shown when there is a digest response */}
      <DebugPanel digest={latestDigest} />
    </div>
  );
}

export default App;
