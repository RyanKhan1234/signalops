/**
 * QueryBar — floating bottom bar shown after a digest is loaded.
 * Displays a "New query..." hint bar that opens a modal overlay with
 * the full ChatInput when clicked. Modal closes on submit or Escape key.
 */

import { useState, useEffect, useCallback } from 'react';
import { ChatInput } from '../chat/ChatInput';

interface QueryBarProps {
  onSubmit: (prompt: string) => void;
  isLoading: boolean;
}

/**
 * Wraps submit so the modal closes after the prompt is submitted.
 */
function useModalSubmit(
  onSubmit: (prompt: string) => void,
  closeModal: () => void
) {
  return useCallback(
    (prompt: string) => {
      onSubmit(prompt);
      closeModal();
    },
    [onSubmit, closeModal]
  );
}

/**
 * Fixed bottom query bar with modal overlay containing the full ChatInput.
 */
export function QueryBar({ onSubmit, isLoading }: QueryBarProps) {
  const [isOpen, setIsOpen] = useState(false);

  const closeModal = useCallback(() => setIsOpen(false), []);
  const handleSubmit = useModalSubmit(onSubmit, closeModal);

  // Close modal on Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeModal();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, closeModal]);

  return (
    <>
      {/* Fixed bottom bar */}
      <div className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-3 z-10">
        <div className="max-w-4xl mx-auto">
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            disabled={isLoading}
            className="w-full flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-400 hover:bg-white hover:border-brand-300 hover:text-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Open new digest query"
          >
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
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
            <span className="flex-1 text-left">New query...</span>
            <span className="text-xs text-gray-300 hidden sm:block">
              {typeof navigator !== 'undefined' && navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+K
            </span>
          </button>
        </div>
      </div>

      {/* Modal overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/50 flex items-end justify-center"
          onClick={(e) => {
            // Close if clicking the backdrop
            if (e.target === e.currentTarget) closeModal();
          }}
          role="dialog"
          aria-modal="true"
          aria-label="New digest query"
        >
          <div className="bg-white rounded-t-2xl p-6 pb-8 w-full max-w-2xl shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-900">New Digest Query</h2>
              <button
                type="button"
                onClick={closeModal}
                aria-label="Close query modal"
                className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            <ChatInput
              onSubmit={handleSubmit}
              isLoading={isLoading}
              placeholder="Ask about a competitor, market trend, or request a new digest..."
            />
          </div>
        </div>
      )}
    </>
  );
}
