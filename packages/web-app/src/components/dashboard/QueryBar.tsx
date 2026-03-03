/**
 * QueryBar — fixed bottom bar shown after a digest is loaded.
 * Clicking it clears the current digest and returns to the EmptyState,
 * where the user can type a new query using the standard ChatInput.
 * No modal overlay is used.
 */

interface QueryBarProps {
  onClear: () => void;
  isLoading: boolean;
}

/**
 * Fixed bottom bar that transitions back to the EmptyState on click.
 */
export function QueryBar({ onClear, isLoading }: QueryBarProps) {
  return (
    <div className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-3 z-10">
      <div className="max-w-4xl mx-auto">
        <button
          type="button"
          onClick={onClear}
          disabled={isLoading}
          className="w-full flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-400 hover:bg-white hover:border-brand-300 hover:text-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Clear digest and start over"
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
        </button>
      </div>
    </div>
  );
}
