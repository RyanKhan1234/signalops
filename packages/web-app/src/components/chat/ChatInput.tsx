/**
 * ChatInput — Natural language prompt input for submitting digest requests.
 *
 * Features:
 * - Textarea that expands with content
 * - Submit via button or Cmd/Ctrl + Enter keyboard shortcut
 * - Disabled and loading states during digest generation
 * - Character limit with counter
 * - Prompt suggestion chips
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import type { KeyboardEvent, ChangeEvent, FormEvent } from 'react';

const MAX_CHARS = 500;

const PROMPT_SUGGESTIONS = [
  "What's new in AI model releases this week?",
  'Deep dive on sports betting regulation',
  'Latest news on OpenAI',
  'Any risks or controversies around Anthropic?',
  "What's trending in AI agents right now?",
] as const;

interface ChatInputProps {
  /** Called when the user submits a prompt */
  onSubmit: (prompt: string) => void;
  /** True while a digest is being generated */
  isLoading: boolean;
  /** Placeholder text for the textarea */
  placeholder?: string;
}

/**
 * Chat input area with prompt suggestions and keyboard shortcut support.
 */
export function ChatInput({
  onSubmit,
  isLoading,
  placeholder = 'What are you researching today?',
}: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const trimmed = value.trim();
  const isOverLimit = value.length > MAX_CHARS;
  const canSubmit = trimmed.length > 0 && !isLoading && !isOverLimit;

  /** Auto-resize the textarea to fit content */
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [value, resizeTextarea]);

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
  };

  const handleSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!canSubmit) return;
    onSubmit(trimmed);
    setValue('');
    // Reset textarea height after clearing
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setValue(suggestion);
    textareaRef.current?.focus();
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Prompt suggestion chips */}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Prompt suggestions">
        {PROMPT_SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => handleSuggestionClick(suggestion)}
            disabled={isLoading}
            className="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1"
          >
            {suggestion}
          </button>
        ))}
      </div>

      {/* Input form */}
      <form onSubmit={handleSubmit} className="relative">
        <div
          className={`flex flex-col rounded-xl border bg-white shadow-sm transition-colors ${
            isOverLimit
              ? 'border-red-300 ring-1 ring-red-300'
              : 'border-gray-200 focus-within:border-brand-400 focus-within:ring-1 focus-within:ring-brand-400'
          }`}
        >
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isLoading}
            rows={3}
            aria-label="Digest prompt"
            aria-describedby="char-count submit-hint"
            className="w-full resize-none rounded-t-xl bg-transparent px-4 pt-4 pb-2 text-sm text-gray-900 placeholder-gray-400 outline-none disabled:cursor-not-allowed disabled:opacity-60"
          />

          <div className="flex items-center justify-between px-4 pb-3">
            <div className="flex items-center gap-3">
              <span
                id="char-count"
                className={`text-xs ${
                  isOverLimit ? 'text-red-500 font-medium' : 'text-gray-400'
                }`}
                aria-live="polite"
              >
                {value.length}/{MAX_CHARS}
              </span>
              <span id="submit-hint" className="text-xs text-gray-400">
                {navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+Enter to submit
              </span>
            </div>

            <button
              type="submit"
              disabled={!canSubmit}
              aria-label="Submit digest request"
              className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
            >
              {isLoading ? (
                <>
                  <svg
                    className="h-4 w-4 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
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
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Generating...
                </>
              ) : (
                <>
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
                      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                    />
                  </svg>
                  Generate Digest
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
