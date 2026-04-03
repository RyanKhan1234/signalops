/**
 * EmptyState — centered landing view shown before any digest is generated.
 * Includes the logo, heading, subtext, ChatInput, and suggestion chips.
 */

import { ChatInput } from '../chat/ChatInput';

interface EmptyStateProps {
  onSubmit: (prompt: string) => void;
  isLoading: boolean;
}

/**
 * Full-page centered empty state with prompt input for the initial view.
 */
export function EmptyState({ onSubmit, isLoading }: EmptyStateProps) {
  return (
    <div className="flex-1 flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-2xl flex flex-col items-center gap-8">
        {/* Logo and heading */}
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-600 shadow-lg">
            <svg
              className="h-9 w-9 text-white"
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
            <h1 className="text-2xl font-bold text-gray-900">
              Personal Research Tool
            </h1>
            <p className="mt-2 text-base text-gray-500 max-w-md">
              Enter a prompt below to generate a structured digest of market signals,
              risks, opportunities, and action items.
            </p>
          </div>
        </div>

        {/* Chat input — full width up to max-w-2xl */}
        <div className="w-full">
          <ChatInput onSubmit={onSubmit} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
}
