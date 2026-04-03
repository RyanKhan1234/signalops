/**
 * useDigest — custom hook for managing the digest request lifecycle.
 *
 * Handles:
 * - Submitting prompts via streaming SSE (with fallback to non-streaming)
 * - Real-time pipeline progress events
 * - Loading state
 * - Error state
 * - Chat message history
 * - Abort on component unmount
 */

import { useState, useCallback, useRef } from 'react';
import type { ChatMessage, DigestResponse, StreamEvent } from '../types/digest';
import { submitDigestStream, submitDigestRequest, DigestApiError } from '../services/api';
import { getMockDigestResponse } from '../mocks/mockDigestResponse';
import { generateId } from '../utils/generateId';

const USE_MOCK = import.meta.env['VITE_USE_MOCK_API'] === 'true';

interface UseDigestReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  streamEvents: StreamEvent[];
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
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([]);
  const [latestDigest, setLatestDigest] = useState<DigestResponse | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const submitPrompt = useCallback(async (prompt: string) => {
    if (isLoading) return;

    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const userMessage: ChatMessage = {
      id: generateId(),
      type: 'user',
      content: prompt,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setStreamEvents([]);

    try {
      let digest: DigestResponse;

      if (USE_MOCK) {
        digest = await getMockDigestResponse(prompt);
      } else {
        const request = { prompt, user_id: 'default' };
        try {
          digest = await submitDigestStream(
            request,
            (event, data) => {
              const streamEvent: StreamEvent = {
                event: event as StreamEvent['event'],
                data,
              };
              setStreamEvents((prev) => [...prev, streamEvent]);
            },
            controller.signal
          );
        } catch (streamErr) {
          if (streamErr instanceof DigestApiError && streamErr.code === 'REQUEST_CANCELLED') {
            throw streamErr;
          }
          digest = await submitDigestRequest(request, controller.signal);
        }
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
      setStreamEvents([]);
    }
  }, [isLoading]);

  const clearMessages = useCallback(() => {
    abortControllerRef.current?.abort();
    setMessages([]);
    setLatestDigest(null);
    setIsLoading(false);
    setStreamEvents([]);
  }, []);

  return {
    messages,
    isLoading,
    streamEvents,
    latestDigest,
    submitPrompt,
    clearMessages,
  };
}
