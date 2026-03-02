/**
 * useDigest — custom hook for managing the digest request lifecycle.
 *
 * Handles:
 * - Submitting prompts to the API (or mock)
 * - Loading state
 * - Error state
 * - Chat message history
 * - Abort on component unmount
 */

import { useState, useCallback, useRef } from 'react';
import type { ChatMessage, DigestResponse } from '../types/digest';
import { submitDigestRequest, DigestApiError } from '../services/api';
import { getMockDigestResponse } from '../mocks/mockDigestResponse';
import { generateId } from '../utils/generateId';

const USE_MOCK = import.meta.env['VITE_USE_MOCK_API'] === 'true';

interface UseDigestReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  latestDigest: DigestResponse | null;
  submitPrompt: (prompt: string) => Promise<void>;
  clearMessages: () => void;
}

/**
 * Manages the chat message history and digest request lifecycle.
 */
export function useDigest(): UseDigestReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [latestDigest, setLatestDigest] = useState<DigestResponse | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const submitPrompt = useCallback(async (prompt: string) => {
    if (isLoading) return;

    // Cancel any in-flight request
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Add user message
    const userMessage: ChatMessage = {
      id: generateId(),
      type: 'user',
      content: prompt,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      let digest: DigestResponse;

      if (USE_MOCK) {
        digest = await getMockDigestResponse(prompt);
      } else {
        digest = await submitDigestRequest(
          { prompt },
          controller.signal
        );
      }

      const digestMessage: ChatMessage = {
        id: generateId(),
        type: 'digest',
        content: digest,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, digestMessage]);
      setLatestDigest(digest);
    } catch (err) {
      // Don't add error message if the request was deliberately cancelled
      if (err instanceof DigestApiError && err.code === 'REQUEST_CANCELLED') {
        return;
      }

      const errorMessage = err instanceof DigestApiError
        ? err.message
        : 'An unexpected error occurred while generating the digest. Please try again.';

      const errorChatMessage: ChatMessage = {
        id: generateId(),
        type: 'error',
        content: errorMessage,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, errorChatMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading]);

  const clearMessages = useCallback(() => {
    abortControllerRef.current?.abort();
    setMessages([]);
    setLatestDigest(null);
    setIsLoading(false);
  }, []);

  return {
    messages,
    isLoading,
    latestDigest,
    submitPrompt,
    clearMessages,
  };
}
