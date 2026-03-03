/**
 * ChatSidebar — left navigation panel for the ChatGPT-style session layout.
 *
 * Shows:
 * - SignalOps logo + New Chat button at top
 * - List of past sessions (newest first) with truncated titles
 * - Active session highlighted in brand color
 */

import type { ChatMessage } from '../../types/digest';

export interface Session {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
}

interface ChatSidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  isCurrentSessionEmpty: boolean;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
}

/** Pencil / compose icon for New Chat button */
function ComposeIcon() {
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
        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
      />
    </svg>
  );
}

/** Chat bubble icon for session items */
function ChatIcon() {
  return (
    <svg
      className="h-3.5 w-3.5 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
      />
    </svg>
  );
}

/**
 * Left sidebar for session management in the chat layout.
 */
export function ChatSidebar({
  sessions,
  activeSessionId,
  isCurrentSessionEmpty,
  onNewChat,
  onSelectSession,
}: ChatSidebarProps) {
  return (
    <aside
      className="w-64 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col h-full overflow-hidden"
      aria-label="Chat sessions"
    >
      {/* Header: logo + new chat button */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
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

        <button
          type="button"
          onClick={onNewChat}
          disabled={isCurrentSessionEmpty}
          aria-label="Clear digest and start over"
          title="New Chat"
          className="flex items-center justify-center rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ComposeIcon />
        </button>
      </div>

      {/* Session list */}
      <nav className="flex-1 overflow-y-auto py-2" aria-label="Past sessions">
        {sessions.length === 0 ? (
          <div className="px-4 py-6 text-center">
            <p className="text-xs text-gray-400">No past sessions yet.</p>
            <p className="text-xs text-gray-400 mt-1">
              Start a chat to see sessions here.
            </p>
          </div>
        ) : (
          <ul className="flex flex-col gap-0.5 px-2">
            {sessions.map((session) => {
              const isActive = activeSessionId === session.id;
              const dateLabel = new Date(session.createdAt).toLocaleDateString([], {
                month: 'short',
                day: 'numeric',
              });

              return (
                <li key={session.id}>
                  <button
                    type="button"
                    onClick={() => onSelectSession(session.id)}
                    className={`w-full flex items-start gap-2 px-3 py-2.5 rounded-lg text-left text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 ${
                      isActive
                        ? 'bg-brand-50 text-brand-700 border-l-2 border-brand-600 font-medium rounded-l-none pl-[10px]'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <span
                      className={`mt-0.5 ${isActive ? 'text-brand-500' : 'text-gray-400'}`}
                    >
                      <ChatIcon />
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className="block truncate leading-snug">
                        {session.title}
                      </span>
                      <span
                        className={`block text-xs mt-0.5 ${
                          isActive ? 'text-brand-400' : 'text-gray-400'
                        }`}
                      >
                        {dateLabel}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </nav>
    </aside>
  );
}
