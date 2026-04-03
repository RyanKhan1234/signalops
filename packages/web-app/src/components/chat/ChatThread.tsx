/**
 * ChatThread — scrollable conversation thread for the chat-session layout.
 *
 * Renders the full message history for a session:
 * - user messages as small query label chips
 * - digest messages as full DashboardContent sections
 * - error messages as red banners
 * - loading spinner at bottom when isLoading
 * - empty state placeholder when no messages
 *
 * Auto-scrolls to bottom when messages change or loading starts.
 */

import { useEffect, useRef } from 'react';
import type { ChatMessage, DigestResponse, StreamEvent } from '../../types/digest';
import { DashboardContent } from '../dashboard/DashboardContent';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/ErrorAlert';
import { StreamingProgress } from './StreamingProgress';

interface ChatThreadProps {
  messages: ChatMessage[];
  isLoading: boolean;
  streamEvents?: StreamEvent[];
}

/**
 * Renders the chat thread with messages and auto-scroll behaviour.
 */
export function ChatThread({ messages, isLoading, streamEvents = [] }: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom whenever messages change or loading state changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div
      className="flex-1 overflow-y-auto"
      role="log"
      aria-label="Chat messages"
      aria-live="polite"
    >
      {/* Empty state */}
      {messages.length === 0 && !isLoading && (
        <div className="flex h-full items-center justify-center px-6 py-16">
          <div className="text-center max-w-sm">
            <div className="mb-4 flex items-center justify-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50">
                <svg
                  className="h-7 w-7 text-brand-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
            </div>
            <p className="text-sm text-gray-500">
              What are you researching today?
            </p>
          </div>
        </div>
      )}

      {/* Message list */}
      {(messages.length > 0 || isLoading) && (
        <div className="flex flex-col">
          {messages.map((message) => (
            <div key={message.id}>
              {message.type === 'user' && (
                <div className="px-6 pt-6 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700 max-w-2xl">
                      <svg
                        className="mr-1.5 h-3.5 w-3.5 flex-shrink-0 text-gray-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                        />
                      </svg>
                      <span className="truncate">{message.content as string}</span>
                    </span>
                    <time
                      dateTime={message.timestamp}
                      className="flex-shrink-0 text-xs text-gray-400"
                    >
                      {new Date(message.timestamp).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </time>
                  </div>
                </div>
              )}

              {message.type === 'digest' && typeof message.content === 'object' && (
                <div className="pb-4">
                  <DashboardContent digest={message.content as DigestResponse} />
                </div>
              )}

              {message.type === 'error' && (
                <div className="px-6 py-4">
                  <ErrorAlert message={message.content as string} />
                </div>
              )}
            </div>
          ))}

          {/* Streaming progress or loading spinner at bottom of thread */}
          {isLoading && (
            <div className="px-6 py-4">
              {streamEvents.length > 0 ? (
                <StreamingProgress events={streamEvents} />
              ) : (
                <div className="flex items-center justify-center py-4">
                  <LoadingSpinner size="lg" label="Connecting to agent..." />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Scroll anchor */}
      <div ref={bottomRef} aria-hidden="true" />
    </div>
  );
}
