/**
 * ChatMessageList — renders the conversational thread of user prompts and digest responses.
 */

import type { ChatMessage } from '../../types/digest';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/ErrorAlert';
import { DigestViewer } from '../digest/DigestViewer';

interface ChatMessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
}

/**
 * Renders the full chat thread including user messages, loading states,
 * error messages, and digest responses.
 */
export function ChatMessageList({ messages, isLoading }: ChatMessageListProps) {
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50">
          <svg
            className="h-8 w-8 text-brand-500"
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
        <h3 className="text-base font-medium text-gray-900">
          Ready for intelligence
        </h3>
        <p className="mt-1 max-w-sm text-sm text-gray-500">
          Type a prompt below or choose a suggestion to generate your first competitive digest.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6" role="log" aria-label="Chat messages" aria-live="polite">
      {messages.map((message) => (
        <div key={message.id} className="flex flex-col gap-2">
          {message.type === 'user' && (
            <div className="flex justify-end">
              <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-brand-600 px-4 py-3 text-sm text-white shadow-sm">
                <p className="whitespace-pre-wrap">{message.content as string}</p>
                <time
                  dateTime={message.timestamp}
                  className="mt-1 block text-right text-xs text-brand-200"
                >
                  {new Date(message.timestamp).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </time>
              </div>
            </div>
          )}

          {message.type === 'digest' && typeof message.content === 'object' && !Array.isArray(message.content) && (
            <div className="flex justify-start">
              <div className="w-full">
                <div className="mb-2 flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100">
                    <svg
                      className="h-3.5 w-3.5 text-brand-600"
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
                  <span className="text-xs font-medium text-gray-500">SignalOps</span>
                  <time
                    dateTime={message.timestamp}
                    className="text-xs text-gray-400"
                  >
                    {new Date(message.timestamp).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </time>
                </div>
                <DigestViewer digest={message.content} />
              </div>
            </div>
          )}

          {message.type === 'error' && (
            <div className="flex justify-start">
              <div className="w-full max-w-2xl">
                <ErrorAlert message={message.content as string} />
              </div>
            </div>
          )}
        </div>
      ))}

      {isLoading && (
        <div className="flex justify-start">
          <div className="rounded-2xl rounded-tl-sm border border-gray-200 bg-white px-5 py-4 shadow-sm">
            <LoadingSpinner label="Generating competitive intelligence digest..." />
          </div>
        </div>
      )}
    </div>
  );
}
